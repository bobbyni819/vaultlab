---
name: palantir
description: Cell-fate trajectory inference + pseudotime for differentiation studies. Runs on AnnData.
domains: [single-cell, trajectory, pseudotime, differentiation]
install: pip install palantir
docs_url: https://github.com/dpeerlab/Palantir
---

# Palantir


## Summary

Branching-trajectory inference (Setty 2019, *Nat. Biotech.*). For differentiation hierarchies with multiple terminal states (hematopoiesis, neurogenesis). Outputs pseudotime + per-cell branch probabilities + branching entropy (high entropy = bipotent state). Requires manual `early_cell` argument. For non-branching trajectories, `scanpy.tl.dpt` is cheaper.

Setty 2019 (Nat. Biotech). Trajectory inference for branching differentiation hierarchies. Better than diffusion-pseudotime alone when there are multiple terminal states.

## When to use

- Single-cell trajectory inference with branching (>1 terminal state)
- Quantifying cell-fate probabilities at intermediate states
- Multipotent → committed lineage analyses (hematopoiesis, neurogenesis, etc.)

## Key functions

```python
import palantir
# Step 1: diffusion components
dm_res = palantir.utils.run_diffusion_maps(adata.obsm['X_pca'])
ms_data = palantir.utils.determine_multiscale_space(dm_res)

# Step 2: pick an early cell
early_cell = adata.obs.index[some_HSC_cell_idx]

# Step 3: run Palantir
pr_res = palantir.core.run_palantir(
    ms_data, early_cell,
    terminal_states=['terminal_idx_1', 'terminal_idx_2'],
)
adata.obs['palantir_pseudotime'] = pr_res.pseudotime
adata.obs['palantir_entropy'] = pr_res.entropy  # branching entropy
```

## Use-case examples

1. **Hematopoietic differentiation:** identify HSC cell as early; pass GMP / MEP / lymphoid as terminal candidates; Palantir estimates pseudotime + per-cell branch probabilities.
2. **Neurogenesis trajectory:** stem cell as early; mature neuron + astrocyte as terminals.

## Notes for the LLM

- Requires a `early_cell` argument — must be picked manually (no automatic root-cell inference).
- Branching entropy = uncertainty about which terminal a cell belongs to. High entropy = bipotent / multipotent state.
- For non-branching trajectories, simpler methods (`scanpy.tl.dpt`) are cheaper.
