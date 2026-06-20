"""Unified per-claim and per-figure manuscript verification ladder."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from vaultlab.citations import Citation
from vaultlab.figures.understand.visual_qa import VisualQAResult, visual_qa_figure
from vaultlab.manuscript.citation_gate import CitationGateReport, run_citation_gate
from vaultlab.manuscript.claim_ledger import (
    CitationTier,
    Claim,
    ClaimLedger,
    FigureLink,
)
from vaultlab.manuscript.preflight import (
    FixItem,
    ManuscriptPreflightReport,
    run_manuscript_preflight,
)
from vaultlab.roles._invoke import AuditPrompt

_ACCEPTABLE_REVIEWER_VERDICTS = {
    "accept",
    "accepted",
    "acceptable",
    "approve",
    "approved",
    "pass",
    "passed",
    "ship",
}


class LadderRung(Enum):
    """Ordered manuscript verification ladder rung."""

    PROPOSED = 0
    SOURCE_SEARCHED = 1
    QUOTE_BACKED = 2
    RENDERED = 3
    PIXEL_AUDITED = 4
    REVIEWER_APPROVED = 5

    @property
    def rank(self) -> int:
        """Numeric ordering for strict ladder comparisons."""
        return int(self.value)


@dataclass(frozen=True)
class ClaimRung:
    """Verification ladder position for one manuscript claim."""

    claim_id: str
    rung: LadderRung
    next_blocker: str | None

    def to_dict(self) -> dict[str, str | None]:
        """Serialize the claim rung to a JSON-ready dict."""
        return {
            "claim_id": self.claim_id,
            "rung": self.rung.name,
            "next_blocker": self.next_blocker,
        }


@dataclass(frozen=True)
class FigureRung:
    """Verification ladder position for one referenced figure."""

    figure_id: str
    rung: LadderRung
    next_blocker: str | None

    def to_dict(self) -> dict[str, str | None]:
        """Serialize the figure rung to a JSON-ready dict."""
        return {
            "figure_id": self.figure_id,
            "rung": self.rung.name,
            "next_blocker": self.next_blocker,
        }


@dataclass(frozen=True)
class VerificationLadderReport:
    """Unified verification ladder dashboard for manuscript claims and figures."""

    claim_rungs: list[ClaimRung]
    figure_rungs: list[FigureRung]
    min_claim_rung: LadderRung | None
    summary: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report to a JSON-ready dict."""
        return {
            "claim_rungs": [rung.to_dict() for rung in self.claim_rungs],
            "figure_rungs": [rung.to_dict() for rung in self.figure_rungs],
            "min_claim_rung": self.min_claim_rung.name if self.min_claim_rung is not None else None,
            "summary": dict(self.summary),
        }

    def to_markdown(self) -> str:
        """Render the ladder as a reviewer-facing markdown dashboard."""
        weakest = self.min_claim_rung.name if self.min_claim_rung is not None else "NONE"
        lines = [
            "# Verification Ladder Dashboard",
            "",
            (
                "The manuscript is only as verified as its weakest claim: "
                f"`{weakest}`."
            ),
            "",
            "## Claim rungs",
            "",
            "| claim | rung | next blocker |",
            "|---|---|---|",
        ]
        if self.claim_rungs:
            for claim_rung in self.claim_rungs:
                lines.append(
                    f"| {_cell(claim_rung.claim_id)} | {claim_rung.rung.name} | "
                    f"{_cell(claim_rung.next_blocker or 'none')} |"
                )
        else:
            lines.append("| none |  |  |")

        lines.extend(
            [
                "",
                "## Figure rungs",
                "",
                "| figure | rung | next blocker |",
                "|---|---|---|",
            ]
        )
        if self.figure_rungs:
            for figure_rung in self.figure_rungs:
                lines.append(
                    f"| {_cell(figure_rung.figure_id)} | {figure_rung.rung.name} | "
                    f"{_cell(figure_rung.next_blocker or 'none')} |"
                )
        else:
            lines.append("| none |  |  |")

        lines.extend(["", "## Claim summary", ""])
        for ladder_rung in LadderRung:
            lines.append(f"- `{ladder_rung.name}`: {self.summary.get(ladder_rung.name, 0)}")
        return "\n".join(lines).rstrip() + "\n"


