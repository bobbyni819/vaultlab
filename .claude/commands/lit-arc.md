---
name: lit-arc
purpose: Generate a literature lineage arc (history -> development -> SOTA) for a topic, using Claude Code itself as the LLM (no API key needed).
arguments: <topic>
---

# /lit-arc

Compose a research literature **lineage arc** for `<topic>`: a 3-section narrative
(history / development / state-of-the-art) backed by a citation-graph corpus,
per-paper Claude-read summaries, and structured citation statistics.

## What this command produces

For topic `<topic>` (slugified), this command writes:

- `Sources/Notes/lit-search-<topic-slug>-<date>.md` — search session log
- `Sources/Articles/<doi-slug>.md` — one stub per seed paper
- `Sources/Papers/<doi-slug>.pdf` — downloaded full-text (acquisition waterfall)
- `Wiki/Summaries/<doi-slug>.md` — per-paper LLM summary (with og_score, year_bucket, [[wikilinks]])
- `Wiki/Concepts/<topic-slug>-lineage-<date>.md` — the lineage arc narrative
- `<arc>.provenance.json` + `<arc>.method.md` — provenance receipts

## How to execute

You (Claude Code) are the LLM. The Python pipeline does deterministic work
(search, citation graph, PDF acquisition); YOU read the PDFs and write the
summaries + arc narrative. No Anthropic API key is needed because YOU are
the API.

The whole pipeline is wired through `run_lit_arc(..., reader=..., narrator=...)`.
The `reader` and `narrator` callbacks are filled in BY YOU at runtime — when
the orchestrator invokes them, you (Claude) read the PDF / summaries with
the Read tool and produce a JSON response matching the task's schema.

### Step 1 — Set up

```python
from pathlib import Path
from vaultlab.context import locations as _loc
from vaultlab.research import (
    ArcTask, PickerTask, SummarizationTask, run_lit_arc,
)

topic = "<topic from $ARGUMENTS>"
kb_locations = _loc.load_locations()
kb_root = Path(_loc.get_path("kb.root", locations=kb_locations))

# F-1 onboarding handoff: when /onboard-project ran earlier in this
# project folder (or a parent), pick up slug + kb_root + topic from the
# .vaultlab-project.json instead of re-asking. Threading explicitly is
# still recommended; the orchestrator (run_lit_arc) ALSO falls back to
# load_project_config_from_cwd() internally when project_slug is None
# (G-2 fix from conceptual-flow audit 2026-04-30), so a forgetful caller
# no longer silently spawns a parallel Wiki/Projects/<topic-slug>/.
# Explicit kwargs still win when the values disagree.
from vaultlab.onboarding import load_project_config_from_cwd
project_cfg = load_project_config_from_cwd()
project_slug: str | None = None
if project_cfg is not None:
    project_slug = project_cfg.slug or None
    if project_cfg.kb_root:
        kb_root = Path(project_cfg.kb_root)
    if not topic and project_cfg.topic:
        topic = project_cfg.topic
```

If `kb_root` is not set, ask the user which KB they want this written to
(they may have multiple — `research`, `tools`, `dcp`, etc.).

### Step 2 — Define the content-aware paper picker (YOU read abstracts)

Before Tier-A reads, the orchestrator builds a `PickerTask` containing
the top-30 candidates' abstracts and asks YOU to rank by topical
relevance + likely contribution + diversity. This avoids the
"citation-graph picks an off-topic paper because it has a cached figure"
failure mode (L4 spatial-tx Gjerstorff 2006 bug, 2026-04-30).

Your job per call:

1. Inspect `task.candidates` — list of `CandidatePaper` (doi, title,
   authors, year, journal, abstract, og_score, forward_influence, has_pdf).
2. Inspect `task.prompt` (already includes the topic + ranking criteria).
3. Return JSON matching `task.response_schema`:

```
{
  "picks": [
    {"doi": "10.1038/...", "rank": 1, "rationale": "Foundational CODEX paper..."},
    {"doi": "10.1126/...", "rank": 2, "rationale": "Methodological extension..."},
    ...
  ]
}
```

