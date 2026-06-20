---
title: Read-the-PNG visual QA
type: figure-understanding
---

# Read-the-PNG visual QA

`visual_qa_figure()` is the post-render check for a PNG that a reviewer will
actually see. It always runs the deterministic `run_layout_audit()` checks first:
cutoff detection, DPI, empty-panel detection, palette accessibility, aspect ratio,
and the existing layout heuristics.

When `run_vision=False` (the default), the pass is fully deterministic and CI-safe:
no model, network, SDK client, or API key is touched.

When `run_vision=True`, the pass adds an advisory vision readback using the existing
figure-understanding SDK verify path. The vision prompt asks the figure-reader role
to flag reviewer-visible issues that rcParams and layout heuristics may miss, such as
tiny labels, overlapping text, stale labels, cropped content, confusing legends, or a
PNG that does not support the supplied `conclusion`.

If the Anthropic SDK or API key is unavailable, the vision leg is skipped gracefully.
The deterministic layout audit still runs and the result records a pass-severity
finding saying that vision QA was skipped. Vision QA is advisory; it complements the
publication bundle's existing layout audit rather than replacing deterministic checks
or human review.

Sidecars are written next to the PNG by default:

- `<png>.visual_qa.json`
- `<png>.visual_qa.md`

Use `write_sidecar=False` for in-memory tests or callers that manage their own
artifact storage.
