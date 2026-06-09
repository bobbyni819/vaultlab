---
name: figure-audit
type: pure-capability
backed_by: vaultlab.figures.verify_semantic.audit_figure_claims
arguments: <figure-path> "<claim>"   |   --spec <claims.json>
---

# /figure-audit <figure-path> "<claim>"

> *"Does this figure actually support what I wrote about it?"*

Semantic **figure-vs-claim** audit. Given a rendered figure and a textual claim about it,
a vision model returns a structured verdict — `SUPPORTED | PARTIAL | UNSUPPORTED |
FABRICATED` — with **figure-grounded evidence anchors** (bar heights, axis values, category
labels), plus a confidence. Use it to catch a claim that cites the wrong panel, invents a
quantification the figure never shows (p-value / n / error bars), drifts a value away from
the plotted bar, or overreaches from a partial truth.

This is the **discrete, user-invoked** path. It is NOT run automatically on every `/lit-arc`
figure — the benchmark showed ~0.82 precision (over-flags some correct figures) and a
non-deterministic SUPPORTED↔PARTIAL boundary, so an always-on inline gate would cause alarm
fatigue. As a reviewer-invoked audit, where you read the anchors and adjudicate, it is well
calibrated: measured **recall 1.0 on catching problems** (no broken claim passed as
SUPPORTED) and **FABRICATED detection 1.0/1.0**.

## Lineage

- Promotes the `methods_critic` semantic-figure-audit pattern (K=100-vs-K=25 argmax
  inversion; fig5C +0.32→+0.38 drift) into a measured primitive. See `INSPIRATIONS.md` →
  *verify_semantic*.
- Complements — does NOT duplicate — the deterministic text verifiers `enforce_hedge`,
  `verify_numeric`, `compare_two_groups`. Those catch lexical/numeric lies in *text*; this
  catches semantic mismatch between a claim and what a figure *shows*.
- Evidence-anchor UX mirrors NotebookLM hover-to-quote (cite the figure element, not prose).

## Inputs

- `<figure-path>`: path to a rendered figure (`.png`/`.jpg`/`.gif`/`.webp`).
- `"<claim>"`: the textual claim to verify against that figure.
- `--spec <claims.json>` (alternative, for batch): a JSON list of `{"figure": "...", "claim": "..."}`
  objects. Audits every pair and writes one aggregate report.

Scope: audits **explicit (figure, claim) pairs**. Automatically mining figure-claims from
manuscript prose is a separate, unbuilt component — out of scope here.

## Outputs

- `<kb>/Output/<project-slug>/Reports/figure-audit-<slug>-<date>.json` — machine-readable
  report (per-claim verdict, evidence anchors, confidence, flagged).
- `…/figure-audit-<slug>-<date>.md` — critical-first human report (flagged claims first).
- `…<file>.provenance.json` + `.method.md` — provenance receipts (Red Line #2).

## Pre-flight

1. `resolve_kb_root()`; if it raises `KbRootNotConfigured`, tell the user to run `vaultlab init`.
2. `load_project_config_from_cwd()` for the project slug (fall back to the figure stem if `None`).
3. Verify each figure path exists + is readable.

## Execution

### Mode A — SDK (default; `ANTHROPIC_API_KEY` set)

Each pair routes through the real `claude-sonnet-4-6` vision verifier.

```python
from datetime import datetime
from pathlib import Path
from vaultlab.context import resolve_kb_root
from vaultlab.kb.paths import project_dir
from vaultlab.figures.verify_semantic import audit_figure_claims, write_audit_report

# pairs := [(figure_path, claim), ...]  parsed from $ARGUMENTS or --spec
report = audit_figure_claims(pairs, project=project_slug)

out_dir = project_dir(resolve_kb_root(), project_slug) / "Reports"
paths = write_audit_report(
    report, out_dir,
    slug=Path(pairs[0][0]).stem,
    date_str=datetime.now().strftime("%Y-%m-%d"),
)
print(report.overall, report.verdict_counts, paths["md"])
```

### Mode B — Claude-Code-as-LLM (no API key)

You (Claude Code) are the vision model. For each pair: `Read` the figure, apply the system
prompt at `vaultlab/figures/verify_semantic/prompt.md`, and return a verdict dict. Pass it
through `verdict_fn` — `audit_figure_claims` validates it with the same `validate_verdict`
the SDK path uses (an out-of-contract verdict is surfaced, never coerced).

```python
def claude_code_verdict(claim: str, figure_path: str) -> dict:
    # 1. Read(file_path=figure_path)  — actually look at the figure
    # 2. Apply prompt.md; judge the claim against what is visible
    # 3. Return {"verdict": "...", "evidence_anchors": ["axis value ...", ...], "confidence": 0.0}
    ...

report = audit_figure_claims(pairs, project=project_slug, verdict_fn=claude_code_verdict)
```

## Surface to the user

- The overall verdict (`clean` / `flags_found`) and the per-verdict counts.
- For each **flagged** claim: the verdict, confidence, and its evidence anchors — these are
  the re-check prompts.
- Path to the saved report (`bobby-kb open <path>` so it can be read on their schedule).

Hedged voice: a flag means the figure does not fully support the claim *as written* — a
prompt to re-check, not a ruling on the science.

## What this is NOT

- Not a deterministic publication-guideline check (DPI/fonts/color) — that is
  `/publication-guideline-audit`.
- Not a content read of "what does this figure show?" — that is `/understand-figure`.
- Not a numeric re-computation of result tables — that is the analysis pipeline's
  `verify_numeric` / `compare_two_groups`.
- Not an inline `/lit-arc` pass (gated on a precision fix + the bar-chart-renderer
  overlapping-x-label fix — the seaborn `mean(value)` barplot path, not `research/figures.py`;
  see the benchmark report).

## See also

- `vaultlab/src/vaultlab/figures/verify_semantic/{verifier.py, audit.py, prompt.md}`
- Benchmark + measured accuracy + recommendation:
  `<kb>/<project>/Output/figure-claim-verifier-2026-06-09/measurement-report.md`
- `INSPIRATIONS.md` → *verify_semantic*

## Test plan

- [x] Offline engine tests: `tests/test_vaultlab_figures/test_figure_audit.py`
- [x] Smoke test: invoked on `Fig4A_bar.png` (elife-91157-stress) — faithful claim →
      SUPPORTED (0.95), invented p-value/n claim → FABRICATED (0.99); report + provenance
      written under `Output/<slug>/Reports/`.
- [x] `vaultlab claude validate` lists `/figure-audit` (38/38 command files valid)