Rank papers most-relevant-first. The orchestrator takes
`task.target_n` picks. **Only return DOIs that appear in
`task.candidates`** — fabricated DOIs get filtered out.

```python
def claude_code_picker(task: PickerTask) -> dict:
    # YOU implement this at runtime by reading abstracts and ranking.
    # Citation-graph fallback runs if you raise / return non-dict.
    ...
```

### Step 2b — Define the LLM-driven binning callback (YOU read every abstract)

Between corpus build and per-paper summarization, the orchestrator
asks YOU to assign each corpus paper to **history / development / sota**
based on its conceptual role in THIS topic's lineage — not just its
publication year. This fixes the "empty history bucket" failure mode
where every paper in the corpus is from 2018+ and the deterministic
year-quartile bucketing produces zero foundational papers (Bobby's
L4 CODEX bug, 2026-04-30).

The orchestrator builds a `BinningTask` containing every corpus paper's
title, year, abstract, og_score, forward_influence, and the deterministic
year-quartile bucket as a hint. Your job per call:

1. Inspect `task.candidates` — list of `BinningCandidate` (doi, title,
   year, abstract, og_score, forward_influence, deterministic_bucket).
2. Inspect `task.prompt` and `task.system` (already include the per-bucket
   criteria and the "year is a hint, not a rule" guidance).
3. Return JSON matching `task.response_schema`:

```
{
  "assignments": [
    {"doi": "10.1016/...", "bucket": "history", "rationale": "Introduces CODEX (foundational)..."},
    {"doi": "10.1038/...", "bucket": "development", "rationale": "Application of CODEX..."},
    {"doi": "10.1016/...", "bucket": "sota", "rationale": "Most recent meaningful advance..."},
    ...
  ]
}
```

Bucket definitions (also in `task.system`):
- `history`: foundational method, precursor concept, paradigm-defining
  work for the topic — REGARDLESS of publication year.
- `development`: intermediate refinement, scaling, methodological
  adaptation, mid-arc work.
- `sota`: current frontier — most recent meaningful advance, even if
  not the most-recent paper by date. Incremental applications of older
  methods are DEVELOPMENT, not SOTA.

Aim for non-empty bins where the corpus reasonably supports it. If the
deterministic system left HISTORY empty but a foundational paper is
present, MOVE that paper to HISTORY.

```python
def claude_code_binner(task: BinningTask) -> dict:
    # YOU implement this at runtime by reading abstracts and deciding
    # the conceptual bucket per topic. Deterministic fallback runs if
    # you raise / return non-dict.
    ...
```

When `binner_callback` is None, the deterministic year-quartile buckets
stand (the previous behaviour, preserved for backwards compat). The
LLM-driven path is **recommended** — pass `binner_callback=claude_code_binner`
to `run_lit_arc` to avoid empty-bucket failures on recent corpora.

### Step 3 — Define the per-paper reader (YOU read the PDF)

When `run_lit_arc` reaches phase 6, it builds a `SummarizationTask` for each
Tier-A paper (one with an acquired PDF) and calls your reader with it.
Your job per call:

1. Read `task.pdf_path` with the Read tool.
2. Inspect `task.prompt` (already includes title / authors / refs guidance).
3. Inspect `task.system_prompt` (the "be faithful, cite pages" guard rail).
4. Return JSON matching `task.response_schema`:

```
{
  "tldr": "<3 sentences>",
  "why_it_matters": ["<bullet 1>", "<bullet 2>", ...],
  "methods_summary": "<1-2 paragraphs>",
  "key_findings": [
    "<finding 1 [p<N>]>",
    "<finding 2 [p<N>]>",
    "<finding 3 [p<N>]>"
  ],
  "extracted_references": []  # only populate when task.crossref_refs_missing
}
```

Rules:
- Every key_finding MUST end with `[p<N>]` (page number) or `[unknown]`.
- TL;DR is exactly 3 sentences; first sentence states the central contribution.
- Tier-C papers (no PDF) are NEVER passed to your reader — the orchestrator
  emits a citation-stat-only stub for them automatically.

```python
def claude_code_reader(task: SummarizationTask) -> dict:
    # YOU implement this at runtime by:
    #   1. Read(file_path=str(task.pdf_path))
    #   2. produce JSON matching task.response_schema
    ...
```

