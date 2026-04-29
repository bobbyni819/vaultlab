"""Figure extraction from PDFs.

Extracts embedded images from PDFs, attempts to pair each with its caption,
and saves them as standalone PNG files with sidecar metadata.

Uses PyMuPDF (fitz) for image extraction — best library for this on Python.
Captions are detected by searching for "Figure N." (or "Fig. N.") text near
each image bbox.

Pipeline:
    extract_figures(pdf_path, output_dir) → list[FigureRecord]

Each FigureRecord is a dict:
    {
        "path": "/abs/path/fig_1.png",
        "page": 3,
        "figure_num": "1",       # "1", "2A", "S1", or "" if undetected
        "caption": "...",
        "width_px": 1200,
        "height_px": 800,
        "min_dimension": 800,    # smaller of width/height — used for quality filter
        "bbox": [x0, y0, x1, y1] # location on page, in PDF points
    }

Quality filter: by default skips images with min_dimension < 200 px or
file_size < 5 KB (likely icons, logos, or rasterized math symbols).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Caption pattern — matches "Figure 1.", "Fig. 1.", "Figure 1A.", "Figure S1." etc.
_CAPTION_RE = re.compile(
    r"(?:^|\n)(?:Figure|Fig\.?)\s*([0-9A-Za-z]+)\s*[\.\:\)]\s*",
    re.IGNORECASE,
)

_DEFAULT_MIN_DIM = 200  # pixels — smaller than this is probably an icon
_DEFAULT_MIN_BYTES = 5_000  # bytes — smaller is probably a glyph


def extract_figures(
    pdf_path: str | Path,
    output_dir: str | Path,
    min_dimension: int = _DEFAULT_MIN_DIM,
    min_bytes: int = _DEFAULT_MIN_BYTES,
    write_metadata: bool = True,
) -> list[dict[str, Any]]:
    """Extract figures from a PDF and save as PNG files.

    Args:
        pdf_path: Source PDF
        output_dir: Where to save extracted figures
        min_dimension: Skip images smaller than this (px). Default 200.
        min_bytes: Skip images smaller than this (bytes). Default 5KB.
        write_metadata: If True, write a sidecar `.figures.json` with all records.

    Returns:
        List of FigureRecord dicts. Empty list on failure or no figures.
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_path.exists():
        logger.warning("PDF not found: %s", pdf_path)
        return []

    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF (fitz) not installed. pip install pymupdf")
        return []

    records: list[dict[str, Any]] = []
    stem = pdf_path.stem

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        logger.warning("Could not open PDF %s: %s", pdf_path, e)
        return []

    fig_counter = 0
    for page_num, page in enumerate(doc, 1):
        page_text = page.get_text("text")
        # Build a list of (figure_num, caption_text, position) on this page
        captions = _find_captions_on_page(page_text)

        # Get image list — each entry is (xref, smask, w, h, bpc, ...)
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.n - pix.alpha >= 4:  # CMYK → convert to RGB
                    pix = fitz.Pixmap(fitz.csRGB, pix)

                w, h = pix.width, pix.height
                if min(w, h) < min_dimension:
                    pix = None
                    continue

                fig_counter += 1
                out_path = output_dir / f"{stem}_fig{fig_counter}.png"
                pix.save(str(out_path))
                pix = None  # release

                size = out_path.stat().st_size
                if size < min_bytes:
                    out_path.unlink(missing_ok=True)
                    continue

                # Get bounding box of this image on the page
                bbox = None
                try:
                    rects = page.get_image_rects(xref)
                    if rects:
                        r = rects[0]
                        bbox = [r.x0, r.y0, r.x1, r.y1]
                except Exception:
                    pass

                # Pair with caption — pick the closest caption on this page
                # (heuristic: caption usually appears below image)
                fig_num, caption = _pick_caption(captions, bbox)

                rec = {
                    "path": str(out_path),
                    "page": page_num,
                    "figure_num": fig_num,
                    "caption": caption,
                    "width_px": w,
                    "height_px": h,
                    "min_dimension": min(w, h),
                    "bbox": bbox,
                    "size_bytes": size,
                }
                records.append(rec)
            except Exception as e:
                logger.debug("Could not extract image xref=%s on page %d: %s", xref, page_num, e)

    doc.close()

    if write_metadata and records:
        meta_path = output_dir / f"{stem}.figures.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

    logger.info("Extracted %d figures from %s", len(records), pdf_path)
    return records


