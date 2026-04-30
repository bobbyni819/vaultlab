---
name: lit-arc
purpose: Generate a literature lineage arc (history → development → SOTA) for a topic, using Claude Code itself as the LLM (no API key needed).
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

### Step 1 — Set up

```python
from pathlib import Path
from vaultlab.context.locations import get_kb_root
from vaultlab.research.lineage import run_lit_arc

topic = "<topic from $ARGUMENTS>"
kb_root = get_kb_root("vaultlab")  # or whichever KB the user is in
```

If `kb_root` is not set, ask the user which KB they want this written to
(they may have multiple — `research`, `tools`, `dcp`, etc.).

### Step 2 — Run phases 1-5 (deterministic, no LLM)

These use the ResearchClient + corpus + acquisition pipeline. They don't
need you to do anything beyond invoking the orchestrator.

```python
result = run_lit_arc(
    topic,
    kb_root=kb_root,
    max_seeds=15,
    max_papers_to_summarize=20,
    skip_summarization=True,   # YOU will do summaries, not the SDK path
    skip_arc=True,              # YOU will write the arc, not the SDK path
)
```

`result.summary_paths` will contain Tier C stubs only at this point (frontmatter
populated; LLM-written sections empty).

### Step 3 — Per-paper summaries (you read the PDFs)

For each paper in `result.summary_paths` that has a corresponding PDF in
`Sources/Papers/<doi-slug>.pdf`:

```python
from vaultlab.research.summarize import (
    prepare_summary_task, render_summary_from_response,
    summary_response_schema,
)
from vaultlab.research.corpus import build_corpus_from_seeds  # already done
# corpus, metrics already in result

for doi, summary_path in result.summary_paths.items():
    pdf_path = ...  # Sources/Papers/<doi>.pdf, check it exists
    if not pdf_path.exists():
        continue  # leave Tier C stub
    
    task = prepare_summary_task(
        doi=doi,
        pdf_path=pdf_path,
        paper_metadata=...,        # title, authors, year, journal from corpus
        corpus_metrics=result.metrics,
        corpus_papers=result.corpus_papers,
        crossref_refs_missing=...,
        kb_root=kb_root,
    )
    
    # YOU now read the PDF and respond with JSON matching task.response_schema
    pdf_bytes = pdf_path.read_bytes()  # or use Read tool
    # Read the PDF with multimodal capability + emit JSON per task.prompt
    response_json = <your structured JSON response>
    
    summary = render_summary_from_response(task, response_json)
    summary_path.write_text(render_summary_markdown(summary), encoding="utf-8")
```

For each PDF you read:
- TL;DR: 3 sentences max
- key_findings: each MUST have a `[p<N>]` page marker
- methods_summary: paragraph
- If `crossref_refs_missing=True`: also extract the References list as DOIs

### Step 4 — Lineage arc narrative

Once all summaries are written, generate the arc:

```python
from vaultlab.research.lineage import (
    prepare_arc_task, render_arc_from_response, arc_response_schema,
)

arc_task = prepare_arc_task(
    topic=topic,
    corpus=result.corpus,
    summaries=result.summaries,  # PaperSummary dict
    kb_root=kb_root,
)

# Read arc_task.prompt; respond with JSON per arc_response_schema()
# (3 paragraphs: history / development / sota; each cites 3-5 [[doi-slug]] wikilinks)
response_json = <your JSON arc response>

arc_path = render_arc_from_response(arc_task, response_json)
```

The arc reads ONLY the per-paper summaries (TL;DRs + key findings), not full
PDFs — so it fits comfortably in your context.

### Step 5 — Provenance receipts

```python
from vaultlab.provenance import write_receipts, ProvenanceRecord

record = ProvenanceRecord(
    generated_by="vaultlab.research.lineage.run_lit_arc",
    project="lit-arc",
    topic=topic,
    inputs=[str(p) for p in result.summary_paths.values()],
    params={"max_seeds": 15, "max_papers_to_summarize": 20},
    model="claude-code-session",  # YOU are the LLM
)
write_receipts(arc_path, record)
```

### Step 6 — Print results

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
