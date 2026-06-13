# Template: figure recipe

Recipes are **flat file pairs** in `src/vaultlab/figures/recipes/` —
`<recipe_name>.py` + `<recipe_name>.md`, not subdirectories.

To add a new figure recipe to vaultlab:

1. Copy this folder's `_recipe_name.py` + `_recipe_name.md` scaffolds to
   `src/vaultlab/figures/recipes/<recipe_name>.{py,md}` and fill them in
   (renderer + description + ≥3 real paper references).
2. Register `<recipe_name>` in `src/vaultlab/figures/recipes/__init__.py`
3. Add a smoke-render builder in
   `tests/test_vaultlab_figures/test_recipe_smoke.py` (the invariant + smoke
   meta-tests then cover the new recipe automatically).
4. Regenerate the corpus index:
   `python -c "from vaultlab.figures.corpus import save_sources_index; save_sources_index()"`
5. Run `vaultlab claude validate` and `pytest tests/test_vaultlab_figures/`

> **Status:** scaffold files are ready to copy — `_recipe_name.py` and
> `_recipe_name.md` in this folder. The `corpus/sources.json` index is built
> (`vaultlab.figures.corpus`); it is *derived* from each recipe's
> `ANCHOR_PAPERS` tuple (the source of truth) and guarded by a staleness test.

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

Recipes must cite ≥3 references (per AGENTS.md). This is now ENFORCED:
`tests/test_vaultlab_figures/test_recipe_invariants.py` fails the build if any
recipe's `ANCHOR_PAPERS` tuple has fewer than 3 entries.
