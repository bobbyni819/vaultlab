---
title: Recombination
type: concept
---

# Recombination

Recombination is a small deterministic operator: take the two best prior
artifacts, combine them into a child, then run the same verifier on the child.
It is inspired by empirical recombination results such as ERA, where some
combined hypotheses beat both parents, and by Co-Scientist-style evolution by
combination.

The rule is deliberately conservative: recombination proposes, verification
disposes. A child is not assumed better because it inherited pieces from strong
parents. It must pass the verifier supplied by the caller.

`vaultlab.recombine.recombine(...)` accepts two parents, a pure `combine_fn`,
an optional `verify_fn`, and an optional `accept_fn` for custom verdict logic.
Combine and verification exceptions are captured in `RecombineResult` instead
of crashing the caller, so iterative pipelines can keep their lineage and
failure rationale.

For figure planning, `recombine_figure_contracts(...)` demonstrates the
operator on `FigureContract`: evidence chains are unioned, parent B wins panel
key conflicts, the stronger conclusion is retained, notes are merged, and
stricter export commitments such as maximum DPI are carried forward.