def _find_captions_on_page(text: str) -> list[tuple[str, str, int]]:
    """Return list of (figure_num, caption_text, char_offset) on a page.

    Caption text is taken as the line containing the match plus the next
    line (heuristic — most captions span 1-3 lines).
    """
    results = []
    for m in _CAPTION_RE.finditer(text):
        fig_num = m.group(1)
        start = m.end()
        # Take ~300 chars after the match as the caption
        snippet = text[start : start + 300].split("\n\n")[0].strip()
        # Truncate at next "Figure" mention if any
        next_fig = _CAPTION_RE.search(snippet)
        if next_fig:
            snippet = snippet[: next_fig.start()].strip()
        results.append((fig_num, snippet, m.start()))
    return results


def _pick_caption(
    captions: list[tuple[str, str, int]],
    bbox: list[float] | None,
) -> tuple[str, str]:
    """Pair an image bbox with its likely caption.

    Heuristic: caption usually appears below the image. Without exact
    coordinates we just pick the first un-claimed caption on the page,
    which works in most single-column journal layouts. For multi-figure
    pages with mixed positions, this can mis-pair — flag those for human
    review.

    Returns (figure_num, caption_text). Empty strings if no caption found.
    """
    if not captions:
        return ("", "")
    # Simple: take the first caption (best-effort)
    fig_num, snippet, _ = captions[0]
    # Remove from list so the next image gets the next caption
    captions.pop(0)
    return (fig_num, snippet)


def write_figure_notes(
    pdf_path: str | Path,
    output_dir: str | Path,
    paper_title: str = "",
    paper_doi: str = "",
) -> str:
    """Run extract_figures and write a markdown notes file describing each figure.

    The notes file is intended for downstream consumers (slide builders,
    KB search) — a quick way for an LLM to know what figures exist in a
    paper without reopening the PDF.

    Output structure:
        <output_dir>/<pdf_stem>.figures.md

    Returns the path to the markdown file (empty string on failure).
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    figures = extract_figures(pdf_path, output_dir)
    if not figures:
        return ""

    md_path = output_dir / f"{pdf_path.stem}.figures.md"
    lines = [
        "---",
        f'title: "Figures from {paper_title or pdf_path.stem}"',
        f'source_pdf: "{pdf_path}"',
        f'doi: "{paper_doi}"',
        f"figure_count: {len(figures)}",
        "type: figure_dissection",
        "---",
        "",
        f"# Figures from {paper_title or pdf_path.stem}",
        "",
        f"Extracted {len(figures)} figure(s) from `{pdf_path.name}`.",
        "",
    ]
    for i, fig in enumerate(figures, 1):
        rel_path = Path(fig["path"]).name
        fig_num = fig["figure_num"] or f"(unmarked {i})"
        lines.extend(
            [
                f"## Figure {fig_num}",
                "",
                f"- File: `{rel_path}`",
                f"- Page: {fig['page']}",
                f"- Dimensions: {fig['width_px']} x {fig['height_px']} px",
                "",
            ]
        )
        if fig["caption"]:
            lines.extend(
                [
                    "**Caption:**",
                    "",
                    fig["caption"],
                    "",
                ]
            )
        else:
            lines.append("_(no caption detected — review manually)_\n")
        lines.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info("Wrote figure notes to %s", md_path)
    return str(md_path)
