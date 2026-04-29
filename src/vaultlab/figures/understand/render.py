"""Render annotated overlays for visual inspection + downstream PPTX use."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from vaultlab.figures.understand.color_motif import Region
from vaultlab.figures.understand.models import ElementAnnotation

# Solarized-ish palette - high contrast on most figure backgrounds
_PALETTE = [
    (0, 102, 204),
    (220, 50, 47),
    (38, 139, 210),
    (181, 137, 0),
    (133, 153, 0),
    (108, 113, 196),
    (203, 75, 22),
    (211, 54, 130),
    (42, 161, 152),
]


def render_debug_overlay(
    image_path: str | Path,
    regions: Sequence[Region],
    output_path: str | Path,
    *,
    label_by_motif: bool = True,
) -> Path:
    """Draw motif-colored bboxes on the figure for visual inspection.

    Useful for tuning :class:`ColorMotif` thresholds and debugging which
    regions came from which motif.

    Parameters
    ----------
    image_path
        Original figure.
    regions
        Output of :func:`extract_regions` (optionally followed by
        :func:`merge_regions`).
    output_path
        Where to write the annotated PNG.
    label_by_motif
        If ``True``, color regions by motif (one consistent color per motif).
        If ``False``, color sequentially.

    Returns
    -------
    Path
        Resolved path to the written PNG.
    """
    img = Image.open(Path(image_path)).convert("RGB").copy()
    draw = ImageDraw.Draw(img)
    font = _font(max(14, img.height // 60))

    motif_colors: dict[str, tuple[int, int, int]] = {}

    def _color_for(motif_name: str, idx: int) -> tuple[int, int, int]:
        if not label_by_motif:
            return _PALETTE[idx % len(_PALETTE)]
        if motif_name not in motif_colors:
            motif_colors[motif_name] = _PALETTE[len(motif_colors) % len(_PALETTE)]
        return motif_colors[motif_name]

    for i, region in enumerate(regions):
        color = _color_for(region.motif_name, i)
        x0, y0, x1, y1 = region.bbox_px
        draw.rectangle([(x0, y0), (x1, y1)], outline=color, width=4)
        draw.text(
            (x0 + 4, max(0, y0 - 22)),
            f"{region.motif_name}",
            fill=color,
            font=font,
        )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def render_annotated_figure(
    image_path: str | Path,
    annotations: Sequence[ElementAnnotation],
    output_path: str | Path,
    *,
    gutter_width_px: int = 420,
) -> Path:
    """Render the figure with numbered annotations + right-gutter callouts.

    The shipping output of the understanding pipeline. One numbered marker
    per annotation, leader line to a callout in the right gutter.

    Parameters
    ----------
    image_path
        Original figure.
    annotations
        Concept-to-region pairings.
    output_path
        Where to write the annotated PNG.
    gutter_width_px
        Right-side gutter for callout text.

    Returns
    -------
    Path
        Resolved path to the written PNG.
    """
    fig = Image.open(Path(image_path)).convert("RGB")
    W, H = fig.size

    canvas = Image.new("RGB", (W + gutter_width_px, H), (255, 255, 255))
    canvas.paste(fig, (0, 0))
    draw = ImageDraw.Draw(canvas)

    label_font = _font(max(14, H // 55))
    body_font = _font(max(12, H // 75))

    n = len(annotations)
    if n == 0:
        canvas.save(Path(output_path))
        return Path(output_path)

    # Sort callouts top-to-bottom by box-y to minimize leader-line crossings
    indexed = list(enumerate(annotations))
    indexed.sort(key=lambda pair: pair[1].bbox_px[1])

    gutter_x = W + 12
    callout_top = 30
    callout_bottom = H - 30
    spacing = (callout_bottom - callout_top) / max(n, 1)

    for slot, (orig_idx, ann) in enumerate(indexed):
        color = _PALETTE[orig_idx % len(_PALETTE)]
        x0, y0, x1, y1 = ann.bbox_px

        draw.rectangle([(x0, y0), (x1, y1)], outline=color, width=4)

        num = str(orig_idx + 1)
        marker_size = max(28, H // 35)
        try:
            tw, th = draw.textbbox((0, 0), num, font=label_font)[2:]
        except AttributeError:
            tw, th = label_font.getsize(num)  # type: ignore[attr-defined]

        # On-figure marker
        marker_xy = (x0, max(0, y0 - marker_size))
        draw.rectangle(
            [marker_xy, (marker_xy[0] + marker_size, marker_xy[1] + marker_size)],
            fill=color,
        )
        draw.text(
            (marker_xy[0] + (marker_size - tw) / 2, marker_xy[1] + (marker_size - th) / 2 - 2),
            num,
            fill=(255, 255, 255),
            font=label_font,
        )

        # Gutter callout
        callout_y = int(callout_top + spacing * slot)
        anchor_box = (x1, (y0 + y1) // 2)
        anchor_callout = (gutter_x, callout_y + marker_size // 2)
        draw.line([anchor_box, anchor_callout], fill=color, width=2)

        draw.rectangle(
            [(gutter_x - marker_size - 4, callout_y), (gutter_x - 4, callout_y + marker_size)],
            fill=color,
        )
        draw.text(
            (
                gutter_x - marker_size - 4 + (marker_size - tw) / 2,
                callout_y + (marker_size - th) / 2 - 2,
            ),
            num,
            fill=(255, 255, 255),
            font=label_font,
        )

        for j, line in enumerate(_wrap(ann.label, max_chars=34)):
            draw.text(
                (gutter_x + 2, callout_y + j * (max(12, H // 75) + 2)),
                line,
                fill=(20, 20, 20),
                font=body_font,
            )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return out


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVu-Sans-Bold.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def _wrap(text: str, max_chars: int) -> list[str]:
    words = text.split()
    out: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for w in words:
        if cur_len + len(w) + 1 > max_chars and cur:
            out.append(" ".join(cur))
            cur = [w]
            cur_len = len(w)
        else:
            cur.append(w)
            cur_len += len(w) + 1
    if cur:
        out.append(" ".join(cur))
    return out


__all__ = ["render_annotated_figure", "render_debug_overlay"]
