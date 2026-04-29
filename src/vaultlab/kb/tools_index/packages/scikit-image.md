---
name: scikit-image
description: Image processing in Python — segmentation, morphology, filtering, feature extraction. Workhorse for microscopy image analysis.
domains: [imaging, microscopy, segmentation, image-processing]
install: pip install scikit-image
docs_url: https://scikit-image.org
---

# scikit-image

General-purpose image processing. The default tool for non-deep-learning microscopy work.

## When to use

- Threshold-based segmentation (Otsu, adaptive)
- Morphological operations (open, close, dilate, erode)
- Filtering (Gaussian, median, edge-preserving)
- Region-property extraction (area, eccentricity, intensity per object)
- Distance transforms / watershed segmentation

## Key functions

- `skimage.io.imread(path)` — read TIFF/PNG/JPEG
- `skimage.filters.threshold_otsu(image)` — Otsu threshold
- `skimage.filters.gaussian(image, sigma=1)` — Gaussian smooth
- `skimage.morphology.binary_opening(mask, footprint)` — denoise mask
- `skimage.measure.label(mask)` — connected-component labeling
- `skimage.measure.regionprops_table(label, intensity_image, properties=...)` — per-object features
- `skimage.segmentation.watershed(elevation, markers)` — watershed
- `skimage.exposure.equalize_adapthist(image)` — CLAHE contrast enhancement
- `skimage.transform.resize(image, shape)` — resize/rescale

## Use-case examples

1. **Nuclear segmentation (light microscopy):** `gaussian` → `threshold_otsu` → `binary_opening` → `label` → `regionprops_table`.
2. **CODEX channel preprocessing:** background subtract, denoise, normalize before passing to Mesmer/Cellpose.
3. **Cell-feature extraction:** after segmentation, `regionprops_table(intensity_image=channel_X)` gives mean intensity per cell.

## Notes for the LLM

- Image dtype matters — most functions expect `float` in [0, 1] or `uint8`/`uint16`. Use `skimage.util.img_as_float()` to coerce.
- For 3D stacks, most functions accept the leading axis as Z; check the docstring for any function operating on multi-channel data.
