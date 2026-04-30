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

### Step 4 — Run the orchestrator

```python
result = run_lit_arc(
    topic,
    kb_root=kb_root,
    max_seeds=15,
    max_papers_to_summarize=20,
    reader=claude_code_reader,
    narrator=claude_code_narrator,
)
```

This will:
1. Search PubMed / Semantic Scholar / CrossRef for seeds.
2. Write the search log + article stubs (no LLM).
3. Build the corpus + metrics (CrossRef ref-walk, no LLM).
4. Acquire OA PDFs via the Unpaywall / PMC / publisher waterfall (no LLM).
5. Call your reader once per Tier-A paper (you read each PDF, return JSON).
6. Call your narrator once with all summaries (you read summaries, return JSON).
7. Write provenance receipts.

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
  acquisition success rate.
- For non-Claude-Code users: `run_lit_arc(topic, kb_root=...)` (no `reader` /
  `narrator` kwargs) calls the Anthropic SDK directly. See
  `docs/setup-api-keys.md` for the "Anthropic API key — do you need one?"
  decision tree.

## Test plan

- Trial dry-run (canned reader / narrator):
  `python scripts/_trial_lit_arc_claude_code.py`
- Unit tests:
  `tests/test_vaultlab_research/test_summarize.py::test_summarize_corpus_with_reader`
  `tests/test_vaultlab_research/test_lineage.py::test_run_lit_arc_with_reader_and_narrator`
