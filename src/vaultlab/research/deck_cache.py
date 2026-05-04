"""Cross-deck consistency cache — same paper → same figure + same notes.

When the same paper is cited across multiple decks (Hickey 2021 in both
multi-lung short and spatial-tx short, etc.), cache the figure choice +
3-tier speaker_notes so all decks get a consistent treatment of that
paper.

Cache layout:
    ~/.cache/vaultlab/deck_cache/<doi-slug>.json

Each entry stores:
    - doi
    - figure_path: absolute path to the chosen figure file
    - speaker_notes: full 3-tier dict (mental_map + script + walkthrough)
    - citation: "Authors et al., Journal Year"
    - cached_at: ISO timestamp

Use ``deck_decision`` as the single entry point — it reads from cache,
falls back to fresh computation (notes_from_summary + figure_picker),
caches the result, and returns it.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from vaultlab.research.figure_picker import pick_best_figure_for_doi
from vaultlab.research.notes_from_summary import (
    load_summary,
    speaker_notes_from_summary,
)

logger = logging.getLogger(__name__)


def _default_cache_dir() -> Path:
    return Path.home() / ".cache" / "vaultlab" / "deck_cache"


@dataclass
class DeckDecision:
    """A cached deck-level decision about how to use a paper across decks."""

    doi: str
    figure_path: str
    speaker_notes: dict[str, Any]
    citation: str
    cached_at: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "doi": self.doi,
            "figure_path": self.figure_path,
            "speaker_notes": self.speaker_notes,
            "citation": self.citation,
            "cached_at": self.cached_at,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> DeckDecision:
        return cls(
            doi=data.get("doi", ""),
            figure_path=data.get("figure_path", ""),
            speaker_notes=data.get("speaker_notes") or {},
            citation=data.get("citation", ""),
            cached_at=data.get("cached_at", ""),
        )


def _slug_for_doi(doi: str) -> str:
    """Sluggify a DOI for use as a filename."""
    return doi.lower().replace("/", "_").replace(":", "_")


def _cache_path_for_doi(
    doi: str, *, cache_dir: Path | str | None = None
) -> Path:
    base = Path(cache_dir) if cache_dir else _default_cache_dir()
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{_slug_for_doi(doi)}.json"


def get_cached_decision(
    doi: str, *, cache_dir: Path | str | None = None
) -> DeckDecision | None:
    """Return cached :class:`DeckDecision` for ``doi`` or ``None``."""
    p = _cache_path_for_doi(doi, cache_dir=cache_dir)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return DeckDecision.from_json(data)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Bad cache file %s: %s", p, exc)
        return None


def cache_decision(
    decision: DeckDecision, *, cache_dir: Path | str | None = None
) -> Path:
    """Persist a :class:`DeckDecision` to the cache, return its file path.

    Stamps ``cached_at`` if not already set.
    """
    if not decision.cached_at:
        decision.cached_at = datetime.now().astimezone().isoformat(timespec="seconds")
    p = _cache_path_for_doi(decision.doi, cache_dir=cache_dir)
    p.write_text(
        json.dumps(decision.to_json(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return p


def clear_cache(*, cache_dir: Path | str | None = None) -> int:
    """Delete all cached deck decisions. Returns the number of files removed."""
    base = Path(cache_dir) if cache_dir else _default_cache_dir()
    if not base.exists():
        return 0
    n = 0
    for f in base.glob("*.json"):
        try:
            f.unlink()
            n += 1
        except OSError:
            pass
    return n


def deck_decision(
    doi_slug: str,
    *,
    summary_dir: Path | str = "G:/My Drive/Knowledge/vaultlab/Wiki/Summaries",
    papers_dir: Path | str = "G:/My Drive/Knowledge/vaultlab/Sources/Papers",
    figure_staging_dir: Path | str = "C:/Users/bobby/.cache/vaultlab/_deck_figures_2026_05_03",
    figure_path_override: str | None = None,
    cache_dir: Path | str | None = None,
    use_cache: bool = True,
    audience_familiar: bool = False,
) -> DeckDecision | None:
    """Consult the cache, otherwise compute fresh decision and cache it.

    Args:
        doi_slug: The DOI slug (e.g., ``10.1038_s41586-022-05672-3``).
        summary_dir: Where Tier-A summaries live.
        papers_dir: Where cached PDFs live (for figure picker).
        figure_staging_dir: Where extracted figures get cached.
        figure_path_override: If supplied, use this exact path as the
            figure (skips the picker). Useful when the deck author has a
            specific figure in mind.
        cache_dir: Override the default cache location.
        use_cache: When ``False``, recompute even if cached.
        audience_familiar: Forwarded to ``speaker_notes_from_summary``.

    Returns:
        :class:`DeckDecision` or ``None`` if no summary exists.
    """
    # Normalize the slug to a DOI key (slug uses _ for /, but doi is the key)
    if use_cache:
        cached = get_cached_decision(doi_slug, cache_dir=cache_dir)
        if cached is not None:
            # If override provided AND differs from cache, respect override
            # but don't clobber the cached version (caller may want both)
            if figure_path_override and figure_path_override != cached.figure_path:
                return DeckDecision(
                    doi=cached.doi,
                    figure_path=figure_path_override,
                    speaker_notes=cached.speaker_notes,
                    citation=cached.citation,
                    cached_at=cached.cached_at,
                )
            return cached

    # Fresh compute
    record = load_summary(doi_slug, summaries_dir=summary_dir)
    if record is None:
        logger.info("No summary for %s; cannot make decision", doi_slug)
        return None

    notes = speaker_notes_from_summary(record, audience_familiar=audience_familiar)
    citation = record.citation_footer()

    # Figure: explicit override > picker > None
    if figure_path_override:
        figure_path = figure_path_override
    else:
        picked = pick_best_figure_for_doi(
            doi_slug,
            papers_dir=papers_dir,
            output_dir=figure_staging_dir,
        )
        figure_path = str(picked) if picked else ""

    decision = DeckDecision(
        doi=doi_slug,
        figure_path=figure_path,
        speaker_notes=notes,
        citation=citation,
    )
    cache_decision(decision, cache_dir=cache_dir)
    return decision


__all__ = [
    "DeckDecision",
    "deck_decision",
    "get_cached_decision",
    "cache_decision",
    "clear_cache",
]
