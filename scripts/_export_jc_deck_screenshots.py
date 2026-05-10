"""Export the Pentimalli JC deck as static PNGs + a cycling GIF for the README.

Uses PowerPoint COM (win32com) to render each slide as PNG, then PIL to
combine into an animated GIF (1.2 s per frame, looping). Also emits 4
static screenshot files for inline embedding.

Run from the vaultlab repo root. Output goes to docs/screenshots/.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

SRC_PPTX = Path(
    "G:/My Drive/Knowledge/vaultlab/Output/Decks/"
    "journal-club-pentimalli-2026-05-05/"
    "journal-club-pentimalli-2026-05-05.pptx"
)
TEMP_PPTX = Path("C:/temp/_jc_pentimalli_export.pptx")
OUT_DIR = Path("docs/screenshots")
GIF_PATH = OUT_DIR / "journal-club-pentimalli-cycle.gif"
WIDTH_PX = 1280
HEIGHT_PX = 720
GIF_FRAME_MS = 1200
GIF_TARGET_WIDTH = 960  # downscale for GIF size


def export_slides_via_powerpoint() -> list[Path]:
    """Drive PowerPoint via COM to export each slide as PNG."""
    import pythoncom
    import win32com.client

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_PPTX.parent.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] Copying {SRC_PPTX.name} to temp (avoid file lock)...")
    shutil.copy(SRC_PPTX, TEMP_PPTX)

    pythoncom.CoInitialize()
    ppt = win32com.client.Dispatch("PowerPoint.Application")
    # PowerPoint COM requires Visible for some Slide.Export calls
    ppt.Visible = 1

    print(f"[2/3] Opening + exporting slides...")
    pres = ppt.Presentations.Open(str(TEMP_PPTX), WithWindow=False)

    paths: list[Path] = []
    for i, slide in enumerate(pres.Slides, start=1):
        out_png = OUT_DIR / f"slide_{i:02d}.png"
        slide.Export(str(out_png.absolute()), "PNG", WIDTH_PX, HEIGHT_PX)
        paths.append(out_png)
        print(f"     slide {i:02d} -> {out_png}")

    pres.Close()
    ppt.Quit()
    pythoncom.CoUninitialize()
    return paths


def build_gif(png_paths: list[Path]) -> Path:
    """Combine PNGs into an animated GIF."""
    from PIL import Image

    print(f"[3/3] Building GIF ({len(png_paths)} frames, {GIF_FRAME_MS}ms each)...")
    frames: list[Image.Image] = []
    for p in png_paths:
        img = Image.open(p).convert("RGB")
        ratio = GIF_TARGET_WIDTH / img.width
        new_h = int(img.height * ratio)
        img = img.resize((GIF_TARGET_WIDTH, new_h), Image.LANCZOS)
        frames.append(img)

    frames[0].save(
        GIF_PATH,
        save_all=True,
        append_images=frames[1:],
        duration=GIF_FRAME_MS,
        loop=0,
        optimize=True,
    )
    size_mb = GIF_PATH.stat().st_size / (1024 * 1024)
    print(f"     {GIF_PATH}  ({size_mb:.1f} MB)")
    return GIF_PATH


def main() -> int:
    if not SRC_PPTX.exists():
        print(f"ERROR: source pptx not found: {SRC_PPTX}", file=sys.stderr)
        return 1
    paths = export_slides_via_powerpoint()
    build_gif(paths)
    print(f"\nDone. Static PNGs: {len(paths)}; GIF: {GIF_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
