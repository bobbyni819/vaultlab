---
recipe_name: <recipe_name>
data_signature: "<e.g. DataFrame[float] (N rows = cells, M cols = markers)>"
typical_use: "<one-line description of the question this figure answers>"
references_required: 3
---

# <Human-readable name>

## When to use

(2-3 sentences — what scientific question this figure archetype answers, and
when to reach for it over the other recipes.)

## Data shape

(Specific input shape — column names, dtypes, index. Match the `render()`
docstring exactly so a caller can build valid input without reading the code.)

## References (≥3 required)

These are the published figures whose layout this recipe reproduces — the reason
the recipe is trustworthy rather than an AI guess. Keep this list in sync with
the `ANCHOR_PAPERS` tuple in the `.py` (the meta-test enforces ≥3).

1. <DOI / panel ID>: <one-line context>
2. <DOI / panel ID>: <one-line context>
3. <DOI / panel ID>: <one-line context>

## Knobs

- `variant` (default: ...): ...
- `palette` (default: ...): ...

## Status

🚧 **Scaffold — replace this whole file.** Flip to "✅ Implemented (v0.1.0)" once
`render()` produces a real figure and a smoke test in
`tests/test_vaultlab_figures/test_recipe_smoke.py` covers it.

## Gotchas

(Any failure modes / surprising input requirements to call out.)
