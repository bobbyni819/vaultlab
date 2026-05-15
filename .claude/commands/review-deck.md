---
name: review-deck
description: Run the unified self-review pass on a rendered .pptx — per-slide checks (fonts ≥ 28/24/18pt, descriptive titles ≥ 3 words, ≤ 7 bullets, no shape overlap, figure-presence on Figure slides) plus story-arc audits across the deck. Returns a ReviewReport and renders it as a critical-first HTML view (same grammar as the rigor-audit reports the pipeline already emits).
arguments: <pptx-path> [--out <path>] [--json]
---

# /review-deck <pptx-path>

> *"Audit your rendered deck against the slide hard-rules and the story
> arc — get a critical-first HTML report you can scan in 30 seconds
> before opening PowerPoint."*

Drives `vaultlab.slides.self_review.review_deck`. The check sequence:

| Scope | Check |
|---|---|
| Per-slide | Title font ≥ 28pt, body ≥ 24pt, caption ≥ 18pt (hard floor 18pt) |
| Per-slide | Descriptive title — ≥ 3 words, not a bare noun phrase like "Methods" |
| Per-slide | ≤ 7 bullets per slide |
| Per-slide | No overlapping shapes |
| Per-slide | Figure slides actually carry a figure |
| Story arc | Opening / divider / closing structure |
| Story arc | Section dividers ≤ 5 per deck |

Nothing is raised on a failing check — callers consult
`ReviewReport.n_critical` (or `ReviewReport.ok()`) for a pass/fail
decision. The HTML view colour-codes issues by severity and filters
to critical-first.

## Pre-flight

1. Confirm `<pptx-path>` exists and is a `.pptx`
2. python-pptx must be importable — install with
   `pip install -e ".[slides]"` if not
3. Resolve `--out` (default: alongside the pptx, `<stem>-review.html`)

## Execution

```python
import json
import shlex
from pathlib import Path
from vaultlab.slides.self_review import (
    review_deck,
    render_review_html,
    write_review_report,
)

raw_args = shlex.split("$ARGUMENTS") if "$ARGUMENTS" else []
positional: list[str] = []
out_arg: str | None = None
emit_json = False
i = 0
while i < len(raw_args):
    tok = raw_args[i]
    if tok == "--out" and i + 1 < len(raw_args):
        out_arg = raw_args[i + 1]
        i += 2
    elif tok == "--json":
        emit_json = True
        i += 1
    else:
        positional.append(tok)
        i += 1
pptx_path = Path(" ".join(positional).strip())
if not pptx_path.exists():
    raise SystemExit(f"pptx not found: {pptx_path}")

report = review_deck(pptx_path)

out_path = Path(out_arg) if out_arg else pptx_path.with_name(
    f"{pptx_path.stem}-review.html"
)
written = write_review_report(report, out_path)

print(f"Deck self-review for {pptx_path.name}:")
print(f"  slides:       {len(report.per_slide)}")
print(f"  critical:     {report.n_critical}")
print(f"  warnings:     {report.n_warning}")
print(f"  story-arc:    {len(report.story_arc_issues)} issue(s)")
print(f"  verdict:      {'PASS' if report.ok() else 'FAIL'}")
print(f"  html:         {written}")
print(f"to open: bobby-kb open {written}")

if emit_json:
    # Best-effort dataclass → dict
    from dataclasses import asdict
    sidecar = out_path.with_suffix(".json")
    sidecar.write_text(json.dumps(asdict(report), default=str, indent=2), encoding="utf-8")
    print(f"  json:         {sidecar}")
```

## Output

- `<stem>-review.html` — critical-first HTML audit (same grammar as
  `vaultlab.slides.audit_html`). Filter by severity, drill into the
  per-slide list, see the story-arc issues at the top.
- `<stem>-review.html.provenance.json` + `<stem>-review.html.method.md`
  — Red Line #2 sidecars
- `<stem>-review.json` *(optional, `--json` flag)* — the raw
  `ReviewReport` as JSON for downstream tooling

## When to use

- **Always** before opening a deck for Bobby — slide-hard-rules are
  non-negotiable (Roboto, 28/24/18pt min, descriptive titles, ≤ 5
  section_dividers, no overlap). Self-audit before showing.
- Before submitting a journal-club deck or grant talk for review.
- In a CI hook on any `.pptx` artifact emitted by the deck pipeline.

## Rules of engagement

- **The check is non-fatal.** A failing review doesn't stop downstream
  work — it just flags issues. Re-render the deck after fixing.
- **Regenerate, don't retrofit.** When font / overlap / title issues
  surface, fix them in the deck *plan*, not by hand-editing the pptx.
  Re-run `/build-deck` with the updated plan.
- **The HTML report is the source of truth.** Scan it before opening
  PowerPoint — it surfaces issues PowerPoint won't.

## Test plan

- Synthetic pptx with 8pt body text → review should flag a `critical`
  font-size violation.
- Deck with a slide titled "Methods" (one word) → review should flag a
  `warning` descriptive-title violation.
- Deck with two text boxes overlapping > 20% area → review should flag
  a `critical` overlap violation.
- Story-arc deck with 0 opening slides → review should append a
  `warning` to `story_arc_issues`.

## Related

- `vaultlab.slides.self_review` — underlying audit + renderer
- `vaultlab.slides.audit_html` — the shared HTML grammar
- `/build-deck` — generate the `.pptx` from a plan (always run this
  command after)
- `/preview-deck` — keynav HTML preview (no audit; just see the slides)
- `Wiki/Concepts/slide-hard-rules.md` — the hard-rule reference
