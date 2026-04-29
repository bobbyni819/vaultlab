---
name: pyimzML
description: Read MALDI imaging mass-spectrometry imzML files. The Python entry point for MALDI-MSI data.
domains: [maldi, mass-spectrometry, imaging, spatial-omics]
install: pip install pyimzml
docs_url: https://github.com/alexandrovteam/pyimzML
---

# pyimzML


## Summary

Reader for MALDI mass-spectrometry imzML files. Iterates spectra by spatial coordinate; builds 2D ion images for given m/z ± tolerance. Two flavors: continuous (shared m/z axis) vs processed (per-pixel axis); `p.continuous` flag tells which. Bridge to scanpy / squidpy by binning spectra to a fixed m/z grid and stacking into AnnData.

Reader for the imzML community standard. Most MALDI vendor software exports imzML — this is how Python sees the data.

## When to use

- Load MALDI-MSI datasets exported from Bruker / Thermo / Waters / etc.
- Iterate spectra by spatial coordinate (x, y, z)
- Build ion-image arrays for downstream visualization

## Key functions

```python
from pyimzml.ImzMLParser import ImzMLParser, getionimage
p = ImzMLParser("path/to/file.imzML")
n_pixels = len(p.coordinates)             # (x, y, z) tuples per pixel
mzs, intensities = p.getspectrum(idx=0)   # one pixel's spectrum
img = getionimage(p, mz_value=400.5, tol=0.01)  # 2D ion image at m/z ± tol
```

## Use-case examples

1. **Single ion image at a target m/z:** `getionimage(p, target_mz, tol)` returns a 2D numpy array; `imshow` to visualize.
2. **Build a (n_pixels × n_features) intensity matrix:** loop `getspectrum`, bin to a fixed m/z axis, stack rows. Then load into AnnData for squidpy / scanpy-compatible downstream analyses.
3. **Coregister with H&E:** combine ion image with `skimage.registration` or manual landmark-based affine transform.

## Notes for the LLM

- imzML files come in two flavors: "continuous" (single shared m/z axis) and "processed" (per-pixel m/z axes). `p.continuous` flag tells which.
- Spectra are typically large + sparse; binning to a fixed grid (e.g. 0.01 Da) is usually the first step.
- For peak-picking / preprocessing, R's `Cardinal` is more mature; bridge via `rpy2` if needed.
