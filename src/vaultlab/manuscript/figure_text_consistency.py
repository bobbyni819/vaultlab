"""Deterministic manuscript figure-text consistency checks.

The identity check is intentionally heuristic: it only flags cases where the
same extracted entity, such as an m/z value, is associated with different
nearby labels in manuscript prose and figure coverage metadata. Absence of a
label or weak context is not treated as a contradiction.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, NamedTuple

from vaultlab.figures.publication.coverage import CoverageManifest
from vaultlab.manuscript.claim_ledger import (
    _TAG_RE,
    ClaimLedger,
    FigureLink,
    NumericLink,
)

ProblemKind = Literal[
    "missing_figure",
    "cut_figure",
    "number_mismatch",
    "identity_contradiction",
]
ProblemSeverity = Literal["error", "warning"]

_FIGURE_REF_RE = re.compile(
    r"\b(?:Fig(?:ure)?s?)\.?\s+"
    r"(?P<refs>[A-Za-z]?\d+[A-Za-z]?(?:\s*(?:,|and|&)\s*[A-Za-z]?\d+[A-Za-z]?)*)(?!\w)",
    re.IGNORECASE,
)
_SINGLE_FIGURE_TOKEN_RE = re.compile(r"(?P<figure>[A-Za-z]?\d+)(?P<panel>[A-Za-z])?$")
_TAG_PANEL_RE = re.compile(r"(?:^|\s)panel=(?P<panel>[^\]\s]+)")
_DEFAULT_IDENTITY_PATTERNS = [r"m/z\s*(?P<entity>[0-9]+\.[0-9]+)"]
_NUMERIC_QUANTITY_RE = re.compile(
    r"\b(?P<quantity>rho|r|p|n|auc|or|mean|median)\s*(?:=|:|<|>|<=|>=)\s*"
    r"(?P<value>[+-]?(?:\d+(?:\.\d+)?|\.\d+))",
    re.IGNORECASE,
)
_DONOR_COUNT_RE = re.compile(
    r"\b(?P<value>\d+)\s+(?:donors?|samples?|cells?|regions?|replicates?)\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9/-]*")
_LABEL_STOPWORDS = {
    "a",
    "an",
    "and",
    "annotated",
    "as",
    "by",
    "figure",
    "fig",
    "in",
    "is",
    "label",
    "labeled",
    "labelled",
    "labels",
    "map",
    "maps",
    "mz",
    "of",
    "region",
    "regions",
    "signal",
    "signals",
    "the",
    "to",
    "was",
    "were",
    "with",
    "z",
}
_KNOWN_LABELS = {
    "cer",
    "lpi",
    "pc",
    "pe",
    "pi",
    "ps",
    "sm",
    "sulfatide",
    "sulphatide",
    "phosphatidylinositol",
}
_FIGURE_SUFFIXES = (".png", ".svg", ".pdf")


@dataclass(frozen=True)
class FigureCallout:
    """One inline figure callout found in manuscript prose."""

    figure_id: str
    panel: str | None = None
    line_number: int = 0
    source: Literal["tag", "prose"] = "prose"
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "figure_id": self.figure_id,
            "panel": self.panel,
            "line_number": self.line_number,
            "source": self.source,
            "raw_text": self.raw_text,
        }


@dataclass(frozen=True)
class ConsistencyProblem:
    """One figure-text consistency problem."""

    kind: ProblemKind
    severity: ProblemSeverity
    message: str
    figure_id: str | None = None
    claim_id: str | None = None
    detail: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "message": self.message,
            "figure_id": self.figure_id,
            "claim_id": self.claim_id,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ConsistencyReport:
    """Structured result from figure-text consistency checks."""

    ok: bool
    problems: list[ConsistencyProblem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "problems": [problem.to_dict() for problem in self.problems],
        }


class _NumericMention(NamedTuple):
    quantity: str
    value: float
    raw_text: str


class _IdentityAssociation(NamedTuple):
    entity: str
    label: str
    source_text: str


def find_figure_callouts(text: str) -> list[FigureCallout]:
    """Find ``[FIG:id]`` tags and prose refs such as ``Figure 5C`` or ``Fig. 6``."""
    callouts: list[FigureCallout] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for match in _TAG_RE.finditer(line):
            if match.group("tag") != "FIG":
                continue
            figure_id, panel = _split_figure_token(match.group("target"))
            explicit_panel = _panel_from_tag_attrs(match.group("attrs"))
            callouts.append(
                FigureCallout(
                    figure_id=figure_id,
                    panel=(explicit_panel or panel),
                    line_number=line_number,
                    source="tag",
                    raw_text=match.group(0),
                )
            )
        for match in _FIGURE_REF_RE.finditer(line):
            for token in _split_prose_refs(match.group("refs")):
                figure_id, panel = _split_figure_token(token)
                callouts.append(
                    FigureCallout(
                        figure_id=figure_id,
                        panel=panel,
                        line_number=line_number,
                        source="prose",
                        raw_text=match.group(0),
                    )
                )
    return callouts


def check_figure_text_consistency(
    manuscript_md: str,
    *,
    ledger: ClaimLedger | None = None,
    figures_dir: Path | str | None = None,
    coverage_dir: Path | str | None = None,
    identity_patterns: list[str] | None = None,
) -> ConsistencyReport:
    """Check manuscript prose against claim-ledger links and coverage manifests.

    Numeric and identity checks are conservative: they flag explicit
    contradictions only when both sides state comparable values or labels.
    Missing evidence, missing labels, and uncertain associations are skipped.
    """
    active_ledger = ledger if ledger is not None else ClaimLedger.from_markdown(manuscript_md)
    figure_root = Path(figures_dir) if figures_dir is not None else None
    coverage_root = Path(coverage_dir) if coverage_dir is not None else None
    callouts = find_figure_callouts(manuscript_md)
    manifests = _read_coverage_manifests(coverage_root)

    problems: list[ConsistencyProblem] = []
    problems.extend(
        _missing_and_cut_figure_problems(
            callouts,
            active_ledger.figure_links,
            figure_root=figure_root,
            coverage_root=coverage_root,
        )
    )
    problems.extend(_numeric_mismatch_problems(manuscript_md, active_ledger, manifests))
    problems.extend(
        _identity_contradiction_problems(
            manuscript_md,
            callouts,
            manifests,
            identity_patterns or _DEFAULT_IDENTITY_PATTERNS,
        )
    )
    return ConsistencyReport(ok=not problems, problems=problems)


def _split_figure_token(token: str) -> tuple[str, str | None]:
    cleaned = token.strip().rstrip(".,;:)")
    match = _SINGLE_FIGURE_TOKEN_RE.fullmatch(cleaned)
    if match is None:
        return cleaned, None
    panel = match.group("panel")
    return match.group("figure"), panel.upper() if panel else None


def _panel_from_tag_attrs(raw_attrs: str) -> str | None:
    match = _TAG_PANEL_RE.search(raw_attrs)
    if match is None:
        return None
    return match.group("panel").strip().upper() or None


def _split_prose_refs(raw_refs: str) -> list[str]:
    return [
        token.strip()
        for token in re.split(r"\s*(?:,|and|&)\s*", raw_refs)
        if token.strip()
    ]


def _read_coverage_manifests(coverage_root: Path | None) -> dict[str, CoverageManifest]:
    if coverage_root is None or not coverage_root.exists():
        return {}
    manifests: dict[str, CoverageManifest] = {}
    for path in coverage_root.glob("*.coverage.json"):
        try:
            manifest = CoverageManifest.read_json(path)
        except (OSError, ValueError):
            continue
        manifests[manifest.figure_id] = manifest
    return manifests


def _missing_and_cut_figure_problems(
    callouts: list[FigureCallout],
    figure_links: list[FigureLink],
    *,
    figure_root: Path | None,
    coverage_root: Path | None,
) -> list[ConsistencyProblem]:
    problems: list[ConsistencyProblem] = []
    if figure_root is None and coverage_root is None:
        return problems

    referenced = {callout.figure_id for callout in callouts}
    referenced.update(link.figure_id for link in figure_links)
    for figure_id in sorted(referenced):
        if not _figure_exists(figure_id, figure_root, coverage_root):
            problems.append(
                ConsistencyProblem(
                    "missing_figure",
                    "error",
                    f"Figure {figure_id} is referenced but no figure file or coverage manifest was found.",
                    figure_id=figure_id,
                )
            )

    prose_referenced = {callout.figure_id for callout in callouts if callout.source == "prose"}
    for link in figure_links:
        if link.figure_id not in prose_referenced:
            problems.append(
                ConsistencyProblem(
                    "cut_figure",
                    "warning",
                    f"Ledger links figure {link.figure_id}, but prose does not mention it.",
                    figure_id=link.figure_id,
                    claim_id=link.claim_id,
                )
            )

    disk_figures = _figures_on_disk(figure_root)
    disk_figures.update(_coverage_ids_on_disk(coverage_root))
    for figure_id in sorted(disk_figures - prose_referenced):
        problems.append(
            ConsistencyProblem(
                "cut_figure",
                "warning",
                f"Figure {figure_id} exists on disk but is not referenced in prose.",
                figure_id=figure_id,
            )
        )
    return _dedupe_problems(problems)


def _figure_exists(
    figure_id: str,
    figure_root: Path | None,
    coverage_root: Path | None,
) -> bool:
    if figure_root is not None:
        for suffix in _FIGURE_SUFFIXES:
            if (figure_root / f"{figure_id}{suffix}").exists():
                return True
    if coverage_root is not None and (coverage_root / f"{figure_id}.coverage.json").exists():
        return True
    return False


def _figures_on_disk(figure_root: Path | None) -> set[str]:
    if figure_root is None or not figure_root.exists():
        return set()
    return {
        path.stem
        for suffix in _FIGURE_SUFFIXES
        for path in figure_root.glob(f"*{suffix}")
        if path.is_file()
    }


def _coverage_ids_on_disk(coverage_root: Path | None) -> set[str]:
    if coverage_root is None or not coverage_root.exists():
        return set()
    return {
        path.name[: -len(".coverage.json")]
        for path in coverage_root.glob("*.coverage.json")
        if path.is_file()
    }


def _numeric_mismatch_problems(
    manuscript_md: str,
    ledger: ClaimLedger,
    manifests: dict[str, CoverageManifest],
) -> list[ConsistencyProblem]:
    problems: list[ConsistencyProblem] = []
    claim_contexts = _claim_contexts(manuscript_md, ledger)
    figure_links_by_claim = _figure_links_by_claim(ledger.figure_links)
    for link in ledger.numeric_links:
        linked = _parse_numeric_link(link)
        if linked is None:
            continue
        quantity, expected = linked
        contexts = [claim_contexts.get(link.claim_id, "")]
        contexts.extend(
            _manifest_text(manifests[figure_link.figure_id])
            for figure_link in figure_links_by_claim.get(link.claim_id, [])
            if figure_link.figure_id in manifests
        )
        for context in contexts:
            mentions = [
                mention for mention in _extract_numeric_mentions(context) if mention.quantity == quantity
            ]
            if not mentions:
                continue
            if any(_numbers_match(mention.value, expected) for mention in mentions):
                continue
            conflicting = mentions[0]
            problems.append(
                ConsistencyProblem(
                    "number_mismatch",
                    "error",
                    (
                        f"Claim {link.claim_id} states {conflicting.raw_text}, but ledger links "
                        f"{link.value}."
                    ),
                    claim_id=link.claim_id,
                    detail={
                        "quantity": quantity,
                        "prose_value": conflicting.value,
                        "ledger_value": expected,
                        "source_file": link.source_file,
                    },
                )
            )
            break
    return problems


def _parse_numeric_link(link: NumericLink) -> tuple[str, float] | None:
    match = _NUMERIC_QUANTITY_RE.search(link.value)
    if match is None:
        return None
    return _normalize_quantity(match.group("quantity")), float(match.group("value"))


def _extract_numeric_mentions(text: str) -> list[_NumericMention]:
    mentions: list[_NumericMention] = []
    for match in _NUMERIC_QUANTITY_RE.finditer(text):
        mentions.append(
            _NumericMention(
                _normalize_quantity(match.group("quantity")),
                float(match.group("value")),
                match.group(0),
            )
        )
    for match in _DONOR_COUNT_RE.finditer(text):
        mentions.append(_NumericMention("n", float(match.group("value")), match.group(0)))
    return mentions


def _normalize_quantity(quantity: str) -> str:
    normalized = quantity.strip().lower()
    return "or" if normalized == "odds ratio" else normalized


def _numbers_match(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)


def _claim_contexts(manuscript_md: str, ledger: ClaimLedger) -> dict[str, str]:
    contexts = {claim.claim_id: claim.text for claim in ledger.claims}
    paragraphs = re.split(r"\n\s*\n", manuscript_md)
    for paragraph in paragraphs:
        for match in _TAG_RE.finditer(paragraph):
            if match.group("tag") == "CLAIM":
                contexts[match.group("target")] = _TAG_RE.sub("", paragraph)
                break
    return contexts


def _figure_links_by_claim(links: list[FigureLink]) -> dict[str, list[FigureLink]]:
    grouped: dict[str, list[FigureLink]] = {}
    for link in links:
        grouped.setdefault(link.claim_id, []).append(link)
    return grouped


def _identity_contradiction_problems(
    manuscript_md: str,
    callouts: list[FigureCallout],
    manifests: dict[str, CoverageManifest],
    identity_patterns: list[str],
) -> list[ConsistencyProblem]:
    problems: list[ConsistencyProblem] = []
    line_by_number = {
        line_number: line for line_number, line in enumerate(manuscript_md.splitlines(), start=1)
    }
    prose_by_figure = _prose_by_figure(callouts, line_by_number, manuscript_md)
    compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in identity_patterns]
    for figure_id, manifest in manifests.items():
        if figure_id not in prose_by_figure:
            continue
        prose_assoc = _extract_identity_associations(prose_by_figure[figure_id], compiled_patterns)
        manifest_assoc = _extract_identity_associations(_manifest_text(manifest), compiled_patterns)
        for entity, prose_labels in prose_assoc.items():
            manifest_labels = manifest_assoc.get(entity)
            if manifest_labels is None:
                continue
            for prose_label in prose_labels:
                for manifest_label in manifest_labels:
                    if _normalize_label(prose_label.label) == _normalize_label(manifest_label.label):
                        continue
                    problems.append(
                        ConsistencyProblem(
                            "identity_contradiction",
                            "error",
                            (
                                f"Figure {figure_id} maps entity {entity} to "
                                f"{manifest_label.label!r} in coverage metadata but "
                                f"{prose_label.label!r} in prose."
                            ),
                            figure_id=figure_id,
                            detail={
                                "entity": entity,
                                "prose_label": prose_label.label,
                                "coverage_label": manifest_label.label,
                                "prose_text": prose_label.source_text,
                                "coverage_text": manifest_label.source_text,
                            },
                        )
                    )
                    break
                else:
                    continue
                break
    return problems


def _prose_by_figure(
    callouts: list[FigureCallout],
    line_by_number: dict[int, str],
    manuscript_md: str,
) -> dict[str, str]:
    grouped: dict[str, list[str]] = {}
    for callout in callouts:
        line = line_by_number.get(callout.line_number, "")
        lines = grouped.setdefault(callout.figure_id, [])
        if line not in lines:
            lines.append(line)
    if not grouped:
        return {"": manuscript_md}
    return {figure_id: "\n".join(lines) for figure_id, lines in grouped.items()}


def _extract_identity_associations(
    text: str,
    patterns: list[re.Pattern[str]],
) -> dict[str, list[_IdentityAssociation]]:
    associations: dict[str, list[_IdentityAssociation]] = {}
    for pattern in patterns:
        for match in pattern.finditer(text):
            entity = _identity_entity(match)
            if entity is None:
                continue
            label = _identity_label(match, text)
            if label is None:
                continue
            associations.setdefault(entity, []).append(_IdentityAssociation(entity, label, text))
    return associations


def _identity_entity(match: re.Match[str]) -> str | None:
    if "entity" in match.groupdict() and match.group("entity") is not None:
        return match.group("entity")
    if match.lastindex:
        return match.group(1)
    return None


def _identity_label(match: re.Match[str], text: str) -> str | None:
    if "label" in match.groupdict() and match.group("label") is not None:
        return match.group("label")
    after = text[match.end() : match.end() + 80]
    cue_match = re.search(
        r"\b(?:as|label(?:ed|led|s)?|annotated\s+as|assigned\s+to|identified\s+as)\b"
        r"[\s:=,-]*(?P<label>[A-Za-z][A-Za-z0-9/-]*)",
        after,
        re.IGNORECASE,
    )
    if cue_match is not None:
        candidate = cue_match.group("label")
        return candidate if _is_label_candidate(candidate) else None
    immediate = _WORD_RE.search(after)
    if immediate is None:
        return None
    candidate = immediate.group(0)
    return candidate if _is_label_candidate(candidate) else None


def _is_label_candidate(token: str) -> bool:
    normalized = _normalize_label(token)
    if normalized in _LABEL_STOPWORDS:
        return False
    return normalized in _KNOWN_LABELS or token.isupper() or normalized.endswith(("tide", "lipid"))


def _normalize_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", label.lower())


def _manifest_text(manifest: CoverageManifest) -> str:
    parts = [
        manifest.figure_id,
        manifest.panel_role or "",
        manifest.footer or "",
        manifest.footer_text(),
        _stringify_jsonish(manifest.params),
        _stringify_jsonish(manifest.analysis_params),
    ]
    return "\n".join(part for part in parts if part)


def _stringify_jsonish(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(f"{key}: {_stringify_jsonish(nested)}" for key, nested in value.items())
    if isinstance(value, list):
        return "\n".join(_stringify_jsonish(item) for item in value)
    if value is None:
        return ""
    return str(value)


def _dedupe_problems(problems: list[ConsistencyProblem]) -> list[ConsistencyProblem]:
    seen: set[tuple[ProblemKind, str | None, str | None, str]] = set()
    deduped: list[ConsistencyProblem] = []
    for problem in problems:
        key = (problem.kind, problem.figure_id, problem.claim_id, problem.message)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(problem)
    return deduped


__all__ = [
    "ConsistencyProblem",
    "ConsistencyReport",
    "FigureCallout",
    "check_figure_text_consistency",
    "find_figure_callouts",
]