### Step 3 — Define the lineage-arc narrator (YOU read the summaries)

After all per-paper summaries are written, `run_lit_arc` builds a single
`ArcTask` and calls your narrator. Your job:

1. The summaries are embedded in `task.summaries` (a dict of doi -> PaperSummary)
   AND already on disk under `Wiki/Summaries/<doi>.md`. Use whichever is more
   convenient — the in-memory dict has fields like `tldr`, `key_findings`,
   `og_score`, `year_bucket`.
2. Inspect `task.prompt` (it already feeds you the bucketed summaries +
   top-OG papers + top co-citation pairs and the exact wikilink targets to use).
3. Return JSON matching `task.response_schema`:

```
{
  "history":     "<3-6 sentence paragraph with [[<doi-slug>|Author Year]] wikilinks>",
  "development": "<3-6 sentence paragraph>",
  "sota":        "<3-6 sentence paragraph>"
}
```

Each paragraph must cite 3-5 papers. Use ONLY the slugs / labels listed in
`task.prompt` — never invent citations.

```python
def claude_code_narrator(task: ArcTask) -> dict:
    # YOU implement this at runtime by reading task.summaries + answering
    # task.prompt with three paragraphs of JSON.
    ...
```

### Step 4 — Define the runner callback (for crosstalk; tiered default ON)

Per Bobby's "tiered + dynamic" crosstalk decision, `/lit-arc` defaults
to ADVERSARIAL meetings on **picker** and **arc** (analyst → critic →
synthesizer over 3 rounds, hard cap 5, 10-min wall-clock timeout).
Each role outputs structured JSON to prevent spirals. To opt into
crosstalk, define a `runner_callback`:

```python
from vaultlab.workflows import RunnerCallback
from vaultlab.runner.models import Meeting, Role
from typing import Sequence

def claude_code_runner(meeting: Meeting, members: Sequence[Role]) -> list[dict]:
    """Execute one ADVERSARIAL meeting in this Claude Code session.
    Each round: each role gets meeting.task + the prior turns,
    returns structured JSON per their role's schema. The orchestrator
    composes the turns into the meeting transcript.
    
    YOU implement at runtime — no SDK call. Reads role.system_prompt
    + meeting state, returns analyst draft / critic objections /
    synthesizer integration as JSON dicts in turn order.
    """
    ...
```

When `runner_callback` is None, picker_mode and arc_mode FALL BACK to
single-shot picker_callback / narrator. Backwards compat preserved.

### Step 5 — Run the orchestrator

```python
result = run_lit_arc(
    topic,
    kb_root=kb_root,
    project_slug=project_slug,       # F-1: from .vaultlab-project.json
                                     # (None if no onboarding config —
                                     # falls back to slugify_topic(topic))
    depth="balanced",                # see "Depth modes" below
    max_seeds=15,
    
    # Single-shot LLM callbacks (always required)
    picker_callback=claude_code_picker,
    binner_callback=claude_code_binner,   # recommended — fixes empty-bucket
    reader=claude_code_reader,
    narrator=claude_code_narrator,
    
    # Crosstalk integration (tiered default ON per Bobby's decision)
    picker_mode="adversarial",       # "fast" | "adversarial"
    arc_mode="adversarial",          # "fast" | "adversarial"
    crosstalk_runner=claude_code_runner,
    crosstalk_n_rounds=3,            # default 3, hard cap 5

    # Figure acquisition (Fix 1, 2026-04-30 evening-4) - opt-in.
    # When True, the orchestrator runs Phase 5b after PDF acquisition,
    # fetching native-resolution figures + captions via the API
    # waterfall (PMC OA tar -> Elsevier ScienceDirect XML ->
    # Springer OA JSON). The resulting figure_assignments map
    # (DOI -> figure_path) is carried on the LineageRunResult so
    # build_deck_from_lineage_result can populate figure-slides
    # without a second acquisition pass. Default False.
    acquire_figures=True,            # figures land at <kb_root>/Sources/Figures/
)

# Then plumb figures into the deck (no need to call
# acquire_figures_for_corpus a second time):
#   from vaultlab.slides.deck import build_deck_from_lineage_result
#   build_deck_from_lineage_result(
#       result, ..., figure_assignments=result.figure_assignments,
#   )
```