def assess_verification_ladder(
    manuscript_md: str,
    *,
    ledger: ClaimLedger | None = None,
    figures_dir: Path | str | None = None,
    coverage_dir: Path | str | None = None,
    citations: list[Citation] | None = None,
    run_visual_qa: bool = False,
    executor: Callable[[AuditPrompt], Mapping[str, Any]] | None = None,
) -> VerificationLadderReport:
    """Compose existing manuscript checks into strict per-item ladder rungs."""
    active_ledger = _safe_ledger(manuscript_md, ledger)
    citation_report = _safe_citation_gate(active_ledger, citations)
    preflight = _safe_preflight(
        manuscript_md,
        active_ledger,
        figures_dir=figures_dir,
        coverage_dir=coverage_dir,
        run_visual_qa=run_visual_qa,
        executor=executor,
    )
    visual_results = _safe_visual_qa(active_ledger, figures_dir, run_visual_qa)

    figure_links_by_claim = _figure_links_by_claim(active_ledger.figure_links)
    citation_links_by_claim = _citation_links_by_claim(active_ledger)
    citation_blockers = _citation_blockers_by_claim(citation_report)
    visual_by_figure = _visual_results_by_figure(visual_results, preflight)

    claim_rungs = [
        _claim_rung(
            claim,
            citation_links_by_claim.get(claim.claim_id, []),
            figure_links_by_claim.get(claim.claim_id, []),
            citation_blockers.get(claim.claim_id, []),
            visual_by_figure,
            figures_dir=figures_dir,
            coverage_dir=coverage_dir,
            preflight=preflight,
        )
        for claim in active_ledger.claims
    ]
    figure_rungs = [
        _figure_rung(
            figure_id,
            visual_by_figure,
            figures_dir=figures_dir,
            coverage_dir=coverage_dir,
            preflight=preflight,
        )
        for figure_id in _unique_figures(active_ledger.figure_links)
    ]
    return VerificationLadderReport(
        claim_rungs=claim_rungs,
        figure_rungs=figure_rungs,
        min_claim_rung=_min_claim_rung(claim_rungs),
        summary=_summary(claim_rungs),
    )


def _safe_ledger(manuscript_md: str, ledger: ClaimLedger | None) -> ClaimLedger:
    if ledger is not None:
        return ledger
    try:
        return ClaimLedger.from_markdown(manuscript_md)
    except Exception:
        return ClaimLedger()


def _safe_citation_gate(
    ledger: ClaimLedger,
    citations: list[Citation] | None,
) -> CitationGateReport | None:
    try:
        if citations is not None:
            return run_citation_gate(citations=citations)
        return run_citation_gate(ledger=ledger)
    except Exception:
        return None


def _safe_preflight(
    manuscript_md: str,
    ledger: ClaimLedger,
    *,
    figures_dir: Path | str | None,
    coverage_dir: Path | str | None,
    run_visual_qa: bool,
    executor: Callable[[AuditPrompt], Mapping[str, Any]] | None,
) -> ManuscriptPreflightReport | None:
    try:
        return run_manuscript_preflight(
            manuscript_md,
            ledger=ledger,
            figures_dir=figures_dir,
            coverage_dir=coverage_dir,
            roles=[],
            run_visual_qa=run_visual_qa,
            executor=executor,
        )
    except Exception:
        return None


def _safe_visual_qa(
    ledger: ClaimLedger,
    figures_dir: Path | str | None,
    run_visual_qa: bool,
) -> list[VisualQAResult]:
    figures_root = Path(figures_dir) if figures_dir is not None else None
    if not run_visual_qa or figures_root is None:
        return []
    results: list[VisualQAResult] = []
    for figure_id in _unique_figures(ledger.figure_links):
        png = figures_root / f"{figure_id}.png"
        if not png.exists():
            continue
        try:
            results.append(visual_qa_figure(png, run_vision=False, write_sidecar=False))
        except Exception:
            continue
    return results


