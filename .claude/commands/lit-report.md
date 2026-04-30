---
name: lit-report
purpose: Generate a 3000-5000 word deep-research review report for a topic. Five sections (background / methods landscape / key findings / contradictions / future directions) generated via FULL adversarial crosstalk meetings. The differentiator that proves vaultlab can produce graduate-student-level scientific review writing.
arguments: <topic>
---

# /lit-report

Compose a **deep-research review report** for `<topic>`: a 3000-5000
word, 5-section review-paper-style markdown produced via FULL
adversarial crosstalk meetings on every section, plus a final rigor
audit. This is the differentiator from `/lit-arc` -- same Phase 1-6
pipeline, but instead of a 3-paragraph arc, you get a graduate-student-
level review with cohesion threading and per-section evidence anchoring.

## What this command produces

For topic `<topic>` (slugified), this command writes:

- `Sources/Notes/lit-search-<topic-slug>-<date>.md` -- search session log
- `Sources/Articles/<doi-slug>.md` -- one stub per seed paper
- `Sources/Papers/<doi-slug>.pdf` -- downloaded full-text (acquisition waterfall)
- `Wiki/Summaries/<doi-slug>.md` -- per-paper LLM summary with `[pN]` page markers
- `Wiki/Concepts/<topic-slug>-report-<date>.md` -- **the assembled review**
- `Wiki/Concepts/<topic-slug>-report-<date>/<section>.md` -- per-section drafts
- `Wiki/Concepts/<topic-slug>-report-<date>/audit.md` -- rigor-audit fix-list
- `<report>.provenance.json` + `<report>.method.md` -- provenance receipts

## Tiered crosstalk default: ON for every section

