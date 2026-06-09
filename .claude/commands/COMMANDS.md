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
- `/onboard-me [path] [-- "<freeform>"]` — natural-language onboarding (paste any description; vaultlab parses)
- `/onboard-project [path]` — structured-Q&A onboarding for an existing project folder
- `/start-project "<topic>"` — topic-only scaffold; no folder, no questions
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
- `/figure-audit <figure-path> "<claim>"` — **Built.** Semantic figure-vs-claim verifier (SUPPORTED/PARTIAL/UNSUPPORTED/FABRICATED + evidence anchors). Discrete reviewer-invoked path; not the inline /lit-arc pass. Backed by `vaultlab.figures.verify_semantic`.
- `/figure-coverage` — _Placeholder (unbuilt)._ Audit figure coverage + manifest verdict (does every expected figure exist; is the manifest complete). Displaced from the old `/figure-audit` slot when the semantic verifier took that name.

### Manuscript
- `/manuscript-status` — manifest table for current manuscript
- `/manuscript-section <name> draft` — draft a section with verified citations
- `/manuscript-section <name> review` — review section with cite-watch + critic
- `/manuscript-export final` — strip evidence; produce submission-ready
- `/polish <manuscript-path>` — 25-rule prose polish + 12-step workflow (v0.0.4)
- `/respond <reviewer-block>` — point-by-point response letter scaffolding (v0.0.4)
- `/das-audit <text-or-manuscript>` — Data Availability statement audit + FAIR check (v0.0.4)

### HTML output (v0.0.4)
- `/audit-html <input>` — universal dispatcher: render any deck-audit / lit-arc / reasoning chain / citation audit / dossier as HTML
- `/preview-deck <plan-or-pptx>` — keynav HTML preview (arrow keys, inline-base64 figures, no PowerPoint needed)
- `/reorder-slides <plan>` — drag-drop slide reorder editor; export new ordering as JSON
- `/journal-club <doi-or-summary>` — paper-type-aware journal-club deck (en + zh-CN)
- `/figure-contract "<conclusion>"` — figure-contract before plotting (conclusion → evidence chain → archetype → backend → export)

### v0.0.5 primitives exposed as slash commands
- `/full-reader <paper-source>` — bilingual figure-aware paper.md reader (DOI / paperclip-ID / PDF / arXiv ID / URL) with stable anchor IDs (S/C/F/T)
- `/run-analysis <project-dir>` — vaultlab.analysis pipeline; tidy CSV/Parquet → stats + figures + methods.md + provenance receipts
- `/state-dashboard <state-md-or-json>` — render a project state doc as an HTML dashboard (Pattern #16 + #6 + #15 composed)
- `/review-deck <pptx-path>` — unified slide self-review (font / overlap / descriptive-title / story-arc) with critical-first HTML report
- `/triage-citations <citations-json>` — drag-drop citation triage kanban (Accept / Reject / Needs review / Flag for plagiarism)

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

### Cross-project + workflow orchestrators (NEW v0.0.3)
- `/find-analogs <concept>` — cross-project pattern recognition; structural analogs across all KBs (lifts virtual-lab multi-agent meeting + Karpathy LLM Wiki cross-link)
- `/next-analysis [hint]` — "what should I do next" — project-state-aware deep-think round (lifts AI-Scientist plan-execute-verify + virtual-lab 4-role meeting)
- `/debug <traceback>` — multi-agent debug round, auto-logs lesson to decisions-log (virtual-lab + AI-Scientist verifier-driven termination)
- `/code-review <file-or-author>` — rigor_auditor pass + decisions-log convention check + drafted feedback message (PaperQA2 grounding + gstack review checklist)
- `/explore-data <file>` — pure EDA via 4-role meeting + auto-lit-pointer for top finding (virtual-lab + scanpy/squidpy EDA conventions + PaperQA2)
- `/demo [topic]` — live narrated end-to-end demo with 5-min wall-clock target + pre-cached fallback (gstack live-demo pattern + AI-Scientist bounded loop)

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
