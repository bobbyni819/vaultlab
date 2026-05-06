# `vaultlab.figures.index` — cross-figure pattern recognition

Maintains a per-project `figure-index.json` so vaultlab can answer *"this figure pairs with..."* queries. Closes Phase 3 of the figure-stack-and-orchestrators roadmap.

## Public surface

```python
from vaultlab.figures.index import (
    update_figure_index,
    find_figure_pairs,
    load_figure_index,
)

# After rendering a figure, register it in the index:
update_figure_index(
    kb_root="G:/My Drive/Knowledge",
    project_slug="metabolism",
    figure_path="path/to/marker_dot_plot.png",
    source="own",                      # "own" or "paper"
    recipe_id="marker_dot_plot",       # if source=own
    related_claims=["LPI signaling driven by phospholipid abundance"],
    doi_or_data_source="lipid_xgboost_2026-04",
)

# Later, query for similar figures:
pairs = find_figure_pairs(
    figure_path="path/to/marker_dot_plot.png",
    kb_root="G:/My Drive/Knowledge",
    project_slug="metabolism",
    top_n=3,
)
# pairs is a list of {entry, similarity, reasoning} dicts
```

## What's in the index

`<kb>/<project>/figure-index.json` — one JSON file per project, list of entries:

```json
[
  {
    "path_hash": "ab12cd34ef56",
    "figure_path": "/abs/path/to/figure.png",
    "source": "own",
    "recipe_id": "marker_dot_plot",
    "pixel_signature": {
      "size_px": [1280, 960],
      "aspect": 1.333,
      "dominant_bins": [[5, 5, 5], [3, 7, 2], ...],
      "dominant_bin_counts": [12450, 8932, ...],
      "n_pixels_non_bg": 230451
    },
    "related_claims": ["..."],
    "doi_or_data_source": "10.1016/...",
    "registered_at": "2026-05-06T22:14:33",
    "extra_metadata": {}
  }
]
```

## Similarity metric

Cosine distance over dominant-color-bin vectors:

1. Quantize each figure's non-background pixels into 8x8x8 RGB bins (512 total possible bins)
2. Take the top-16 most-frequent bins as the figure's "color signature"
3. Compute cosine similarity over the bin-frequency vectors

Plus a small bonus (`same_recipe_bonus=0.10`) when both figures share the same `recipe_id`. Plus a "same source" reasoning note when both reference the same DOI or dataset.

This is intentionally cheap — no embedding model, no GPU, no extra deps. Sub-second for typical figure-index sizes (<1000 entries).

## When to call

- **`update_figure_index()`** — every time a figure is rendered or ingested. Recipes can opt-in; the figure-acquisition pipeline (paper figures) should call automatically.
- **`find_figure_pairs()`** — when the user asks *"what else does this figure connect to"* OR after each new figure render to surface 1-2 *"this pairs with..."* hints.

## Integration with `/find-analogs`

`/find-analogs` (the cross-PROJECT pattern recognition slash command) should query each project's figure-index in addition to its concept-doc set, so figures contribute to the structural-analog matches. This makes the figure-index a building block of the broader cross-project intelligence pillar (CLAUDE.md commitment #6).

## Lineage

| Pattern | Source |
|---|---|
| Hover-to-see-quote citation UX adapted for figures | NotebookLM (Google) |
| Wiki-style cross-linking via `[[wikilinks]]` | Karpathy LLM Wiki + Obsidian |
| Pixel-signature similarity (cosine over color-motif vectors) | scanpy clustering primitives + standard sklearn |

## Tests (recommended coverage)

- Round-trip: write entry → load index → entry present
- Idempotent: write same path twice → still one entry, updated `registered_at`
- Similarity: render two near-identical scatters → high similarity; one scatter + one heatmap → low similarity
- Recipe bonus: two scatter plots with same recipe_id rank above two with different recipe_ids
- Empty index: `find_figure_pairs` returns empty list cleanly
