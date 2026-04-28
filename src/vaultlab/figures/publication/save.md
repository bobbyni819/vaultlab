---
module: vaultlab.figures.publication.save
purpose: Multi-format figure save (PNG + PDF) with sane publication defaults
---

# Save — multi-format figure export

## What this provides

`save_fig(fig, out_path, formats=("png", "pdf"), dpi=300)` — saves a matplotlib figure in multiple formats with publication-ready defaults (300 DPI, white background, tight bounding box).

## What this deliberately does NOT do

- **No provenance writing.** That's `vaultlab.provenance.write_provenance()` (called separately by recipes). Keeping these concerns split lets `save_fig()` be cheap to call from quick analyses without enforcing the full provenance contract.
- **No filename munging.** The caller passes the output path without extension; this module just writes `{path}.{fmt}`. Naming conventions (versioning, timestamps) live in the recipe layer.

## Convention for recipes

Every recipe's `render()` function pairs `save_fig()` with `write_provenance()`:

```python
from vaultlab.figures.publication import save_fig
from vaultlab.provenance import write_provenance

paths = save_fig(fig, out_path)
write_provenance(
    paths[0],                    # main output (PNG)
    inputs=[input_csv_path],
    params=render_params,
    code_called=["recipes.balloon_marker_genes.render"],
)
```

This produces the full output bundle:

```
out_path.png                     # the figure (raster)
out_path.pdf                     # the figure (vector, embeddable)
out_path.png.provenance.json     # machine-readable receipt
out_path.method.md               # human-readable narrative for paper methods
```

## Format guidance

- **PNG + PDF** (default) — journal submissions; PDF for editing/embedding, PNG for browsers/Slack/Obsidian
- **PNG only** — quick previews; chat / DM sharing
- **PDF + SVG** — vector-only workflows; web rendering

## DPI guidance

- **300 DPI** — journal-acceptable for most venues
- **600 DPI** — camera-ready / cover candidate
- **150 DPI** — review-only previews (not for submission)

## See also

- `vaultlab.provenance` — reproducibility receipts
- [`style.md`](style.md) — figure size presets
