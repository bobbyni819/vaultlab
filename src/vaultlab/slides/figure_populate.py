"""Populate an existing deck with figures, producing auto + aspirational variants.

Bobby's 2026-05-02 ask: "create two versions of the decks — 1 deck with
all figures we can actually extract automatically, 2nd deck with what we
hope for — a mix of figures we can already extract + placeholders for
figures the user needs to fetch manually."

Two modes:

* ``auto``         — insert only figures we can actually fetch
                     (paperclip JPGs OR PyMuPDF on cached PDFs). Slides
                     where no figure is obtainable keep their bullet
                     fallback. The deck is "honest about what we have."
* ``aspirational`` — same as auto, PLUS for slides where the cited
                     paper is high-impact but figure-fetch failed, drop a
                     "FIGURE NEEDED" call-out text box on the slide
                     pointing to the publisher URL. The deck is "what
                     we'd want — fetch the missing figures manually to
                     make this slide complete."

Both variants are saved as separate .pptx files (``-auto.pptx`` and
``-aspirational.pptx``) so the user can pick which to share. Audit
runs on both before declaring done.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


_PICTURE_SHAPE_TYPE = 13


@dataclass
class FigureSlot:
    """One figure-gap slide that needs filling."""

    slide_index: int
    slide_title: str
    candidate_dois: list[str] = field(default_factory=list)


@dataclass
class FigurePopulateResult:
    """Outcome of populating a deck with figures."""

    deck_path: Path
    mode: str  # "auto" | "aspirational"
    n_inserted: int = 0
    n_placeholders: int = 0
    inserted_dois: list[str] = field(default_factory=list)
    placeholder_dois: list[str] = field(default_factory=list)


def fetch_figure_from_paperclip(
    paper_id: str,
    *,
    cache_dir: Path,
    paperclip_binary: str | None = None,
) -> Path | None:
    """Try to download figure_1.jpg from paperclip's virtual filesystem.

    Returns local path if successful, None otherwise.
    """
    if not paperclip_binary:
        paperclip_binary = shutil.which("paperclip")
    if not paperclip_binary:
        return None
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path = cache_dir / f"{paper_id}_figure_1.jpg"
    if out_path.exists() and out_path.stat().st_size > 5000:
        return out_path

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["MSYS_NO_PATHCONV"] = "1"

    # Try figure_1, then a few common fallbacks
    for fname in ("figure_1.jpg", "figure_1_a.jpg", "figure_2.jpg", "fig_1.jpg"):
        try:
            r = subprocess.run(
                [paperclip_binary, "cat", f"/papers/{paper_id}/figures/{fname}"],
                capture_output=True,
                timeout=60,
                env=env,
            )
        except (subprocess.TimeoutExpired, OSError):
            continue
        if r.returncode == 0 and len(r.stdout) > 5000 and r.stdout[:3] == b"\xff\xd8\xff":
            out_path.write_bytes(r.stdout)
            return out_path
    return None


def fetch_figure_from_local_pdf(
    pdf_path: Path,
    *,
    cache_dir: Path,
) -> Path | None:
    """Extract figure_1 from a locally-cached PDF via PyMuPDF.

    Returns local path to the largest extracted figure, None on failure.
    """
    if not pdf_path.exists():
        return None
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    try:
        from vaultlab.research.figures import extract_figures
    except ImportError:
        return None

    try:
        records = extract_figures(
            pdf_path=pdf_path,
            output_dir=cache_dir,
            min_dimension=300,
            min_bytes=10_000,
            write_metadata=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("PyMuPDF extract failed for %s: %s", pdf_path, exc)
        return None

    if not records:
        return None
    # Sort by min_dimension desc — pick the largest figure (most likely to be a real figure, not an icon)
    records.sort(key=lambda r: r.get("min_dimension", 0), reverse=True)
    return Path(records[0]["path"])


def _doi_slug(doi: str) -> str:
    return doi.lower().replace("/", "_")


def _try_resolve_paperclip_id_for_doi(doi: str, *, paperclip_binary: str) -> str | None:
    """Map a DOI to a paperclip paper-id via lookup.

    Returns the paperclip ID (e.g. ``arx_2107.07953``, ``PMC...``) or None.
    """
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["MSYS_NO_PATHCONV"] = "1"
    try:
        r = subprocess.run(
            [paperclip_binary, "lookup", "doi", doi.strip().lower()],
            capture_output=True,
            timeout=30,
            env=env,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if r.returncode != 0:
        return None
    out = r.stdout.decode("utf-8", errors="replace")
    # Output format includes "<id> · <source> · <date>" line
    m = re.search(r"\b(arx_\S+|PMC\d+|bio_\w+|med_\w+)\b", out)
    return m.group(1) if m else None


def populate_deck_with_figures(
    deck_path: Path | str,
    *,
    candidate_dois: list[str],
    pdf_cache_dir: Path | str,
    figure_staging_dir: Path | str,
    mode: str = "auto",
    out_path: Path | str | None = None,
) -> FigurePopulateResult:
    """Insert figures into a deck's figure-gap slides.

    Args:
        deck_path: Existing .pptx file to populate.
        candidate_dois: Ordered list of DOIs cited in the arc, most-
            important first. We try to resolve each to a paperclip
            paper-id and fetch its figure_1.jpg.
        pdf_cache_dir: Where local PDFs live for the PyMuPDF fallback.
            Used when paperclip doesn't have the paper.
        figure_staging_dir: Where downloaded figures are cached so
            multiple deck variants can share them.
        mode: "auto" (insert only fetchable) or "aspirational" (also
            add FIGURE-NEEDED placeholders for unfetchable papers).
        out_path: Where to save the populated deck. Defaults to
            ``<deck_path>-<mode>.pptx`` next to the input.

    Returns:
        :class:`FigurePopulateResult`.
    """
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor

    deck_path = Path(deck_path)
    pdf_cache_dir = Path(pdf_cache_dir)
    figure_staging_dir = Path(figure_staging_dir)
    figure_staging_dir.mkdir(parents=True, exist_ok=True)

    if out_path is None:
        out_path = deck_path.with_name(deck_path.stem + f"-{mode}.pptx")
    else:
        out_path = Path(out_path)

    paperclip_binary = shutil.which("paperclip")

    # Identify figure-gap slides — section_intro / figure-titled slides
    # without an existing image.
    from vaultlab.slides.audit import audit_deck
    audit = audit_deck(deck_path)
    gap_slides = [s for s in audit.per_slide if s.figure_gap]
    if not gap_slides:
        logger.info("No figure-gap slides in %s; nothing to populate", deck_path)
        # Still copy to the output path for consistency
        shutil.copy(str(deck_path), str(out_path))
        return FigurePopulateResult(deck_path=out_path, mode=mode)

    # Resolve DOIs OR paperclip native IDs → figure paths. Cache so
    # multiple deck variants share the staging dir.
    resolved: dict[str, Path | None] = {}
    for ident in candidate_dois:
        if ident in resolved:
            continue
        fig_path: Path | None = None

        # Native paperclip ID (PMC<digits>, arx_, bio_, med_)? Fetch
        # directly without DOI lookup.
        is_pcl_native = bool(re.match(
            r"^(PMC\d+|arx_|bio_|med_)", ident, re.I,
        ))
        if is_pcl_native and paperclip_binary:
            fig_path = fetch_figure_from_paperclip(
                ident, cache_dir=figure_staging_dir,
                paperclip_binary=paperclip_binary,
            )
        # Otherwise treat as DOI — try paperclip lookup → figure_1
        elif paperclip_binary:
            pid = _try_resolve_paperclip_id_for_doi(
                ident, paperclip_binary=paperclip_binary,
            )
            if pid:
                fig_path = fetch_figure_from_paperclip(
                    pid, cache_dir=figure_staging_dir,
                    paperclip_binary=paperclip_binary,
                )

        # PyMuPDF fallback on cached PDF (only for DOI inputs)
        if fig_path is None and not is_pcl_native:
            slug = _doi_slug(ident)
            for candidate in (
                pdf_cache_dir / f"{slug}.pdf",
                pdf_cache_dir / f"{slug.replace('.', '-')}.pdf",
            ):
                if candidate.exists():
                    fig_path = fetch_figure_from_local_pdf(
                        candidate, cache_dir=figure_staging_dir,
                    )
                    if fig_path is not None:
                        break
        resolved[ident] = fig_path
        if len(resolved) >= len(gap_slides) * 3:
            break

    available_dois = [d for d, p in resolved.items() if p is not None]
    unavailable_dois = [d for d, p in resolved.items() if p is None]

    # Open the deck and insert
    prs = Presentation(str(deck_path))
    inserted_dois: list[str] = []
    placeholder_dois: list[str] = []

    available_iter = iter(available_dois)
    unavail_iter = iter(unavailable_dois)

    for s in gap_slides:
        slide = prs.slides[s.index - 1]
        slide_w = prs.slide_width
        slide_h = prs.slide_height
        pic_w = Inches(4.0)
        pic_h = Inches(2.5)
        left = slide_w - pic_w - Inches(0.3)
        top = slide_h - pic_h - Inches(0.5)

        # Try to use a real figure first
        try:
            doi = next(available_iter)
            fig_path = resolved[doi]
            slide.shapes.add_picture(
                str(fig_path), left, top, width=pic_w, height=pic_h,
            )
            # Caption
            caption_top = top + pic_h + Emu(60_000)
            caption = slide.shapes.add_textbox(left, caption_top, pic_w, Inches(0.4))
            tf = caption.text_frame
            tf.text = f"Figure: {doi}"
            for p in tf.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(8)
                    r.font.italic = True
                    r.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
            inserted_dois.append(doi)
            continue
        except StopIteration:
            pass

        # Aspirational mode: drop a FIGURE NEEDED placeholder
        if mode == "aspirational":
            try:
                doi = next(unavail_iter)
            except StopIteration:
                continue
            placeholder = slide.shapes.add_textbox(left, top, pic_w, pic_h)
            tf = placeholder.text_frame
            tf.text = (
                f"📥 FIGURE NEEDED\n\n"
                f"Manually fetch Figure 1 from:\n"
                f"https://doi.org/{doi}\n\n"
                f"Drop the image here to complete this slide."
            )
            for p in tf.paragraphs:
                p.alignment = 2  # center
                for r in p.runs:
                    r.font.size = Pt(11)
                    r.font.color.rgb = RGBColor(0xAA, 0x33, 0x33)
            placeholder_dois.append(doi)

    prs.save(str(out_path))
    return FigurePopulateResult(
        deck_path=out_path,
        mode=mode,
        n_inserted=len(inserted_dois),
        n_placeholders=len(placeholder_dois),
        inserted_dois=inserted_dois,
        placeholder_dois=placeholder_dois,
    )


__all__ = [
    "FigurePopulateResult",
    "FigureSlot",
    "fetch_figure_from_paperclip",
    "fetch_figure_from_local_pdf",
    "populate_deck_with_figures",
]