Per Bobby''s grill-crosstalk-integration-2026-04-30.md Q1 ("tiered +
dynamic"), `/lit-report` defaults to **FULL ADVERSARIAL crosstalk on
every section** -- no opt-out. Each section runs a section-specific
3-role meeting (3 rounds, 10-min wall-clock cap), and the assembled
document gets a final pass from the `rigor_auditor` role.

This is intentional: `/lit-arc` is for daily literature review (fast +
optional crosstalk); `/lit-report` is for the deep-research-mode reviews
that prove the system works.

## Section role mixes

Per grill Q3 + section purpose:

| Section | Roles | Why |
|---|---|---|
| Background | literature_surveyor, domain_expert, synthesizer | broad scope |
| Methods landscape | literature_surveyor, methods_critic, synthesizer | technical comparison |
| Key findings | data_analyst, methods_critic, literature_critic, synthesizer | evidence-grounded synthesis |
| Contradictions | methods_critic, literature_critic, synthesizer | adversarial reading |
| Future directions | domain_expert, synthesizer | speculative but bounded |

Synthesizer is always last -- its JSON output IS the meeting''s
`final_output`.

## How to execute

You (Claude Code) are the LLM. The Python pipeline does deterministic
work (search, citation graph, PDF acquisition); YOU read the PDFs,
write the per-paper summaries, drive crosstalk meetings, and audit the
final document. No Anthropic API key is needed because YOU are the API.

The whole pipeline is wired through
`run_lit_report(..., reader=..., crosstalk_runner=...)`. The callbacks
are filled in BY YOU at runtime -- when the orchestrator invokes them,
you (Claude) read the PDFs / execute the meeting turns and produce JSON
responses matching the task''s schema.

### Step 1 -- Set up

```python
from pathlib import Path
from vaultlab.context import locations as _loc
from vaultlab.research import (
    ReportTask, SummarizationTask, run_lit_report,
)

topic = "<topic from $ARGUMENTS>"
kb_locations = _loc.load_locations()
kb_root = Path(_loc.get_path("kb.root", locations=kb_locations))
```

If `kb_root` is not set, ask the user which KB they want this written
to (they may have multiple -- `research`, `tools`, `dcp`, etc.).

### Step 2 -- Define the per-paper PDF reader (YOU read each PDF)

When `run_lit_report` reaches Phase 6, it builds a `SummarizationTask`
for each Tier-A paper and calls your reader with it. Same shape as
`/lit-arc`''s reader. Your job per call:

1. Read `task.pdf_path` with the Read tool.
2. Inspect `task.prompt` (already includes title / authors / refs guidance).
3. Return JSON matching `task.response_schema`:

```json
{
  "tldr": "<3 sentences>",
  "why_it_matters": ["<bullet 1>", "<bullet 2>"],
  "methods_summary": "<1-2 paragraphs>",
  "key_findings": [
    "<finding 1 [p<N>]>",
    "<finding 2 [p<N>]>",
    "<finding 3 [p<N>]>"
  ],
  "extracted_references": []
}
```

```python
def claude_code_reader(task: SummarizationTask) -> dict:
    # YOU implement this at runtime by reading task.pdf_path and
    # producing the JSON response.
    ...
```

### Step 3 -- Define the crosstalk runner (YOU drive section meetings)

The crosstalk runner is the heart of `/lit-report`. For every section
(5 total) AND the final rigor audit, the orchestrator calls
`crosstalk_runner(meeting, roles)` and expects a list of dicts --
one per role -- with each dict carrying `{"output": "<role''s response text>"}`.

Per round:

1. Each role gets `meeting.session_context` + the prepared agenda
   (visible via `meeting.agenda.statement` and `meeting.agenda.questions`).
2. The synthesizer role (always last in `roles`) MUST return JSON
   matching the section''s response schema. The orchestrator parses the
   JSON and uses it as the meeting''s `final_output`.
3. Non-synthesizer roles return free text -- those go into the
   transcript but don''t drive the final output.

Section schemas:

For sections (background, methods_landscape, findings, contradictions,
future_directions), the synthesizer''s JSON must match
`section_response_schema()`:

```json
{
  "section_text": "<full markdown body with [[wikilinks]] every 2-3 sentences>",
  "claims_with_evidence": [
    {"claim": "<a single claim>", "doi_slugs": ["<slug1>", "<slug2>"]}
  ]
}
```

For the rigor audit (audit_kind="report"), the auditor returns:

```json
{
  "passed": true,
  "issues": [
    {
      "loc": "Background",
      "severity": "minor|major|blocker",
      "kind": "missing-evidence|overclaim|broken-wikilink|other",
      "fix": "<actionable fix>"
    }
  ]
}
```

```python
from vaultlab.workflows import RunnerCallback
from vaultlab.runner.models import Meeting, Role

def claude_code_runner(meeting: Meeting, roles: list[Role]) -> list[dict]:
    """Execute one ADVERSARIAL meeting round in this Claude Code session.
    YOU implement at runtime -- read role.system_prompt + meeting.agenda
    + meeting.session_context, return one dict per role with the role''s
    response in {"output": str}.
    """
    ...
```

### Step 4 -- Run the orchestrator

```python
result = run_lit_report(
    topic,
    kb_root=kb_root,
    depth="thorough",                 # /lit-report default = thorough
    max_seeds=20,                     # /lit-report default = 20 seeds
    audience="graduate-student",      # or "domain-expert" / "interdisciplinary"

    # Phase 1-6 callbacks
    reader=claude_code_reader,
    # picker_callback=...             # optional content-aware picker

    # Phase 7+8 -- crosstalk runner is the differentiator
    crosstalk_runner=claude_code_runner,
    crosstalk_n_rounds=3,             # default 3, hard cap 5

    # Optional: section_writer fallback if crosstalk meeting fails
    # section_writer=claude_code_section_writer,

    # Optional: refuse to write report on blocker-level audit issues
    # audit_strict=False,
)
```

This will:

1. Search PubMed / Semantic Scholar / CrossRef for ~20 seeds.
2. Write the search log + article stubs (no LLM).
3. Build the corpus + metrics (CrossRef ref-walk, no LLM).
4. Acquire PDFs via the waterfall (no LLM).
5. Call your reader once per Tier-A paper.
6. **Phase 7** -- for each of the 5 sections, drive an adversarial
   crosstalk meeting (3 rounds, section-specific role mix). Section N+1
   receives sections 1..N as `prior_sections` for cohesion.
7. **Phase 8** -- `rigor_audit` runs on the assembled body. Issues are
   surfaced in the audit footer; missing-evidence claims are inlined
   as `> **[NEEDS EVIDENCE]**` blockquotes by `render_section_from_response`.
8. **Phase 9** -- assemble the markdown (frontmatter + abstract + 5
   sections + references + audit footer), write to
   `Wiki/Concepts/<topic>-report-<date>.md`, drop per-section drafts in
   the sibling directory, write provenance.

### Step 5 -- Print results

```
Lit-report complete for <topic>:
  - Search log:    <search_log_path>
  - Corpus:        <corpus_size> papers, <pdfs_acquired> with full-text
  - Sections:      5 (per-section drafts at <report>/)
  - Total words:   <word_count>  (target: 3000-5000)
  - Audit status:  <passed | passed_with_warnings | failed>
  - Report:        <report_path>

To open: bobby-kb open vaultlab/Wiki/Concepts/<topic-slug>-report-<date>
```

## Word-count guidance

Per spec, sections target:

| Section | Range | Default |
|---|---|---|
| Background | 500-800 | 650 |
| Methods landscape | 800-1200 | 1000 |
| Key findings | 1000-1500 | 1250 |
| Contradictions & open questions | 300-500 | 400 |
| Future directions | 200-400 | 300 |

Target total: 4000 (mid of 3000-5000 spec band). The synthesizer is
told the target in its prompt, but the actual produced length depends
on the conversation -- `render_section_from_response` doesn''t truncate.
The frontmatter records the actual achieved word count.

## Audit handling

- `audit_status: passed` -- no issues, ship clean.
- `audit_status: passed_with_warnings` -- minor issues, ship with audit
  footer.
- `audit_status: failed` -- blocker-level issues; report still ships
  unless you set `audit_strict=True` (then `RuntimeError` is raised
  before the file is written).

`render_section_from_response` also inlines `> **[NEEDS EVIDENCE]**`
margin comments when a claim has no `doi_slugs` or when the section
text contains zero wikilinks -- these are the cheap, automatic checks
that catch obvious hallucinations even before the auditor runs.

## Notes for users

- Runtime: 60-90 min for a 20-seed thorough run. The crosstalk meetings
  are the dominant cost (5 sections * 3 rounds * 3-4 roles + 1 audit
  meeting = 50+ LLM turns).
- Idempotent on the corpus level (same as `/lit-arc`): same topic on
  same date doesn''t re-download PDFs but DOES regenerate sections (so
  you can refine the runner / role prompts).
- For papers without OA PDFs (~25-35% of biomedical), Tier C stubs are
  written with citation stats but no LLM-generated TL;DR. They''re cited
  in the report by metadata only.
- For non-Claude-Code users: `run_lit_report(topic, kb_root=...)` (no
  `reader` / `crosstalk_runner` kwargs) calls the Anthropic SDK directly.
  Same pattern as `/lit-arc`.

## Test plan

- Trial dry-run (canned reader + canned crosstalk runner):
  `python scripts/_trial_lit_report.py`
- Unit tests (17 tests):
  `tests/test_vaultlab_research/test_report.py`
