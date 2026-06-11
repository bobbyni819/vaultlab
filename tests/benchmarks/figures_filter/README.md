# figures.py quality-filter sweep

Characterizes `research/figures.py`'s image quality filter (the `min_dimension` /
`min_bytes` keep-drop predicate) against PMC JATS ground truth, and reports
precision/recall/F1 across a 2-D threshold grid. It **measures** the existing filter
— it does not change `figures.py`.

## What's here

| file | role |
|---|---|
| `labeling.py` | JATS labeler — discover articles, parse `<fig>//<graphic>` hrefs, label package images positive/negative, read (min_dim, bytes) |
| `run_sweep.py` | sweep runner — labels a corpus, sweeps the grid, writes `filter_sweep_report.md` |
| `test_labeling.py` | proves the href→file labeling on a synthetic fixture (positive / negative / unmatched) |
| `filter_sweep_report.md` | generated report (grid + default cell + best-F1 + skip accounting) |

## Ground truth (deterministic, no human labeling)

For each PMC OA package the article `.nxml` is the oracle:
- **positive** — an image file whose stem matches an `xlink:href` of a `<graphic>`
  inside a `<fig>` (a real figure graphic).
- **negative** — any other image file in the package (logos, `<disp-formula>` /
  `<inline-graphic>` equation graphics, icons — the junk the filter targets).
- **unmatched** — a `<fig>` graphic href with no on-disk file (or matching >1 file).
  Counted and reported; never assigned to positive/negative or to P/R.

**href→file rule:** `stem_H = basename(href) minus a trailing image extension`;
file `F` matches iff `F.stem.lower() == stem_H.lower()` (exactly one match → positive).

## Filter & metrics

The faithful predicate (figures.py lines 106 & 116): `keep ⟺ min(w,h) ≥ min_dimension
AND size_bytes ≥ min_bytes`. Defaults are **imported** from `figures.py`
(`_DEFAULT_MIN_DIM=200`, `_DEFAULT_MIN_BYTES=5000`) to mark that cell — not hardcoded.

`size_bytes` is the **PNG-re-encoded** size of each image, not its raw file size:
figures.py saves each raster as PNG and stats that, so its `min_bytes` default is
calibrated against PNG sizes (a JPG on disk is much smaller than its PNG re-encoding).
The harness assumes the canonical **flat** PMC OA package layout (one folder per
article, `.nxml` + images directly inside — no nested image subfolders).

Pooled across the corpus: kept positive = TP, kept negative = FP, dropped positive =
FN. `precision = TP/(TP+FP)`, `recall = TP/(TP+FN)`, `F1 = 2PR/(P+R)`.

Grid: `min_dim ∈ {0,100,150,200,250,300,400}` × `min_bytes ∈ {0,1000,2500,5000,10000,25000,50000}`.

## Corpus contract

`--corpus-dir` points at a folder of PMC OA packages — one subfolder per article,
each containing a `.nxml` plus its bundled image files. The dir is **gitignored**
(don't commit papers). Empty/absent corpus → a clear "point me at the PMC corpus dir"
message and exit 1 (no stack trace).

## Run

```bash
# label + sweep a real corpus
/opt/anaconda3/bin/python tests/benchmarks/figures_filter/run_sweep.py --corpus-dir /path/to/pmc_oa
# verify the labeler
/opt/anaconda3/bin/python -m pytest tests/benchmarks/figures_filter/ -m "not llm"
```

## Note on the committed report

The checked-in `filter_sweep_report.md` was produced from a **synthetic 3-article
smoke corpus** (no real PMC corpus was supplied), purely to exercise the harness
end-to-end — its "best operating point" is an artifact of the synthetic fixture, not
a real verdict about the defaults. Drop a real PMC OA corpus at `--corpus-dir` and
re-run for the real precision/recall.

Security: `.nxml` parsing prefers `defusedxml` when present (blocks XXE /
billion-laughs), falling back to stdlib `xml.etree` — no new hard dependency.
