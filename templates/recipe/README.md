# Template: figure recipe

To add a new figure recipe to vaultlab:

1. Copy this directory to `src/vaultlab/figures/recipes/<recipe_name>/`
2. Fill in `<recipe_name>.py` (the renderer) and `<recipe_name>.md` (description + ≥3 paper references)
3. Add corpus entry to `vaultlab.figures.corpus/sources.json`
4. Add a unit test in `tests/test_vaultlab_figures/`
5. Run `vaultlab claude validate` and `pytest tests/test_vaultlab_figures/`

> **Status:** template scaffold. Files will be added in migration commits.

## Required files in each recipe

```
<recipe_name>/
  <recipe_name>.py            # Recipe class + render()
  <recipe_name>.md            # Description, when to use, references
```

## Required `.md` content

```markdown
---
recipe_name: <name>
data_signature: <e.g., "DataFrame[float] of shape (N, M); rows=cells, cols=genes">
typical_use: <one-line description>
references_required: 3
---

# <Human-readable name>

## When to use

(2-3 sentences)

## Data shape

(specific input shape)

## References (≥3 required)

1. <DOI / repo link / panel ID>: <one-line context>
2. <DOI / repo link / panel ID>: <one-line context>
3. <DOI / repo link / panel ID>: <one-line context>

## Knobs

- `palette` (default: "RdBu_r"): ...
- `figsize` (default: "auto"): ...

## Gotchas

(any failure modes to call out)
```

Recipes without 3+ references fail review (per AGENTS.md).
