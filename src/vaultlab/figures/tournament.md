---
title: Figure alternative tournament
type: figure-workflow
---

# Figure alternative tournament

`run_figure_tournament()` pairwise-ranks alternative rendered figures so a
workflow can prioritize which variant deserves the next review pass. The
winner is a priority signal, not truth: it does not prove that the figure is
scientifically correct, publication-ready, or faithful to the underlying data.
The selected figure still needs data validation, visual QA, contract review,
and human judgment.

By default, the tournament is deterministic and model-free. Each candidate is
scored from its PNG with `run_layout_audit()`:

- `pass` -> `1.0`
- `warn` -> `0.5`
- `fail` or any unknown severity -> `0.0`

If a candidate has no PNG, or the PNG is missing or cannot be audited, the
scorer falls back to `score_hint` when supplied, otherwise `0.0`. This keeps
the tournament safe for draft galleries where not every candidate has a
rendered file yet.

Callers can inject `score_fn` to supply deterministic project-specific quality
numbers, or `judge_fn` to perform direct pairwise decisions. A judge may return
a full `Match`, a winner candidate id, or `None` for a tie. Judge exceptions
become tie matches with a rationale recording the failure, so a single bad
comparison does not abort the whole tournament.

Aggregation is win-count based: win = 1, tie = 0.5. Ties in the ranking are
broken deterministically by mean match margin and then candidate id. Every
pairwise `Match` is retained with winner, margin, rationale, and judge label so
the ranking can be audited rather than accepted blindly.
