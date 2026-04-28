# vaultlab slash command inventory

Every slash command vaultlab exposes. Two categories per AGENTS.md Invariant 9:

- **Pure capability** — single-purpose; calls one capability subpackage directly
- **Orchestrated** — multi-agent meeting or plan-execute-verify-refine loop

## v0.0.1 (current — most are placeholders)

| Command | Type | Status | Purpose |
|---|---|---|---|
| `/onboard-project [path]` | Orchestrated | Spec'd | Walk vaultlab through a new project: structure scan + draft understanding + grill verification + START_HERE init |

For v0.0.1, most commands print "not yet implemented." See [Roadmap](../README.md#roadmap) for landing dates.

## v0.1.0 (target 2026-05-27)

### Project + KB management
- `/onboard-project [path]` — discover + understand a new project
- `/research-status` — current focus, recent activity, files to read next
- `/groom-kb` — KB consistency audit + tidying
- `/kb [compile|ask|lint|ingest]` — KB operations

### Literature
- `/lit-search <query>` — multi-source paper search (PubMed, Semantic Scholar, CrossRef, bioRxiv, Springer, Elsevier, paperclip MCP) with smart query expansion + re-rank
- `/dig-deeper <doi>` — explore citation graph forward + backward
- `/cite [audit|verify|status]` — citation verification + hallucination detection
- `/cite-show <citation_id>` — show NotebookLM-style evidence for a citation
- `/cite-find <claim>` — find candidate citations for a claim

### Data analysis
- `/discover-data <path>` — LLM-driven data discovery + summary
- `/analyze "<question>"` — orchestrated data analysis (LLM picks tools, runs pipeline, returns results)
- `/marker-interpret` — interpret cluster markers
- `/cluster-annotate` — annotate clusters via LLM + KB knowledge
- `/qc-review` — automated QC red-flag review

### Figures
- `/figure-gen <recipe>` — render a figure from a recipe
- `/figure-suggest` — recommend recipes for current data
- `/figure-audit` — audit figure coverage + manifest verdict

### Manuscript
- `/manuscript-status` — manifest table for current manuscript
- `/manuscript-section <name> draft` — draft a section with verified citations
- `/manuscript-section <name> review` — review section with cite-watch + critic
- `/manuscript-export final` — strip evidence; produce submission-ready

### Slides (flagship)
- `/build-deck <topic> --intent <kind> --theme <name> --length <N>` — end-to-end deck generation
- `/paper-to-slides <doi>` — extract figures from a paper, build journal-club deck

### Multi-agent
- `/deep-think` — adversarial 3-agent review of a finding
- `/deep-think-ensemble` — multiple Methods Critics + Area Chair meta-reviewer
- `/synthesize` — cross-finding integration with narrative arc
- `/synthesize-reflect` — synthesize with self-refinement loop
- `/parallel-runs` — N independent investigations on same topic, then synthesizer
- `/pipeline-resume` — auto-queue Round N from prior Critic output
- `/brainstorm-figures` — figure plan before plotting
- `/narrate-finding` — KB Wiki/Concepts page for a finding
- `/lit-dive` — stateful literature deep-dive over paperclip corpus

### Pre-registration
- `/plan draft <topic>` — draft a pre-registration plan
- `/plan compare-to-actual <plan> <run>` — flag deviations as warnings

### Companion (life-context)
- `/brief` — daily morning briefing (calendar + emails + tasks + work log)
- `/prep <meeting>` — pre-meeting prep packet
- `/eod` — end-of-day summary; optionally send to PI via Teams
- `/weekly` — weekly summary from work log
- `/record-meeting <topic>` — start meeting recording (Windows + meeting_recorder)
- `/meetings recent|find|transcribe` — meeting transcript management

### Companion (Google + Outlook)
- `/update <description>` — log to Google Doc work log
- `/meeting-fetch` — pull recent meeting transcripts from Outlook/Teams

## v0.2.0 (post-v0.1.0)

- `/cross-model-judge` — cross-model adversarial review (different LLM checks current LLM)
- `/research-office-hours` — six forcing questions to reframe a research request before doing work
- `/learn capture <insight>` — explicit lesson archiving
- `/research-retro` — weekly research retrospective with metrics

## How to add a new slash command

1. Copy `templates/slash_command/` to `.claude/commands/<name>.md`
2. Fill in: description, inputs, outputs, implementation, test plan, type (pure capability vs orchestrated)
3. Run `vaultlab claude validate` (CI gate)
4. Smoke-test by invoking in Claude Code on a tiny test project

See [`templates/slash_command/README.md`](../../templates/slash_command/README.md).

## Conventions per AGENTS.md

- Pure capability commands call directly into one capability subpackage
- Orchestrated commands use `vaultlab.runner.bounded_loop` with internal verifiers
- Hedged voice + anti-laziness rules apply to every LLM call inside any command
- Provenance receipts written automatically for every output
