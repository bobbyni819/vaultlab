"""Color-motif extraction on a single figure — proof of concept.

Bobby's 2026-04-29 insight: BioRender figures use distinct neon colors
(e.g., introduced TCR is neon green; MHC class I is purple/maroon; CD3
is orange). We can find those regions PROGRAMMATICALLY by color
thresholding — much more precise than my eye-estimated coords.

This script:
1. Loads figure 1 (image1.png).
2. For each named color motif (neon green, magenta MHC peptide region,
   electric blue endogenous TCR), extracts pixel regions that match.
3. Runs connected-component labeling (scikit-image) to get bounding boxes.
4. Renders a debug image showing each detected region with its label.
5. Outputs the boxes as JSON so the LLM can pair them with concept names.

Output: cart_figs_v13_motif/figure1_motif_debug.png + figure1_motifs.json
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from skimage import color as skcolor
from skimage import measure, morphology

INPUT = Path(r"C:\tmp\cart_figs_v13\image1.png")
OUT_DIR = Path(r"C:\tmp\cart_figs_v13_motif")
OUT_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Color motifs — BioRender palette guesses for figure 1 elements.
# Hue ranges in [0, 360]; saturation/value in [0, 1].
# These were picked by reading the figure visually + standard BioRender colors.
# ---------------------------------------------------------------------------


@dataclass
class ColorMotif:
    name: str
    hue_range: tuple[float, float]   # in [0, 360]
    sat_min: float                   # in [0, 1]
    val_min: float                   # in [0, 1]
    min_area_frac: float             # min connected-component size as fraction of total pixels


MOTIFS: list[ColorMotif] = [
    ColorMotif("neon-green (introduced TCR / scFv accent)", (80, 140), 0.40, 0.40, 0.00003),
    ColorMotif("electric-blue (endogenous TCR)", (195, 240), 0.30, 0.35, 0.00003),
    ColorMotif("orange (CD3 chains)", (15, 40), 0.45, 0.45, 0.00003),
    ColorMotif("red-magenta (MHC peptide + TAA + tumor)", (340, 360), 0.35, 0.40, 0.00003),
    ColorMotif("purple-violet (MHC class I body)", (260, 295), 0.18, 0.28, 0.00003),
    ColorMotif("yellow-gold (CAR MHC-Independent label)", (45, 65), 0.40, 0.55, 0.00003),
]


def _load_hsv(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Return (rgb, hsv) arrays of shape (H, W, 3)."""
    rgb = np.asarray(Image.open(path).convert("RGB"))  # uint8 (H, W, 3)
    hsv = skcolor.rgb2hsv(rgb)  # float64 in [0,1]
    return rgb, hsv


def _mask_for_motif(hsv: np.ndarray, motif: ColorMotif) -> np.ndarray:
    h = hsv[..., 0] * 360.0
    s = hsv[..., 1]
    v = hsv[..., 2]
    lo, hi = motif.hue_range
    if lo <= hi:
        hue_match = (h >= lo) & (h <= hi)
    else:
        # wrap-around (e.g., red 350-10)
        hue_match = (h >= lo) | (h <= hi)
    return hue_match & (s >= motif.sat_min) & (v >= motif.val_min)


def _components_for_mask(mask: np.ndarray, min_area: int) -> list[dict]:
    """Connected-component analysis; return per-component metadata."""
    cleaned = morphology.binary_opening(mask, footprint=morphology.disk(2))
    cleaned = morphology.remove_small_objects(cleaned, min_size=min_area)
    labels = measure.label(cleaned, connectivity=2)
    comps = []
    for region in measure.regionprops(labels):
        y0, x0, y1, x1 = region.bbox
        comps.append(
            {
                "bbox_px": [int(x0), int(y0), int(x1), int(y1)],
                "area_px": int(region.area),
                "centroid_px": [int(region.centroid[1]), int(region.centroid[0])],
            }
        )
    return comps


def _font(size: int) -> ImageFont.FreeTypeFont:
    for c in [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf"]:
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


PALETTE = [
    (0, 153, 0),     # green
    (0, 102, 204),   # blue
    (220, 80, 0),    # orange
    (200, 30, 80),   # magenta
    (130, 60, 180),  # purple
    (200, 170, 0),   # gold
]


def main() -> None:
    rgb, hsv = _load_hsv(INPUT)
    H, W = rgb.shape[:2]
    total_px = H * W

    canvas = Image.fromarray(rgb).copy()
    draw = ImageDraw.Draw(canvas)
    label_font = _font(max(14, H // 50))

    results: dict = {"image": INPUT.name, "width": W, "height": H, "motifs": {}}

    for i, motif in enumerate(MOTIFS):
        color_rgb = PALETTE[i % len(PALETTE)]
        mask = _mask_for_motif(hsv, motif)
        min_area = max(20, int(total_px * motif.min_area_frac))
        comps = _components_for_mask(mask, min_area)
        results["motifs"][motif.name] = {
            "hue_range": list(motif.hue_range),
            "n_components": len(comps),
            "components": comps,
        }
        for j, comp in enumerate(comps):
            x0, y0, x1, y1 = comp["bbox_px"]
            draw.rectangle([(x0, y0), (x1, y1)], outline=color_rgb, width=3)
            draw.text(
                (x0 + 4, max(0, y0 - 22)),
                f"{motif.name.split(' ')[0]} #{j+1}",
                fill=color_rgb,
                font=label_font,
            )
        print(
            f"  {motif.name:<48s} -> {len(comps):3d} components "
            f"(hue {motif.hue_range[0]:.0f}-{motif.hue_range[1]:.0f}, "
            f"min area {min_area}px)"
        )

    out_img = OUT_DIR / "figure1_motif_debug.png"
    canvas.save(out_img)
    out_json = OUT_DIR / "figure1_motifs.json"
    out_json.write_text(json.dumps(results, indent=2))
    print(f"\n  debug image -> {out_img}")
    print(f"  bbox json   -> {out_json}")


if __name__ == "__main__":
    main()
