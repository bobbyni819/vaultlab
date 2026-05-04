"""Render image10 with v9 annotations as a preview PNG.

Paints rectangles or ellipses (per bbox_shape) onto the source image so the
multimodal Read tool can verify the placements before shipping the PPTX.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image, ImageDraw, ImageFont

from build_native_annotated_demo import (  # type: ignore[import-not-found]
    IMAGE10,
    IMAGE10_ANNOTATIONS,
    IMAGE10_COLORS,
    auto_offset_annotations,
)

OUT = Path(r"C:\tmp\cart_figs_v13_annotated_v2\image10_v9_preview.png")


def main() -> None:
    img = Image.open(IMAGE10).convert("RGB")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 50)
    except OSError:
        font = ImageFont.load_default()

    anns = auto_offset_annotations(IMAGE10, IMAGE10_ANNOTATIONS)
    for i, ann in enumerate(anns, start=1):
        color = IMAGE10_COLORS.get(ann.motif_name, (200, 0, 0))
        x0, y0, x1, y1 = ann.bbox_px
        if ann.bbox_padding_px == 0:
            pad = 0
        else:
            pad = 30  # match layout default for preview parity
        bx0, by0, bx1, by1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
        if ann.use_box:
            if ann.bbox_shape == "circle":
                draw.ellipse([bx0, by0, bx1, by1], outline=color, width=8)
            else:
                draw.rectangle([bx0, by0, bx1, by1], outline=color, width=8)

        # Marker
        if ann.marker_offset_px is not None:
            mx0 = x0 + ann.marker_offset_px[0]
            my0 = y0 + ann.marker_offset_px[1]
        else:
            mx0 = x0
            my0 = max(0, y0 - 90)
        msize = 90

        # Leader line if marker is far from bbox center (mirror renderer logic)
        bcx = (bx0 + bx1) // 2
        bcy = (by0 + by1) // 2
        mcx = mx0 + msize // 2
        mcy = my0 + msize // 2
        far_threshold = int(0.15 * img.width)
        if abs(mcx - bcx) > far_threshold or abs(mcy - bcy) > far_threshold:
            # pick bbox edge midpoint nearest the marker
            if abs(mcx - bcx) > abs(mcy - bcy):
                anchor_x = bx1 if mcx > bcx else bx0
                anchor_y = bcy
            else:
                anchor_x = bcx
                anchor_y = by1 if mcy > bcy else by0
            draw.line([(anchor_x, anchor_y), (mcx, mcy)], fill=color, width=4)

        draw.rectangle([mx0, my0, mx0 + msize, my0 + msize], fill=color, outline=(255, 255, 255), width=4)
        # number text
        text = str(i)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(
            (mx0 + (msize - tw) / 2 - bbox[0], my0 + (msize - th) / 2 - bbox[1]),
            text,
            fill=(255, 255, 255),
            font=font,
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG")
    print(f"Wrote -> {OUT}")


if __name__ == "__main__":
    main()
