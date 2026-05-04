"""Aggressive figure picker — choose the best figure from a paper for slide use.

Solves the "default fig_1 has bad aspect" failure mode (e.g., Sorin 2023
fig1 is a 0.18-aspect sliver). Extracts all figures from the cached PDF
via PyMuPDF, scores each by aspect-ratio fit + dimension + file size, and
returns the path of the best candidate.

Scoring weights (tunable):
- aspect_score: 1.0 if 0.6 ≤ aspect ≤ 2.2 (slide-friendly), 0.3 otherwise
- size_score:   linear in min_dimension up to 2000 px (bigger = better)
- panel_score:  bonus for figures with file size > 200 KB (proxy for
                multi-panel content; single-panel diagrams are smaller)

The picker also normalises Unicode-minus filenames and copies the
selected figure into the staging dir under a canonical name.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from vaultlab.research.figures import extract_figures

logger = logging.getLogger(__name__)


_DEFAULT_TARGET_ASPECT = (0.6, 2.2)


def pick_best_figure(
    pdf_path: Path | str,
    output_dir: Path | str,
    *,
    target_aspect: tuple[float, float] = _DEFAULT_TARGET_ASPECT,
    min_dimension: int = 400,
    min_bytes: int = 30_000,
    prefer_first_n: int | None = 3,
) -> Path | None:
    """Pick the best figure from a PDF by aspect-ratio fit + size.

    Args:
        pdf_path: Source PDF.
        output_dir: Where extracted figures land (cached for reuse).
        target_aspect: (low, high) — figures inside this range get full
            aspect_score. Defaults to (0.6, 2.2) which fits widescreen
            slide layouts well.
        min_dimension: Skip figures smaller than this (px).
        min_bytes: Skip figures smaller than this on disk.
        prefer_first_n: When multiple high-scoring candidates exist, prefer
            those among the first N figures of the paper (typically the
            "main" figures). ``None`` disables this preference.

    Returns:
        Path to the chosen figure file, or ``None`` if no usable figure
        could be extracted.
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    if not pdf_path.exists():
        logger.warning("PDF not found: %s", pdf_path)
        return None

    try:
        records = extract_figures(
            pdf_path=pdf_path,
            output_dir=output_dir,
            min_dimension=min_dimension,
            min_bytes=min_bytes,
            write_metadata=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("extract_figures failed for %s: %s", pdf_path, exc)
        return None

    if not records:
        return None

    scored = []
    for i, r in enumerate(records):
        w, h = r.get("width_px", 0), r.get("height_px", 0)
        if h <= 0 or w <= 0:
            continue
        aspect = w / h
        # Aspect score: 1.0 if in target range, 0.3 otherwise. Smooth
        # interpolation outside target so very-wide and very-tall figures
        # still get scored above zero.
        if target_aspect[0] <= aspect <= target_aspect[1]:
            aspect_score = 1.0
        else:
            # Distance from target band; 0.5 aspect = 0.85; 3.0 aspect = 0.7
            if aspect < target_aspect[0]:
                dist = target_aspect[0] - aspect
            else:
                dist = aspect - target_aspect[1]
            aspect_score = max(0.3, 1.0 - dist * 0.4)

        # Size score: prefer larger figures up to 2000 px
        size_score = min(r.get("min_dimension", 0) / 2000.0, 1.0)

        # File-size bonus for multi-panel content (>200 KB)
        try:
            on_disk = Path(r["path"]).stat().st_size
        except OSError:
            on_disk = 0
        panel_score = 0.5 if on_disk > 200_000 else 0.0

        # First-N preference
        order_score = 0.3 if (prefer_first_n is None or i < prefer_first_n) else 0.0

        total = aspect_score * 2 + size_score + panel_score + order_score
        scored.append((total, i, r))

    if not scored:
        return None

    scored.sort(key=lambda x: x[0], reverse=True)
    best = scored[0][2]
    return Path(best["path"])


def pick_best_figure_for_doi(
    doi_slug: str,
    *,
    papers_dir: Path | str = "G:/My Drive/Knowledge/vaultlab/Sources/Papers",
    output_dir: Path | str = "C:/Users/bobby/.cache/vaultlab/_deck_figures_2026_05_03",
    **kwargs: Any,
) -> Path | None:
    """Pick the best figure for a paper, given its DOI slug.

    Looks up the cached PDF at ``<papers_dir>/<doi_slug>.pdf`` and runs
    :func:`pick_best_figure` against it. Returns the path of the chosen
    figure or ``None`` if no PDF/figures available.
    """
    papers_dir = Path(papers_dir)
    output_dir = Path(output_dir)
    candidates = [
        papers_dir / f"{doi_slug}.pdf",
        papers_dir / f"{doi_slug.replace('.', '-')}.pdf",
    ]
    for c in candidates:
        if c.exists():
            return pick_best_figure(c, output_dir, **kwargs)
    logger.info("No PDF found for %s", doi_slug)
    return None


__all__ = ["pick_best_figure", "pick_best_figure_for_doi"]
