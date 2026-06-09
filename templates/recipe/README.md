# Template: figure recipe

Recipes are **flat file pairs** in `src/vaultlab/figures/recipes/` —
`<recipe_name>.py` + `<recipe_name>.md`, not subdirectories.

To add a new figure recipe to vaultlab:

1. Create `src/vaultlab/figures/recipes/<recipe_name>.py` (the renderer) and
   `<recipe_name>.md` (description + ≥3 paper references)
2. Register `<recipe_name>` in `src/vaultlab/figures/recipes/__init__.py`
3. Add a unit test in `tests/test_vaultlab_figures/`
4. Run `vaultlab claude validate` and `pytest tests/test_vaultlab_figures/`

> **Status:** template scaffold — the scaffold files themselves are not yet
> written (see `NEXT_STEPS.md`). The `corpus/sources.json` registry referenced
> in older docs is also not yet built; until it exists, anchor papers live in
> the recipe's `ANCHOR_PAPERS` tuple and its `.md` file.

## Required files for each recipe

```
recipes/
  <recipe_name>.py            # render() function + RECIPE_VERSION + ANCHOR_PAPERS
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

Recipes are expected to cite ≥3 references (per AGENTS.md). Note: this is a
manual review expectation — there is no automated check counting references
yet (see `NEXT_STEPS.md`).
