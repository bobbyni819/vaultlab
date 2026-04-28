# Inspirations and intellectual lineage

**Last updated:** 2026-04-28 (initial scaffold; Bobby fills as he goes)

vaultlab is built on the shoulders of many open-source projects. This document is the auditable record of what we drew from where, distinguishing:

- **CODE** — actual source code copied / adapted (line-for-line) into vaultlab
- **PATTERN** — architectural pattern adopted, not source-code
- **CONCEPT** — design idea or framing influence, no implementation lineage
- **TOOL** — package wrapped (acknowledged dependency, not modified)

When a vaultlab function is informed by an external source, this document is the place that records it. Per AGENTS.md, every recipe and role should also cite its lineage in its sibling `.md` doc; this file aggregates those citations.

## How to use this document

When you add a new module, recipe, role, or workflow to vaultlab, ask:
1. Did I look at any external repo to figure this out?
2. Did I copy any code, even with modifications?
3. What architectural pattern did I adopt and from where?

Add an entry below per source you consulted. Include:
- **What was taken** — be specific (e.g., "the bounded_loop pattern with internal verifiers from gstack /review architecture")
- **How** — `CODE` / `PATTERN` / `CONCEPT` / `TOOL`
- **Where** — file path(s) in vaultlab where the inspiration shows up
- **License compatibility** — confirm the source's license is compatible with vaultlab's MIT (most are; AGPL/proprietary need careful handling)
- **Attribution form** — how the source is credited (in this file, in the file's docstring, in the recipe `.md`, in CITATION.cff)

## Honest principle

If we copied 50 lines from someone, say so. If we read their README and got an idea, say so. The integrity of the project depends on accurate lineage. *No silent borrowing.*

---

## Multi-agent orchestration / meetings

### virtual-lab (Zou group, Nature 2025)

- **Repo:** https://github.com/zou-group/virtual-lab (Bobby has fork: `bobbyni819/virtual-lab`)
- **Citation:** Swanson et al., *Nature* 2025, "The Virtual Lab"
- **License:** MIT (verify in repo)
- **What we took:**
  - Multi-agent meeting structure: meetings with structured agendas, team lead + team members, individual meetings with Scientific Critic, parallel-merge pattern.
  - **Temperature control across phases** — separate creative (high-T discovery) phases from convergence (low-T merge) phases.
  - **Sequential refinement with explicit prior_context** — each meeting outputs a `prior_context` summary that feeds the next meeting. Cumulative knowledge across phases.
- **How:** `PATTERN` — adapted into `vaultlab.meetings` and `vaultlab.runner.bounded_loop`. No code copied; reimplemented in Python with our own role taxonomy.
- **Where in vaultlab:** `src/vaultlab/meetings.py`, `src/vaultlab/workflows/`, `src/vaultlab/roles/`, file 02 in the architecture grill (master plan).
- **Files to drill into:** `nanobody_design/run_nanobody_design.ipynb` (meeting protocols), Agent class + temperature settings.
- **Attribution:** Cited in `src/vaultlab/__init__.py` docstring + `docs/architecture.md` + `bobby_ailab/README.md` (pre-rename).

### AI-Scientist (Sakana AI)

- **Repo:** https://github.com/SakanaAI/AI-Scientist (Bobby has fork: `bobbyni819/AI-Scientist`)
- **License:** Sakana Responsible AI License (NOT standard Apache 2.0 — has mandatory AI-disclosure clause; verify our usage is compatible since we adopt patterns only, not code).
- **What we took:**
  - Autonomous research patterns — `EvidenceBundle` numbered round structure, explicit reasoning loops with reflection.
  - **Role-based task distribution** — Researcher (idea + design) → Code (impl) → Writing (manuscript) → Review (critique). Vaultlab has named roles; this formalizes task delegation per role.
  - **Ensemble voting for critical decisions** — Aggregate 5+ independent LLM evaluations via voting (peer-review style). Inspires `vaultlab.decisions.ensemble_vote()` (planned for v0.2).
  - **Domain-specific templates as scaffolds** — `experiment.py`, `plot.py`, `prompt.json` per domain (NanoGPT, 2D Diffusion, Grokking). Inspires extending `vaultlab.figures.recipes/` with domain-specific bundles (oncology, immunology, neuroscience).
- **How:** `PATTERN` and `CONCEPT` — no code copied; concept-level influence only. License caution: their license has AI-disclosure terms that don't extend to our independent reimplementation.
- **Where in vaultlab:** `vaultlab.patterns.EvidenceBundle`, `vaultlab.runner.run_with_reflection`, `vaultlab.workflows.parallel_runs`, planned `vaultlab.decisions.ensemble_vote()`.
- **Files to drill into:** `ai_scientist/researchers/base_researcher.py` (task loop), `ai_scientist/templates/` (domain scaffolds), `ai_scientist/literature_retrieval.py` (fallback patterns), `ai_scientist/paper_generation/` (citation embedding).
- **Attribution:** docstring of `vaultlab.patterns` + `docs/architecture.md`.

### gstack (Garry Tan's Claude Code setup)

- **Repo:** https://github.com/garrytan/gstack (Bobby has fork: `bobbyni819/gstack`, locally cloned at `~/Downloads/gstack/`)
- **License:** TBD (check repo — likely MIT)
- **What we took (concept-level only):**
  - Sprint workflow framing (think → plan → build → review → test → ship → reflect) → adapted as research workflow
  - `/office-hours` six-question reframing pattern → `/research-office-hours` (planned for v0.2)
  - Cross-model second opinion (`/codex`) → `/cross-model-judge` (planned)
  - `/learn` persistent learnings → vaultlab KB Wiki/Concepts (already built differently)
  - Three-tier testing (static / E2E / LLM-judge) → already adopted in test plan
  - Fast-fail over self-healing → already in `vaultlab.runner.bounded_loop` philosophy
  - Auto-generated SKILL.md from code metadata → planned for `vaultlab claude validate --check-docs`
- **How:** `PATTERN` and `CONCEPT` — no code copied; concept-level influence only.
- **Where in vaultlab:** Future commits implementing the planned slash commands. Currently informs design grill files 22 + 10.
- **Attribution:** This file + `docs/architecture.md`. We do NOT use openclaw or hermes.
- **What we explicitly skipped:** Persistent Chromium browser daemon, design-* slash commands (UI-specific), GBrain Postgres/pgvector layer.

---

## Literature search and citation

### paperclip (Zou group / GXL-ai)

- **Repo:** https://github.com/GXL-ai/paperclip (Bobby has fork: `bobbyni819/paperclip`)
- **MCP service:** https://paperclip.gxl.ai
- **License:** Apache 2.0 (verify in repo)
- **What we took:**
  - Use of paperclip MCP as a literature backend — query + grep + map + reduce + lookup + sql + ask-image patterns.
  - **Grep-map-reduce paradigm** — three-tier query (grep corpus → map AI analysis → reduce to summaries). Make the reduce phase explicit in vaultlab rather than hiding in LLM calls.
  - **Virtual filesystem abstraction** — papers as `/papers/` with metadata + sections + figures as files. Adopt this framing for KB queries too (KB as virtual filesystem with wikilinks as joins).
  - **Source-specific ID prefixes** — `bio_`, `med_`, `PMC_` enable tracing citations to source. Vaultlab `Citation.source_id` should be `paperclip_bio_12345` / `arxiv_2401_05678` / `manual_upload_xyz`.
- **How:** `TOOL` (call as MCP) + `PATTERN` (grep-map-reduce; ID prefixes) — no code copied.
- **Where in vaultlab:** `src/vaultlab/research/sources/paperclip.py` (planned), `vaultlab.citations.Citation.source_id` schema enhancement.
- **Files to drill into:** `paperclip/mcp.py` or `server.py` (MCP integration), `paperclip/cli.py` (grep/map/reduce wiring), `meta.json` schema.
- **Attribution:** `vaultlab/research/sources/paperclip.md` + this file.

### PaperQA2 (FutureHouse)

- **Repo:** https://github.com/Future-House/paper-qa
- **License:** Apache 2.0
- **What we took:** Citation verification framing (the idea that LLM-generated citations need verification); RAG-over-papers pattern.
- **How:** `CONCEPT` — vaultlab's `bobby_citations` predates PaperQA2 in our codebase, but PaperQA2's framing of "verify before answer" influenced the multi-tier verification design.
- **Where in vaultlab:** `vaultlab.citations.semantic`, three-tier integrity rule in AGENTS.md.
- **Attribution:** `docs/comparison.md` (positions vaultlab vs PaperQA2 honestly).

### NotebookLM (Google)

- **Product:** https://notebooklm.google
- **License:** N/A (proprietary product; we drew CONCEPT only)
- **What we took:** Citation-evidence UX: hover-to-see-quote, click-for-source. Inline evidence visible in draft mode; stripped for final.
- **How:** `CONCEPT` — no code; design idea.
- **Where in vaultlab:** `vaultlab.citations.evidence.EvidenceRecord`, `vaultlab.manuscript.draft_mode_render` / `final_mode_render` (planned), file 04 in the architecture grill.
- **Attribution:** `vaultlab.citations.evidence.md` + this file.

---

## Wet-lab data analysis

### scanpy / squidpy / scverse (Theis lab + community)

- **Repos:** https://github.com/scverse/scanpy , https://github.com/scverse/squidpy
- **License:** BSD-3
- **What we took:** Wrapping (not modification) of all the canonical analysis: clustering, normalization, DE, spatial primitives.
- **How:** `TOOL` — vaultlab.data.scrnaseq + vaultlab.data.spatial wrap scanpy/squidpy via Python imports.
- **Where in vaultlab:** All of `src/vaultlab/data/scrnaseq/`, `src/vaultlab/data/spatial/`.
- **Attribution:** `pyproject.toml` dependencies; per-module docstrings cite scanpy/squidpy.

### Cellpose / StarDist / Mesmer

- **Repos:** https://github.com/MouseLand/cellpose , https://github.com/stardist/stardist , https://github.com/vanvalenlab/deepcell-tf
- **What we took:** Cell segmentation (wrapped, not modified).
- **How:** `TOOL`.
- **Where in vaultlab:** `src/vaultlab/data/codex/segment.py`.
- **Attribution:** Per-module docstring + tool index entry.

### Hickey lab — neighborhood/community/tissue analysis

- **Source:** Hickey lab internal patterns; see KB at `<kb>/Wiki/Methods/cellular_neighborhoods_hickey_lab.md`
- **Reference paper:** Schürch et al. 2020, *Cell* 182(5), https://doi.org/10.1016/j.cell.2020.07.005
- **What we took:** Cellular-neighborhood (CN) detection methodology with k-NN composition + clustering. Default parameters (k=10, n_clusters=10) match Hickey lab convention.
- **How:** `PATTERN` — implementing the published method via squidpy primitives.
- **Where in vaultlab:** `src/vaultlab/data/spatial/niches.py`.
- **Attribution:** Per-module docstring + sibling `.md` cites Schürch et al. + Hickey lab internal docs.

### Hickey lab — modality expertise (lab + collaborators)

vaultlab is positioned as research companion built **with** a spatial-omics specialty lab, not generic-tool-wrapper. Each modality module benefits from a lab-internal expert vaultlab can tap for refinement:

- **CODEX multiplex IF** — Nick + Young (lab members). Anchor for segmentation method choices, marker normalization conventions, panel-design awareness rules.
- **MALDI imaging** — Angela (Hickey lab collaborator). Ground-truth on lipid-class assignments + ion-image conventions.
- **Spatial transcriptomics** — Reina (lab member). Visium / Xenium / SpatialData workflow expertise.
- **Single-cell RNA-seq** — Bobby (primary) + others as tapped. scanpy + anndata canonical pipelines.
- **Generic imaging / flow cytometry** — TBD lab contact.

**How:** `PATTERN` (when implementing a new modality, draft a method choice → loop in the relevant lab member → adjust based on their experience). No code copied from any individual; the contribution is judgment + experience.

**Where in vaultlab:** Listed in README §"Specialized modules" + per-modality `.md` docs.

### Lab algorithm library (Nick's GitHub — TBD link)

- **Source:** Nick (Hickey lab member) has compiled an internal GitHub repository of data-analysis algorithms tuned for spatial-omics workflows. Repo URL pending Nick's approval to link publicly.
- **What we'll take:** When a vaultlab module needs an algorithm for a spatial-omics task that scanpy/squidpy don't cover well, vaultlab references Nick's repo — *"if your data looks like this, here's the validated algorithm."*
- **How:** `TOOL` (call) + `PATTERN` (the framing of "lab-validated algorithm beats generic default") — depends on what's in Nick's repo.
- **Where in vaultlab:** Will land as `src/vaultlab/kb/tools_index/lab_algorithms.md` once Nick approves sharing. Each algorithm referenced cites Nick's repo + the underlying papers.
- **Attribution:** Per-algorithm citation in the tools index + this entry.

**Action item:** Bobby to (a) get Nick's approval to link/reference the repo; (b) get the URL; (c) trigger a follow-up commit to populate `lab_algorithms.md`.

### CODEX_MALDIIMS — figure helpers

- **Source:** Bobby's own work at `~/Downloads/CODEX_MALDIIMS/lipid_annotations/ims_xgboost/figures/fig_style.py`
- **License:** N/A (Bobby's own code)
- **What we took:** Generic publication-styling helpers (rcParams, figure-size presets, palettes, style_ax, save_fig, save_legend).
- **How:** `CODE` — code adapted; project-specific palettes (lipid classes, cell types) deliberately left behind.
- **Where in vaultlab:** `src/vaultlab/figures/publication/{style,color,legend,save}.py` (commit `4ba6e2c`).
- **Attribution:** Each module's docstring records `Ported from CODEX_MALDIIMS/...`. This file. AGENTS.md.

### HuBMAP — public reference data

- **Source:** https://hubmapconsortium.org/
- **License:** CC BY 4.0
- **What we took:** Tonsil CODEX dataset for the flagship demo + cluster naming benchmark.
- **How:** `TOOL` — public dataset, used as-is.
- **Where in vaultlab:** `examples/codex_hubmap_tonsil/` , `tests/fixtures/cluster_naming_test_set.json`.
- **Attribution:** Example README + dataset license noted in download script.

---

## Tissue simulation / agent-based modeling (your other PhD thread)

### vivarium ecosystem (Bigraph project + tumor-tcell)

- **Repos:** Bobby has forks of `process-bigraph`, `bigraph-schema`, `bigraph-viz`, `vivarium-interface`, `spatio-flux`, `tumor-tcell` (locally cloned at `~/Downloads/tumor-tcell/`)
- **License:** Apache 2.0 (process-bigraph), MIT (tumor-tcell — verify)
- **What we took:**
  - **Typed shared state via schemas** — declared types per state location, deltas for updates, structural keys (`_add`, `_remove`, `_divide`) for runtime changes. Vaultlab wraps AnnData (already typed state); formalize as `vaultlab.data.state.TypedState` (planned v0.2) so multiple analyses (QC → clustering → DE) compose without colliding.
  - **Dependency-driven step networks** — steps compose via data dependencies, not direct calls. Enables parallel execution within a layer. Adopt for `vaultlab.pipeline` to compose figures + statistics + citations in parallel.
  - **Hierarchical process composition** — Process → Composite → Experiment hierarchy maps directly to scRNA-seq → clustering → annotation → DE. Formalize as `vaultlab.analysis.Composite` base class.
  - **From tumor-tcell specifically:** Multiplexed imaging initialization (read segmentation masks + protein expression → cell state vectors). Inspires `vaultlab.data.codex.initialize_simulation()` for users wanting to feed real CODEX data into ABM models.
  - **Behavioral state machines as processes** — explicit transitions documented as Process classes. Inspires framing every analysis result as a "state space" (clustering = state partition).
- **How:** `PATTERN` — no code copied; framework architecture inspires future modules.
- **Where in vaultlab:** Future `vaultlab.data.state.TypedState`, `vaultlab.analysis.Composite`. Currently `vaultlab.data.spatial.niches` uses a similar neighbor-composition pattern.
- **Files to drill into:** `process_bigraph/composite.py` (Composite base + wiring), `process_bigraph/core.py` (delta merging), `tumor_tcell/processes/t_cell.py` (state machine logic), `tumor_tcell/composites/` (composition examples), `tumor_tcell/experiments/main.py` (workflow_library), `tumor_tcell_model.ipynb` (visual documentation).
- **Attribution:** This file + future module docstrings when TypedState lands.

---

## Code-as-documentation philosophy

### Karpathy's nanoGPT / llm.c / micrograd / gpt2-pytorch

- **Repos:** https://github.com/karpathy/nanoGPT , https://github.com/karpathy/llm.c , https://github.com/karpathy/micrograd (Bobby has a fork: `bobbyni819/gpt2-pytorch` — likely Karpathy-derived)
- **License:** MIT
- **What we took:**
  - The fork-and-clone-as-primary-distribution philosophy (file 12 Q12.1 v2 — Hybrid C). Repo IS the documentation; code reads top-to-bottom.
  - **Code clarity over brevity** — verbose comments, domain-specific variable names. Vaultlab variable names should be `cluster_ids`, `expression_matrix`, NOT `x`, `y`.
  - **Pedagogical structure** — phases mirror "show all the work." Vaultlab's recipes/workflows should make every phase have visible outputs (figures, logs, KB updates).
- **How:** `CONCEPT` — design philosophy. No code or pattern copied.
- **Where in vaultlab:** Distribution model in README + `docs/architecture.md`; coding conventions in AGENTS.md.
- **Attribution:** This file.

---

## Code-generation pipeline + deterministic validation

### bobby_google + bobby_outlook (Bobby's own — predecessor in `bobby-tools`)

- **Source:** `~/Downloads/bobby-tools/src/bobby_google/` and `~/Downloads/bobby-tools/src/bobby_outlook/`
- **License:** Bobby's own (MIT-equivalent)
- **What we took:** The full API surface — Google Workspace integration (Docs/Sheets/Drive/Gmail/Calendar with OAuth) and Outlook COM automation (email/calendar/contacts/tasks).
- **How:** `CODE` — code will be lifted (not just adapted) into `vaultlab.context.google/` and `vaultlab.context.outlook/` in upcoming migration commits. Predecessor implementations remain in `bobby-tools` for personal-toolkit use; vaultlab gets the public-surface fork.
- **Why this lift:** vaultlab's "research companion" framing requires the LLM to have life-context — what's on calendar, what's in inbox, what's in the lab work log. Without these, vaultlab is a generic LLM chat. With them, vaultlab becomes a colleague who reads everything you've written.
- **Where in vaultlab:** `src/vaultlab/context/google/` (cross-platform), `src/vaultlab/context/outlook/` (Windows-only). Currently scaffold + `.md` docs; full code migrates next.
- **Setup docs:** `docs/setup-google.md`, `docs/setup-outlook-windows.md`.
- **Attribution:** This file + module docstrings + setup docs cite `bobby-tools` as predecessor.

### MultiAgent (Bobby's own work — local at `~/Downloads/MultiAgent/`)

- **Status:** Bobby's own multi-agent code-generation pipeline (collaborator: Faye does stages 1-3 bio decomposition + lit QA + BSS synthesis; Bobby does stages 4-5 reference analysis + code gen via 11 sub-phases).
- **License:** TBD (Bobby's own)
- **What we took:**
  - **Three-layer error defense for generated artifacts** — (1) prompt rules (`IMPORT_RULES_BLOCK` pattern that constrains output upstream), (2) deterministic AST-based fixers (38 of them in Phase 9), (3) LLM-powered repair (Phase 10). Vaultlab analog: `vaultlab.validate.{manuscript, figure, deck}_safety()` runs deterministic AST/schema checks BEFORE LLM repair. Catches 80% of issues without LLM cost.
  - **Biological System Specification (BSS) as canonical interface** — declarative YAML schema (metadata, cells, states, interactions, experiments) as the middle language between NL and code. Inspires `vaultlab.workflows.ExperimentSpecification` YAML for multi-dataset analyses (planned v0.2).
  - **Evaluation without LLM API keys** — 3,251 deterministic tests across 9 suites (file-structure accuracy, import-correctness, syntax-validation). Vaultlab should adopt: `vaultlab evaluate --no-llm` runs all the cheap deterministic checks; `--with-llm` adds the expensive LLM-judge passes.
  - **Multi-agent orchestration with sys.path isolation** — `phase2_generate_repo/orchestrator.py` clears module namespaces between agents to prevent cross-agent collisions. Worth knowing if vaultlab ever spawns parallel sub-agents.
- **How:** `PATTERN` — patterns adopted; no code copied.
- **Where in vaultlab:** `vaultlab.validate.safety` (planned), `vaultlab.workflows.ExperimentSpecification` (planned), `vaultlab.evaluate` (already in scope).
- **Files to drill into:** `code_repository_generation/pipeline/phase2_generate_repo/prompts/templates.py` (IMPORT_RULES_BLOCK pattern), `phase2_generate_repo/phases/phase9_repo.py` (38 deterministic fixers), `phase2_generate_repo/evaluation/metrics.py` (deterministic eval), `pipeline/orchestrator.py` lines 70-100 (namespace isolation).
- **Attribution:** Bobby's own work; cite as internal predecessor in `vaultlab.validate.__init__` docstring + this file.

### 2025_SpatialOmics (status: needs investigation)

- **Repo:** Bobby's fork at `bobbyni819/2025_SpatialOmics` — upstream parent unclear (gh API didn't return parent).
- **Status:** README + setup.py not found via raw.githubusercontent (404). Repo exists but contents not accessible without auth or with different default-branch.
- **Action:** Bobby to (a) confirm upstream repo name, (b) confirm whether the repo has novel methods worth lifting (community detection, cell-cell interactions, tissue region inference), (c) decide whether to migrate any to `vaultlab.data.spatial.advanced/`.
- **Provisional attribution:** placeholder in this file pending confirmation.

---

## Knowledge base / Obsidian integration

### Obsidian (Dynalist / Obsidian.md)

- **Product:** https://obsidian.md
- **What we took:** Markdown-as-canonical-knowledge-base philosophy. Wikilinks, frontmatter conventions, plugin ecosystem (Advanced URI, Dataview, Templater).
- **How:** `TOOL` — vaultlab targets Obsidian as the recommended GUI; KB is just markdown.
- **Where in vaultlab:** `src/vaultlab/kb/obsidian/`, `docs/setup-obsidian.md`.
- **Attribution:** docs.

---

## Things we explicitly did NOT borrow

This section preserves negative space — choices we made deliberately by NOT taking from somewhere.

| Source | Why we didn't take it |
|---|---|
| **gstack openclaw + hermes** | We're plain Claude Code skills + markdown; the plugin runtime layer adds complexity without v0.1 value. |
| **gstack design-* skills** | UI/UX design is software-specific; vaultlab handles figure-design via `recipes/` instead. |
| **PaperQA2's hosted service** | We're local-first; hosted is the explicit non-goal in file 12. |
| **AI-Scientist's full autonomous experiment runner** | We position as assistant (file 16); not autonomous experiment generation. |
| **Galaxy / Snakemake workflow runners** | Heavy external runtime; vaultlab uses Python orchestration via `vaultlab.runner.bounded_loop` instead. |

---

## Required attribution forms

Per AGENTS.md and OSS norms, every external influence is attributed in at least one of:

1. **`pyproject.toml`** — runtime dependencies (TOOL category)
2. **Module docstring** — for code adapted from a source (CODE category)
3. **Sibling `.md` doc** — for recipes/roles citing methods (PATTERN/CONCEPT)
4. **`CITATION.cff`** — academic citations (`preferred-citation` field for the preprint, plus `references` for foundational work)
5. **This file** — comprehensive aggregator

When you take from a source, make sure it appears in at least 2 of those (this file + one of the others, typically).

---

## Pending Bobby review

This document is a starting point. Bobby to:
- [ ] Confirm each entry's "What we took" is accurate
- [ ] Add any sources I missed (especially anything you've forked but I didn't see)
- [ ] Confirm license compatibility for sources marked TBD
- [ ] Decide on whether `CITATION.cff` should include the foundational works as `references` (recommend yes for virtual-lab + Schürch)