def _claim_rung(
    claim: Claim,
    citation_links: list[Any],
    figure_links: list[FigureLink],
    citation_blockers: list[str],
    visual_by_figure: dict[str, VisualQAResult],
    *,
    figures_dir: Path | str | None,
    coverage_dir: Path | str | None,
    preflight: ManuscriptPreflightReport | None,
) -> ClaimRung:
    if not _source_searched(claim, citation_links):
        return ClaimRung(
            claim.claim_id,
            LadderRung.PROPOSED,
            "needs at least one citation link or kind=novel",
        )
    if not _quote_backed(citation_links):
        return ClaimRung(
            claim.claim_id,
            LadderRung.SOURCE_SEARCHED,
            _first_or_default(citation_blockers, "needs Tier-3 citation support"),
        )
    if not figure_links:
        return ClaimRung(
            claim.claim_id,
            LadderRung.QUOTE_BACKED,
            "needs at least one rendered figure link",
        )
    missing_figures = [
        link.figure_id
        for link in figure_links
        if not _figure_exists(link.figure_id, figures_dir=figures_dir, coverage_dir=coverage_dir)
    ]
    if missing_figures:
        return ClaimRung(
            claim.claim_id,
            LadderRung.QUOTE_BACKED,
            f"referenced figure is not rendered: {', '.join(missing_figures)}",
        )
    failed_qa = [
        link.figure_id
        for link in figure_links
        if _visual_qa_verdict(link.figure_id, visual_by_figure) == "FAIL"
    ]
    if failed_qa:
        return ClaimRung(
            claim.claim_id,
            LadderRung.RENDERED,
            f"visual QA failed for figure: {', '.join(failed_qa)}",
        )
    unaudited = [
        link.figure_id
        for link in figure_links
        if link.figure_id not in visual_by_figure
    ]
    if unaudited:
        return ClaimRung(
            claim.claim_id,
            LadderRung.RENDERED,
            f"needs pixel audit for figure: {', '.join(unaudited)}",
        )
    reviewer_blocker = _reviewer_blocker(preflight, claim.claim_id)
    if reviewer_blocker is not None:
        return ClaimRung(claim.claim_id, LadderRung.PIXEL_AUDITED, reviewer_blocker)
    return ClaimRung(claim.claim_id, LadderRung.REVIEWER_APPROVED, None)


def _figure_rung(
    figure_id: str,
    visual_by_figure: dict[str, VisualQAResult],
    *,
    figures_dir: Path | str | None,
    coverage_dir: Path | str | None,
    preflight: ManuscriptPreflightReport | None,
) -> FigureRung:
    if not _figure_exists(figure_id, figures_dir=figures_dir, coverage_dir=coverage_dir):
        return FigureRung(figure_id, LadderRung.PROPOSED, "figure is not rendered")
    verdict = _visual_qa_verdict(figure_id, visual_by_figure)
    if verdict == "FAIL":
        return FigureRung(figure_id, LadderRung.RENDERED, "visual QA failed")
    if verdict is None:
        return FigureRung(figure_id, LadderRung.RENDERED, "needs pixel audit")
    reviewer_blocker = _reviewer_blocker(preflight, figure_id)
    if reviewer_blocker is not None:
        return FigureRung(figure_id, LadderRung.PIXEL_AUDITED, reviewer_blocker)
    return FigureRung(figure_id, LadderRung.REVIEWER_APPROVED, None)


def _source_searched(claim: Claim, citation_links: list[Any]) -> bool:
    return bool(citation_links) or claim.kind == "novel"


def _quote_backed(citation_links: list[Any]) -> bool:
    return all(getattr(link, "tier", None) is CitationTier.TIER_3 for link in citation_links)


def _figure_exists(
    figure_id: str,
    *,
    figures_dir: Path | str | None,
    coverage_dir: Path | str | None,
) -> bool:
    if coverage_dir is not None and _coverage_exists(Path(coverage_dir), figure_id):
        return True
    if figures_dir is None:
        return False
    figures_root = Path(figures_dir)
    return any((figures_root / f"{figure_id}{suffix}").exists() for suffix in (".png", ".svg", ".pdf"))


