---
module: vaultlab.figures.publication.stamp
purpose: Embed CLI parameter values into figure filenames (Pattern 4)
status: minimal impl; full integration with recipes lands later
---

# Stamp — parameter-aware figure filenames

## What this provides

`parameter_stamp(base, **params)` — appends key=value pairs to a filename base so re-runs with different parameters don't overwrite each other.

## Examples

```python
parameter_stamp(base="cluster_umap", K=8, resolution=0.6)
# → "cluster_umap_K8_res0.6"

parameter_stamp(base="heatmap")
# → "heatmap"  (no params; no suffix)
```

## Convention

Recipes that take a `--K` (or similar) parameter use `parameter_stamp()` to construct the output filename:

```python
out_path = output_dir / parameter_stamp(base="cluster_umap", K=K)
save_fig(fig, out_path)
```

This ensures `cluster_umap_K8.png` and `cluster_umap_K12.png` coexist without collision.

## Pattern 4

From `metabolism-patterns-to-lift-2026-04-22.md`:

> Every figure-generating script accepts a primary tunable parameter (`--K`,
> `--resolution`, `--threshold`) and embeds the value in the output filename.
> Re-runs with different values produce side-by-side comparable outputs.

## See also

- File 06 in the grill — publication helpers (P0.1)
- `vaultlab.figures.recipes` — where parameter conventions land