When the user requests `/lit-arc <topic> --mode fast`, set
`picker_mode="fast"` and `arc_mode="fast"` to bypass crosstalk
(fast scope mode).

This will:
1. Search PubMed / Semantic Scholar / CrossRef for seeds.
2. Write the search log + article stubs (no LLM).
3. Build the corpus + metrics (CrossRef ref-walk, no LLM).
4. Acquire OA PDFs via the Unpaywall / PMC / publisher waterfall (no LLM).
5. Call your reader once per Tier-A paper (you read each PDF, return JSON).
6. Call your narrator once with all summaries (you read summaries, return JSON).
7. Write provenance receipts.

## Depth modes

By default `/lit-arc` runs with `depth="balanced"`. Pass `depth="fast"` for
quick scoping (~15 min, ~20 Tier-A) or `depth="thorough"` for deep work
(~60 min, every cached PDF read). Defaults:

| Depth      | Tier A budget        | Wall time | Use case                    |
|------------|----------------------|-----------|-----------------------------|
| fast       | 20                   | ~15 min   | Quick scoping               |
| balanced   | 50                   | ~30 min   | Daily literature review     |
| thorough   | All cached PDFs      | ~60 min   | Writing a deep review       |
| complete   | All + retry paywall  | ~90 min   | Publication-grade research  |

`depth="complete"` additionally re-runs the acquisition waterfall with the
full Springer/Elsevier tier on any DOI that came back unavailable on the
first pass — use this when the user explicitly says they want every paper
that can possibly be acquired (institutional license required for the
paywalled tiers to actually return PDFs).

Pass `max_papers_to_summarize=N` (an explicit int) to override the
depth-derived budget — explicit always wins. Default is `None`, meaning
"derive from `depth`" (the budget is computed AFTER PDF acquisition so
the ceiling is the actual count of cached PDFs).

When the corpus is large (>200 papers) and depth is `thorough` or
`complete`, the orchestrator logs a warning at the start of Phase 6
(summarization) so the user can Ctrl-C if they didn't mean it.

### Step 5 — Print results

```
Lit-arc complete for <topic>:
  - Search log:    <search_log_path>
  - Corpus:        <corpus_size> papers, <pdfs_acquired> with full-text
  - Summaries:     <summaries_written> at Wiki/Summaries/
  - Arc:           <arc_path>

To open: bobby-kb open vaultlab/Wiki/Concepts/<topic-slug>-lineage-<date>
```

## Notes for users

- The pipeline is **idempotent on the corpus level** — re-running with the same
  topic on the same date doesn't re-download PDFs (acquisition cache is
  honored) but DOES regenerate summaries and arc (so you can refine prompts).
- For papers without OA PDFs (~25-35% of biomedical), Tier C stubs are written
  with citation stats but no LLM-generated TL;DR. They're still cited in the
  arc by metadata.
- Total runtime: ~15-30 min for a 15-seed, 20-summary topic depending on PDF
  acquisition success rate. Use `depth="thorough"` or `depth="complete"` for
  larger corpora — see the **Depth modes** table above.
- For non-Claude-Code users: `run_lit_arc(topic, kb_root=...)` (no `reader` /
  `narrator` kwargs) calls the Anthropic SDK directly. See
  `docs/setup-api-keys.md` for the "Anthropic API key — do you need one?"
  decision tree.

## Test plan

- Trial dry-run (canned reader / narrator):
  `python scripts/_trial_lit_arc_claude_code.py`
- Trial depth-flag budget check:
  `python scripts/_trial_depth_flag.py`
- Unit tests:
  `tests/test_vaultlab_research/test_summarize.py::test_summarize_corpus_with_reader`
  `tests/test_vaultlab_research/test_lineage.py::test_run_lit_arc_with_reader_and_narrator`
  `tests/test_vaultlab_research/test_lineage.py::test_run_lit_arc_depth_fast_caps_at_20`