def _coverage_exists(coverage_root: Path, figure_id: str) -> bool:
    return any(
        (coverage_root / name).exists()
        for name in (
            f"{figure_id}.coverage.json",
            f"{figure_id}.json",
            f"{figure_id}.coverage-manifest.json",
        )
    )


def _reviewer_blocker(
    preflight: ManuscriptPreflightReport | None,
    target: str,
) -> str | None:
    if preflight is None:
        return None
    for item in preflight.fix_queue:
        if item.severity == "error" and _fix_item_touches(item, target):
            return item.message
    if preflight.aggregated is not None:
        verdict = preflight.aggregated.aggregated_verdict
        if not _is_acceptable_verdict(verdict):
            return f"aggregated reviewer verdict is {verdict}"
    return None


def _is_acceptable_verdict(verdict: object) -> bool:
    return str(verdict).strip().lower() in _ACCEPTABLE_REVIEWER_VERDICTS


def _fix_item_touches(item: FixItem, target: str) -> bool:
    fields = [item.where, item.message, item.fix, item.source]
    target_lower = target.lower()
    for field in fields:
        if field is None:
            continue
        text = field.lower()
        if target_lower in text:
            return True
        try:
            if Path(field).stem.lower() == target_lower:
                return True
        except ValueError:
            continue
    return False


def _visual_qa_verdict(
    figure_id: str,
    visual_by_figure: dict[str, VisualQAResult],
) -> str | None:
    result = visual_by_figure.get(figure_id)
    if result is None:
        return None
    return result.verdict


def _visual_results_by_figure(
    explicit_results: list[VisualQAResult],
    preflight: ManuscriptPreflightReport | None,
) -> dict[str, VisualQAResult]:
    results: dict[str, VisualQAResult] = {}
    for result in explicit_results:
        results[_figure_id_from_png(result.png)] = result
    if preflight is not None:
        for result in preflight.visual_qa:
            results.setdefault(_figure_id_from_png(result.png), result)
    return results


def _figure_id_from_png(path: str) -> str:
    return Path(path).stem


def _figure_links_by_claim(links: list[FigureLink]) -> dict[str, list[FigureLink]]:
    grouped: dict[str, list[FigureLink]] = {}
    for link in links:
        grouped.setdefault(link.claim_id, []).append(link)
    return grouped


def _citation_links_by_claim(ledger: ClaimLedger) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for link in ledger.citation_links:
        grouped.setdefault(link.claim_id, []).append(link)
    return grouped


def _citation_blockers_by_claim(
    report: CitationGateReport | None,
) -> dict[str, list[str]]:
    if report is None:
        return {}
    blockers: dict[str, list[str]] = {}
    for status in report.blocked:
        if status.source:
            blockers.setdefault(status.source, []).append(f"{status.citation_key} needs Tier-3")
    return blockers


def _unique_figures(links: list[FigureLink]) -> list[str]:
    seen: set[str] = set()
    figures: list[str] = []
    for link in links:
        if link.figure_id not in seen:
            seen.add(link.figure_id)
            figures.append(link.figure_id)
    return figures


def _min_claim_rung(claim_rungs: list[ClaimRung]) -> LadderRung | None:
    if not claim_rungs:
        return None
    return min((rung.rung for rung in claim_rungs), key=lambda rung: rung.rank)


def _summary(claim_rungs: list[ClaimRung]) -> dict[str, int]:
    return {
        rung.name: sum(1 for claim_rung in claim_rungs if claim_rung.rung is rung)
        for rung in LadderRung
    }


def _first_or_default(values: list[str], default: str) -> str:
    return values[0] if values else default


def _cell(value: str) -> str:
    return value.replace("\n", " ").replace("|", "\\|")


__all__ = [
    "ClaimRung",
    "FigureRung",
    "LadderRung",
    "VerificationLadderReport",
    "assess_verification_ladder",
]
