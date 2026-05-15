# task_weight — route LLM calls to the right model tier

`vaultlab.workflows.task_weight` is the dispatcher that maps an LLM task to
a model tier (`light` / `medium` / `heavy`). Cost-conscious users get
mechanical work on cheap fast models (Haiku) and reserve premium models
(Opus) for the work that actually needs them.

## When to use

Wrap any LLM-calling entrypoint that wants to be cost-aware:

```python
from vaultlab.workflows.task_weight import TaskSpec, classify, model_for_task

spec = TaskSpec(kind="summarize", n_inputs=1)
weight = classify(spec)        # "medium"
model_id = model_for_task(spec)  # "claude-sonnet-4-6"
```

The returned `model_id` is a plain string — pass it to whatever Anthropic
SDK call you wire on the inside. The dispatcher itself does not call any
model.

## Weights

| Weight   | Default model         | Use for                                                    |
|----------|-----------------------|------------------------------------------------------------|
| `light`  | `claude-haiku-4-5`    | format conversion, extraction, simple rendering            |
| `medium` | `claude-sonnet-4-6`   | single-paper summarization, balanced work                  |
| `heavy`  | `claude-opus-4-7`     | cross-paper synthesis, manuscript polish, response letters |

## Task-kind matrix

| `kind`                  | n_inputs == 1 | n_inputs > 5 | requires_synthesis |
|-------------------------|---------------|--------------|---------------------|
| `extract` / `convert` / `format` / `render` | `light`  | `light`  | `heavy` |
| `summarize` / `single_paper_read` / `abstract_only` | `medium` | `heavy` | `heavy` |
| `polish` / `respond` / `manuscript_draft` / `deep_think` / `synthesize` / `synthesis` | `heavy`  | `heavy`  | `heavy` |
| Unknown kind            | `medium`      | `heavy`      | `heavy`             |

Decision order (see `classify()`):

1. `requires_synthesis=True` always upgrades to `heavy`.
2. Heavy-kind always → `heavy`.
3. Light-kind always → `light`.
4. `n_inputs > 5` upgrades anything else to `heavy`.
5. Medium-kind with `n_inputs == 1` → `medium`.
6. Otherwise → `medium` (safe default for unknown kinds).

## Overriding the mapping

Create `~/.config/vaultlab/dispatch.json`:

```json
{
  "light":  "claude-haiku-4-5",
  "medium": "claude-sonnet-4-6",
  "heavy":  "claude-opus-4-7"
}
```

A starter file lives at `examples/configs/dispatch.json`.

You can also override the config path for a single process by setting
the `VAULTLAB_DISPATCH_CONFIG` environment variable — used in tests and
in CI runs where the home directory is not writable.

Unknown keys (anything outside `light` / `medium` / `heavy`) are silently
ignored, and missing keys fall back to the defaults. Malformed JSON
files do not raise — the dispatcher is best-effort and must never crash
the caller's pipeline.

## Provenance integration

Entrypoints that call the dispatcher should record both the chosen model
and the weight in their `ProvenanceRecord.params`:

```python
from vaultlab.workflows.task_weight import TaskSpec, classify, model_for_weight
from vaultlab.provenance import ProvenanceRecord, write_receipts

spec = TaskSpec(kind="single_paper_read", n_inputs=1)
weight = classify(spec)
model_id = model_for_weight(weight)

record = ProvenanceRecord(
    generated_by="vaultlab.research.full_reader.build_paper_reader",
    kind="paper_reader",
    inputs=[source_str],
    model=model_id,
    params={"weight": weight, "model": model_id, ...},
)
write_receipts(str(output_path), record)
```

Audits can then reconstruct which calls ran on cheap models vs. premium
ones and where the budget was spent.

## Wired entrypoints

* `vaultlab.research.full_reader.build_paper_reader` — single-paper
  bilingual reader. Classifies as `medium` (single paper, summarize-ish
  task); the resolved model is recorded in the provenance manifest.

Additional entrypoints will be wired in follow-ups; see the goal file
at `.claude/goals/spec-f-task-weight-dispatch.md` for the current
status.
