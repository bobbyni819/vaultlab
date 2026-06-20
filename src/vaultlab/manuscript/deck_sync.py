"""Sync manuscript claim-ledger figure links against slide-deck figures."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from vaultlab.manuscript.claim_ledger import ClaimLedger
from vaultlab.slides.deck import Deck, DeckPlan

ProblemKind = Literal["claim_figure_missing_from_deck", "deck_figure_not_in_claims"]

_FIGURE_PREFIX_RE = re.compile(r"^(?:figure|fig)", re.IGNORECASE)


def figure_key(s: str) -> str:
    """Normalize a figure reference for ledger/deck matching.

    The key is the path stem, lowercased. A leading ``figure`` or ``fig`` is
    stripped when doing so leaves a non-empty value, because both ledger IDs
    and deck paths pass through the same helper before comparison.
    """
    stem = Path(s).stem.strip().lower()
    without_prefix = _FIGURE_PREFIX_RE.sub("", stem, count=1).strip()
    return without_prefix or stem


@dataclass(frozen=True)
class DeckSyncProblem:
    """One mismatch between claim-ledger figures and deck figures."""

    kind: ProblemKind
    figure: str
    message: str
    claim_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "figure": self.figure,
            "message": self.message,
            "claim_ids": list(self.claim_ids),
        }


@dataclass(frozen=True)
class DeckSyncReport:
    """Structured claim-ledger to deck sync report."""

    ok: bool
    problems: list[DeckSyncProblem]
    claim_figures: list[str]
    deck_figures: list[str]
    matched: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "problems": [problem.to_dict() for problem in self.problems],
            "claim_figures": list(self.claim_figures),
            "deck_figures": list(self.deck_figures),
            "matched": list(self.matched),
        }

    def to_markdown(self) -> str:
        max_len = max(len(self.claim_figures), len(self.deck_figures), 1)
        lines = [
            "# Deck Sync Report",
            "",
            f"- Status: {'ok' if self.ok else 'problems found'}",
            f"- Matched: {', '.join(self.matched) if self.matched else 'none'}",
            "",
            "## Claim Figures vs Deck Figures",
            "",
            "| claim figures | deck figures |",
            "|---|---|",
        ]
        for idx in range(max_len):
            claim = self.claim_figures[idx] if idx < len(self.claim_figures) else ""
            deck = self.deck_figures[idx] if idx < len(self.deck_figures) else ""
            lines.append(f"| {_cell(claim)} | {_cell(deck)} |")

        lines.extend(["", "## Problems", ""])
        if not self.problems:
            lines.append("- none")
        else:
            for problem in self.problems:
                claim_ids = f" (claims: {', '.join(problem.claim_ids)})" if problem.claim_ids else ""
                lines.append(f"- `{problem.kind}` `{problem.figure}`: {problem.message}{claim_ids}")
        return "\n".join(lines) + "\n"


def sync_claims_to_deck(
    ledger: ClaimLedger,
    deck: Deck | DeckPlan | object,
    *,
    extra_deck_figures: list[str] | None = None,
) -> DeckSyncReport:
    """Compare claim-ledger figure links with figures referenced by a deck.

    Supports low-level :class:`vaultlab.slides.deck.Deck` objects via
    ``Slide.figure_path`` and typed :class:`vaultlab.slides.deck.DeckPlan`
    objects via ``DeckSlide.content["figure_path"]``. Unexpected deck shapes
    are treated as empty decks instead of raising.
    """
    claim_ids_by_figure = _claim_figure_map(ledger)
    claim_figures = sorted(claim_ids_by_figure)
    deck_figures = sorted(_deck_figure_keys(deck, extra_deck_figures or []))
    matched = sorted(set(claim_figures) & set(deck_figures))

    problems: list[DeckSyncProblem] = []
    for figure in sorted(set(claim_figures) - set(deck_figures)):
        claim_ids = claim_ids_by_figure[figure]
        problems.append(
            DeckSyncProblem(
                kind="claim_figure_missing_from_deck",
                figure=figure,
                message=f"Claim-linked figure {figure} is not referenced by the deck.",
                claim_ids=list(claim_ids),
            )
        )
    for figure in sorted(set(deck_figures) - set(claim_figures)):
        problems.append(
            DeckSyncProblem(
                kind="deck_figure_not_in_claims",
                figure=figure,
                message=f"Deck figure {figure} is not linked from any claim.",
            )
        )

    return DeckSyncReport(
        ok=not problems,
        problems=problems,
        claim_figures=claim_figures,
        deck_figures=deck_figures,
        matched=matched,
    )


def _claim_figure_map(ledger: ClaimLedger) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for link in ledger.figure_links:
        key = figure_key(link.figure_id)
        if not key:
            continue
        claim_ids = out.setdefault(key, [])
        if link.claim_id not in claim_ids:
            claim_ids.append(link.claim_id)
    for claim_ids in out.values():
        claim_ids.sort()
    return out


def _deck_figure_keys(deck: Deck | DeckPlan | object, extra_deck_figures: list[str]) -> set[str]:
    figures: set[str] = set()
    for slide in _slides_from_deck(deck):
        for reference in _figure_references_from_slide(slide):
            key = figure_key(reference)
            if key:
                figures.add(key)
    for reference in extra_deck_figures:
        key = figure_key(reference)
        if key:
            figures.add(key)
    return figures


def _slides_from_deck(deck: Deck | DeckPlan | object) -> list[object]:
    try:
        slides = getattr(deck, "slides", None)
    except Exception:
        return []
    if not isinstance(slides, list):
        return []
    return [slide for slide in slides if slide is not None]


def _figure_references_from_slide(slide: object) -> list[str]:
    references: list[str] = []
    direct = _string_or_none(_safe_getattr(slide, "figure_path"))
    if direct is not None:
        references.append(direct)

    content = _safe_getattr(slide, "content")
    if isinstance(content, dict):
        content_figure = _string_or_none(content.get("figure_path"))
        if content_figure is not None:
            references.append(content_figure)

    return references


def _safe_getattr(obj: object, name: str) -> object | None:
    try:
        return getattr(obj, name, None)
    except Exception:
        return None


def _string_or_none(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _cell(value: str) -> str:
    return value.replace("\n", " ").replace("|", "\\|")


__all__ = [
    "DeckSyncProblem",
    "DeckSyncReport",
    "figure_key",
    "sync_claims_to_deck",
]
