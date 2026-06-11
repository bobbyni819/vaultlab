# figures.py quality-filter sweep — precision/recall vs PMC/JATS ground truth

- **Corpus:** `/tmp/figfilter_smoke_corpus` — 3 articles
- **Note:** SMOKE (synthetic 3-article corpus) — no real PMC corpus supplied; drop real OA packages at --corpus-dir and re-run for the real verdict.
- **Filter characterized:** `research/figures.py` `extract_figures` inline predicate (lines 106 & 116), unchanged. `keep ⟺ min(w,h) ≥ min_dimension AND size_bytes ≥ min_bytes`.
- **Current default (imported from figures.py):** min_dimension=200, min_bytes=5000
- **Ground truth:** positive = image file matching a `<fig>//<graphic>` xlink:href; negative = any other package image. **P/R:** kept positive=TP, kept negative=FP, dropped positive=FN.

## Headline

- **Current default (200, 5000):** precision **0.500**, recall **0.500**, F1 **0.500** (TP=2, FP=2, FN=2)
- **Best F1 (100, 0):** precision **0.667**, recall **1.000**, F1 **0.800** (TP=4, FP=2, FN=0)
- ΔF1 vs default: **+0.300** (ΔP +0.167, ΔR +0.500). 6 cell(s) share the best F1.
- Label population: **4** positives, **5** negatives.

## F1 grid (rows = min_dim px, cols = min_bytes; `(def)` = default, `*` = best F1)

| min_dim \ min_bytes | 0 | 1000 | 2500 | 5000 | 10000 | 25000 | 50000 |
|---|---|---|---|---|---|---|---|
| **0** | 0.615 | 0.615 | 0.615 | 0.500 | 0.500 | 0.600 | 0.600 |
| **100** | 0.800* | 0.800 | 0.800 | 0.667 | 0.667 | 0.667 | 0.667 |
| **150** | 0.800 | 0.800 | 0.800 | 0.667 | 0.667 | 0.667 | 0.667 |
| **200** | 0.667 | 0.667 | 0.667 | 0.500 (def) | 0.500 | 0.500 | 0.500 |
| **250** | 0.667 | 0.667 | 0.667 | 0.500 | 0.500 | 0.500 | 0.500 |
| **300** | 0.667 | 0.667 | 0.667 | 0.500 | 0.500 | 0.500 | 0.500 |
| **400** | 0.667 | 0.667 | 0.667 | 0.500 | 0.500 | 0.500 | 0.500 |

## Precision grid

| min_dim \ min_bytes | 0 | 1000 | 2500 | 5000 | 10000 | 25000 | 50000 |
|---|---|---|---|---|---|---|---|
| **0** | 0.444 | 0.444 | 0.444 | 0.375 | 0.375 | 0.500 | 0.500 |
| **100** | 0.667* | 0.667 | 0.667 | 0.600 | 0.600 | 0.600 | 0.600 |
| **150** | 0.667 | 0.667 | 0.667 | 0.600 | 0.600 | 0.600 | 0.600 |
| **200** | 0.600 | 0.600 | 0.600 | 0.500 (def) | 0.500 | 0.500 | 0.500 |
| **250** | 0.600 | 0.600 | 0.600 | 0.500 | 0.500 | 0.500 | 0.500 |
| **300** | 0.600 | 0.600 | 0.600 | 0.500 | 0.500 | 0.500 | 0.500 |
| **400** | 0.600 | 0.600 | 0.600 | 0.500 | 0.500 | 0.500 | 0.500 |

## Recall grid

| min_dim \ min_bytes | 0 | 1000 | 2500 | 5000 | 10000 | 25000 | 50000 |
|---|---|---|---|---|---|---|---|
| **0** | 1.000 | 1.000 | 1.000 | 0.750 | 0.750 | 0.750 | 0.750 |
| **100** | 1.000* | 1.000 | 1.000 | 0.750 | 0.750 | 0.750 | 0.750 |
| **150** | 1.000 | 1.000 | 1.000 | 0.750 | 0.750 | 0.750 | 0.750 |
| **200** | 0.750 | 0.750 | 0.750 | 0.500 (def) | 0.500 | 0.500 | 0.500 |
| **250** | 0.750 | 0.750 | 0.750 | 0.500 | 0.500 | 0.500 | 0.500 |
| **300** | 0.750 | 0.750 | 0.750 | 0.500 | 0.500 | 0.500 | 0.500 |
| **400** | 0.750 | 0.750 | 0.750 | 0.500 | 0.500 | 0.500 | 0.500 |

## Corpus accounting (nothing dropped silently)

- articles total: **3**
- articles with no `.nxml`: **1**
- articles with unparseable `.nxml`: **0**
- articles with zero candidate images: **0**
- articles with fig hrefs but zero mapped to files: **0**
- `<fig>` graphic hrefs total: **5**
- unmatched hrefs (declared figure, no on-disk file — excluded from P/R): **1**
- ambiguous hrefs (matched >1 file — excluded from P/R): **0**
- candidate image files total: **10**
- images unreadable by Pillow (excluded from P/R): **1**

