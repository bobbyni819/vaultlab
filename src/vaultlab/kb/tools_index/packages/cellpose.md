---
name: cellpose
description: Generalist cell + nucleus segmentation via deep learning. Pretrained models for fluorescence, brightfield, H&E.
domains: [segmentation, imaging, microscopy, single-cell-imaging]
install: pip install cellpose
docs_url: https://cellpose.readthedocs.io
---

# Cellpose


## Summary

Generalist deep-learning cell + nucleus segmentation (Stringer & Pachitariu, *Nat. Methods* 2021). Pretrained models (`cyto3`, `nuclei`, `tissuenet_cp3`, `livecell_cp3`) work zero-shot on most fluorescence / brightfield / H&E microscopy. GPU recommended; output is per-cell integer mask.

Stringer & Pachitariu (Nat. Methods 2021). Pretrained generalist segmentation that works out-of-the-box on most microscopy modalities.

## When to use

- Cell or nucleus segmentation in fluorescence microscopy
- Brightfield / H&E segmentation
- When U-Net training data is unavailable (Cellpose's pretrained `cyto3` / `nuclei` models work zero-shot)

## Key functions

- `from cellpose import models`
- `model = models.Cellpose(model_type='cyto3', gpu=True)` — load model (`'cyto3'`, `'nuclei'`, `'tissuenet_cp3'`, `'livecell_cp3'`)
- `masks, flows, styles, diams = model.eval(image, diameter=None, channels=[0, 0])` — segment
  - `channels=[0, 0]` — grayscale; `[2, 1]` — green/red channels
  - `diameter=None` — auto-estimate; or pass an integer (faster)

## Use-case examples

1. **CODEX nuclear segmentation:** stack DAPI channel → `model_type='nuclei'` → outputs per-cell mask.
2. **Brightfield cell segmentation:** `cyto3` model directly on uint16 brightfield.
3. **Custom training:** `cellpose train` if pretrained doesn't fit; `human-in-the-loop` GUI available via `python -m cellpose`.

## Notes for the LLM

- GPU is recommended (`gpu=True`); CPU works but slow.
- Output `masks` is `int` array same shape as input, with per-cell label values (0 = background).
- `diameter` matters: too small → over-segmentation; too large → merged cells.
