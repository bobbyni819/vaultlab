---
title: Figure explainer generator
type: module-doc
module: vaultlab.figures.explain
---

# Figure explainer generator

Every embedded figure gets a plain-words explainer. A figure without its explainer is not done.

`vaultlab.figures.explain` generates the first deterministic seed from structured inputs:
`FigureContract`, `CoverageManifest`, and optional claim-ledger `Claim` records. The default path
does not call a model or the network. Callers may pass `refine_fn` to revise the seed later, but the
seed itself stays reproducible.

The explainer always has a one-breath lead followed by five sections:

1. What it is
2. How to read it
3. Method in plain words
4. What it means
5. Caveat

Voice discipline is hedged. Use phrasing such as "consistent with" or "compatible with"; do not use
the explainer to overstate what a figure can support.

Example:

```python
from vaultlab.figures.explain import explain_figure

explainer = explain_figure(contract=contract, coverage=coverage, claims=claims)
print(explainer.to_markdown())
```
