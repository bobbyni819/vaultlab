"""Deck audit — self-evaluation step for slide-deck outputs.

Runs after a deck is composed to surface gaps before declaring "done":

* Slides with **0 images** when the layout intended a figure-or-bullets
  slot (the build_deck_from_lineage_result composer falls back to
  bullets when figure-fetch fails — the audit catches that silent
  degradation).
* Slides that are **text-only and very thin** (e.g. <50 chars across
  all text frames) — usually a layout failure, not a deliberate empty.
* Citation-vs-figure mismatch: papers cited in the arc that *would
  have* yielded a slide-feature figure but weren't fetched (so the
  user can manually fetch them).

The audit returns a structured ``DeckAuditResult`` and a
human-readable markdown report. Bobby's 2026-05-02 ask was: "have
you actually read everything here and evaluate it" — this is the
"have you actually" check.

Usage::

    from vaultlab.slides.audit import audit_deck

    result = audit_deck(
        deck_path,
        arc_path=arc_path,                # optional: cross-check arc citations
        figure_staging_dir=Path("/tmp/_deck_figures"),  # optional: figures available locally
    )
    print(result.to_markdown_report())
    if result.severity >= "warn":
        print(result.manual_fetch_shopping_list())
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Import at module top so tests can patch it cleanly via
# vaultlab.slides.audit.Presentation. python-pptx is already a vaultlab
# dependency so the import never fails in normal usage.
try:
    from pptx import Presentation
except ImportError:  # pragma: no cover — defensive only
    Presentation = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


_THIN_SLIDE_TEXT_THRESHOLD = 50  # chars
_PICTURE_SHAPE_TYPE = 13  # python-pptx MSO_SHAPE_TYPE.PICTURE


@dataclass
class SlideAudit:
    """Per-slide audit record."""

    index: int
    title: str
    n_images: int
    n_text_chars: int
    is_thin_text: bool
    is_figure_intended: bool  # heuristic: title contains "figure", "image", section_intro layout, etc.
    figure_gap: bool  # True if figure_intended but n_images == 0


@dataclass
class DeckAuditResult:
    """Audit findings for one deck."""

    deck_path: Path
    n_slides: int
    n_total_images: int
    slides_with_images: int
    text_only_slides: int
    thin_slides: int
    figure_gap_slides: int  # slides where a figure was intended but missing
    per_slide: list[SlideAudit] = field(default_factory=list)
    citations_in_arc: list[str] = field(default_factory=list)  # DOIs cited in the arc

    @property
    def severity(self) -> str:
        """One of "ok", "warn", "fail"."""
        if self.n_total_images == 0 and self.n_slides >= 5:
            return "fail"  # 0 images is a hard failure for a research deck
        if self.figure_gap_slides > 0 or self.thin_slides > 1:
            return "warn"
        if self.n_total_images < self.n_slides // 4:
            # Heuristic: <25% of slides have images for a 5+ slide deck
            return "warn"
        return "ok"

    def to_markdown_report(self) -> str:
        """Render the audit as a human-readable markdown block."""
        lines: list[str] = []
        lines.append(f"### Audit — `{self.deck_path.name}`")
        lines.append(f"")
        sev_emoji = {"ok": "✅", "warn": "⚠️", "fail": "❌"}.get(self.severity, "?")
        lines.append(f"**Severity:** {sev_emoji} `{self.severity}`")
        lines.append(f"")
        lines.append(f"- {self.n_slides} slides, {self.n_total_images} total images")
        lines.append(f"- {self.slides_with_images} slides with at least one image")
        lines.append(f"- {self.text_only_slides} text-only slides")
        lines.append(f"- {self.thin_slides} thin slides (< {_THIN_SLIDE_TEXT_THRESHOLD} chars text)")
        lines.append(f"- {self.figure_gap_slides} slides where a figure was intended but missing")
        lines.append(f"")
        if self.figure_gap_slides:
            lines.append(f"**Figure gaps:**")
            for s in self.per_slide:
                if s.figure_gap:
                    lines.append(f"  * Slide {s.index}: {s.title or '(no title)'}")
            lines.append("")
        return "\n".join(lines)

    def manual_fetch_shopping_list(self, max_items: int = 10) -> str:
        """Render a 'please manually fetch figures from these papers' list.

        For now this is a stub — the citation-to-figure-source map needs
        the arc's DOI list to be passed in via ``citations_in_arc``. When
        present, this surfaces the top-N most-cited DOIs as "high-value
        figures the user could manually pull and drop into the deck."
        """
        if not self.citations_in_arc:
            return "(no arc citations supplied → cannot suggest manual fetches)"
        lines = ["**Recommended manual figure fetches**"]
        lines.append("")
        lines.append("These DOIs are cited in the arc and have ≥1 figure-gap slide. ")
        lines.append("Manually grab Figure 1 from each, drop into the deck:")
        lines.append("")
        for doi in self.citations_in_arc[:max_items]:
            lines.append(f"- `{doi}` — https://doi.org/{doi}")
        return "\n".join(lines)


def audit_deck(
    deck_path: Path | str,
    *,
    arc_path: Path | str | None = None,
    figure_intended_titles: tuple[str, ...] = (
        "figure", "image", "panel", "schematic", "diagram", "overview",
    ),
) -> DeckAuditResult:
    """Audit a .pptx deck for figure / content gaps.

    Args:
        deck_path: Path to the .pptx file.
        arc_path: Optional path to the source arc markdown — when given,
            the audit extracts cited DOIs and includes them in the
            manual-fetch shopping list.
        figure_intended_titles: Lowercased substrings; a slide whose
            title contains any of these is considered "figure-intended".
            Slides matching this pattern with 0 images are flagged as
            ``figure_gap``.

    Returns:
        :class:`DeckAuditResult`.
    """
    deck_path = Path(deck_path)
    prs = Presentation(str(deck_path))

    per_slide: list[SlideAudit] = []
    n_total_images = 0
    slides_with_images = 0
    text_only_slides = 0
    thin_slides = 0
    figure_gap_slides = 0

    for i, slide in enumerate(prs.slides, 1):
        n_images = sum(
            1 for sh in slide.shapes if sh.shape_type == _PICTURE_SHAPE_TYPE
        )
        title = ""
        all_text = ""
        for sh in slide.shapes:
            if sh.has_text_frame:
                txt = sh.text_frame.text or ""
                all_text += txt + "\n"
                if not title and txt.strip():
                    title = txt.strip().split("\n")[0][:80]
        n_text_chars = len(all_text.strip())
        is_thin = n_text_chars < _THIN_SLIDE_TEXT_THRESHOLD and n_images == 0

        title_lc = title.lower()
        is_figure_intended = any(
            kw in title_lc for kw in figure_intended_titles
        )
        # Section-intro slides (often followed by a figure-or-bullets
        # slide) are also figure-intended in the canonical 7-slide layout
        if title_lc.startswith(("history", "development", "state of",
                                "background", "methods", "results")):
            is_figure_intended = True

        figure_gap = is_figure_intended and n_images == 0

        per_slide.append(SlideAudit(
            index=i,
            title=title,
            n_images=n_images,
            n_text_chars=n_text_chars,
            is_thin_text=is_thin,
            is_figure_intended=is_figure_intended,
            figure_gap=figure_gap,
        ))

        n_total_images += n_images
        if n_images:
            slides_with_images += 1
        else:
            text_only_slides += 1
        if is_thin:
            thin_slides += 1
        if figure_gap:
            figure_gap_slides += 1

    citations: list[str] = []
    if arc_path:
        try:
            arc_text = Path(arc_path).read_text(encoding="utf-8", errors="replace")
            citations = _extract_dois_from_arc(arc_text)
        except OSError:
            pass

    return DeckAuditResult(
        deck_path=deck_path,
        n_slides=len(prs.slides),
        n_total_images=n_total_images,
        slides_with_images=slides_with_images,
        text_only_slides=text_only_slides,
        thin_slides=thin_slides,
        figure_gap_slides=figure_gap_slides,
        per_slide=per_slide,
        citations_in_arc=citations,
    )


def _extract_dois_from_arc(text: str) -> list[str]:
    """Pull DOI strings out of arc markdown.

    Recognises both the wikilink style ``[[10.1038_s41586-...]]`` and
    raw ``10.1038/...`` substrings. Returns a deduplicated list in
    arc-order.
    """
    seen: set[str] = set()
    out: list[str] = []
    # Pattern matches: 10.\d{3,9}/<chars>
    doi_re = re.compile(r"10\.\d{3,9}/[\w.\-/_:;()]+", re.I)
    for m in doi_re.finditer(text):
        doi = m.group(0).rstrip(".,;:)")
        # Some wikilinks use _ instead of / in the slug; revert
        if "_" in doi and "/" not in doi:
            # Convert "10.1038_s41586-..." → "10.1038/s41586-..."
            doi = doi.replace("_", "/", 1)
        if doi.lower() not in seen:
            seen.add(doi.lower())
            out.append(doi)
    return out


__all__ = [
    "DeckAuditResult",
    "SlideAudit",
    "audit_deck",
]
