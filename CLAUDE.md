# CLAUDE.md — vaultlab architectural reference

> **Claude Code: read [`READ_FIRST.md`](READ_FIRST.md) BEFORE this file.** READ_FIRST is the action-oriented dispatch + role-pass + first-encounter cheat sheet that maps natural-language asks to the right vaultlab primitive. CLAUDE.md (this file) is the architectural philosophy behind those primitives — read it second, when you need to understand *why* a primitive is shaped a certain way or before changing one.

## First-encounter checklist (run this BEFORE any vaultlab call)

When Claude Code arrives at a project that uses vaultlab, run these three checks **before** invoking any slash command. Skipping them leaves the user staring at `ModuleNotFoundError` or `KbRootNotConfigured` from three layers deep — bad first impression.

```python
# 1. Importable?
try:
    import vaultlab  # noqa: F401
except ImportError:
    # Don't try to use vaultlab. Point the user at the bootstrap.
    print("vaultlab not installed. Run: pwsh scripts/bootstrap.ps1  (or bash scripts/bootstrap.sh)")
    raise SystemExit(1)

# 2. KB root resolvable?
from vaultlab.context import resolve_kb_root, KbRootNotConfigured
try:
    kb_root = resolve_kb_root()
except KbRootNotConfigured as exc:
    print(f"KB not configured. Run `vaultlab init` (default: {exc.suggested_default}).")
    raise SystemExit(1)

# 3. Project config? (only matters if cwd is INSIDE a project folder)
from vaultlab.onboarding import load_project_config_from_cwd
project_cfg = load_project_config_from_cwd()
# If None, the user hasn't onboarded yet. Suggest /onboard-me (natural-language path).
```

If any check fails:
- (1) failed → run `scripts/bootstrap.ps1` or `scripts/bootstrap.sh`
- (2) failed → `vaultlab init` (one-time, prompts for default KB root)
- (3) None → `/onboard-me` (natural-language) or `/onboard-project` (structured) or `/start-project "<topic>"` (topic-only)

This checklist is a **prose contract**, not an enforced precondition — every slash command currently does its own resolve-or-fail. The contract just shifts the failure mode from "import error in line N of orchestrator" to "human-readable next step."

## What vaultlab is

`vaultlab` is a **research companion** for biological scientists — an open-source capability layer for Claude Code that integrates literature search, citation verification, wet-lab data analysis, figure generation, manuscript drafting, slide deck creation, AND life-context (Google Docs/Sheets/Drive/Gmail/Calendar, Outlook on Windows).

**Companion mode, not autonomous mode.** vaultlab does NOT generate research questions in a vacuum, run robots, or submit papers. It accompanies the user through whatever they're actually doing today — analysis, drafting, lit review, deck-building — with full context of their work pulled from KB + Google + Outlook.

**Architecture philosophy:** capability layer FOR Claude Code, NOT a competing harness. Users invoke vaultlab via slash commands, CLI, or direct Python imports — Claude Code handles orchestration.

## Reading order to understand the system

When opening this repo, read in this order:

1. 📖 [`READ_FIRST.md`](READ_FIRST.md) — **dispatch + role-pass cheat sheet for Claude Code sessions.** What primitive to invoke for what natural-language ask, when to run `methods_critic` vs `rigor_auditor`, the first-encounter checklist. Read this first; everything else is reference.
2. 📖 [`README.md`](README.md) — what vaultlab is + how to install + 5-min demo (user-facing)
3. 📖 [`AGENTS.md`](AGENTS.md) — invariants and conventions (REQUIRED reading before any code change)
4. 📖 [`docs/architecture.md`](docs/architecture.md) — full architectural spec
5. 🛠️ Per-package READMEs in `src/vaultlab/<package>/README.md` (when working on that package)
6. 🛠️ Per-role prompts in `src/vaultlab/roles/<role>/prompt.md` (when working on agent roles)
7. 🛠️ Per-recipe docs in `src/vaultlab/figures/recipes/<recipe>.md` (when adding figures)
8. 📖 Slash command definitions in `.claude/commands/*.md` (when invoking features)

Legend: 🛠️ = read + edit if applicable. 📖 = read only.

## Dispatch + role-pass discipline

The actionable how-to (what primitive for what ask, which role pass before shipping which doc type) lives in [`READ_FIRST.md`](READ_FIRST.md), not here — single source of truth. Two rules summarized for the reader who only opens this file:

1. **Dispatch first, doc-write second.** When the user asks for literature / data analysis / figure work, default to the primitive (`/lit-arc`, `plan_deep_think_round`, `vaultlab.figures.recipes.*`, `methods_critic`) before reaching for free-form markdown. Free-form docs are the fallback, not the default.
2. **Role pass before ship.** Methodology doc → `rigor_auditor`. Novelty / ranking claim → `methods_critic`. Manuscript paragraph → both, sequentially. The pass output saved to `<kb>/Output/<project>/` IS the audit trail.

Skipping these is the single biggest quality leak in the harness — see `Sources/Notes/friction-findings-from-metabolism-run-2026-05-05.md` (KB) for nine concrete ways this went wrong during the dogfood run.

## The nine core commitments (META PRINCIPLES)

These are non-negotiable. Every architectural decision serves them.

### 1. Markdown is the user-facing interface; Python is the engine

Slash commands, role prompts, workflow descriptions, skills, recipe docs, layout templates — all are markdown files. **If you find yourself writing a triple-quoted prompt in a `.py` file, that's a bug — the content goes in a sibling `.md`.**

### 2. Anti-laziness on semantic reading

Every LLM call must REQUIRE quoted evidence. Surface-skim is the enemy. Multi-pass reading for complex tasks. Hedged voice always — *"consistent with X"* never *"is X."*

### 3. Result-oriented agentic loop

User says *"draft methods"* → vaultlab plans + runs internal meetings/critiques/verifications → returns finished result. Bounded loop (max 3 iterations) with internal verifiers (citation, numeric, cross-doc, hedge enforcement).

### 4. KB is the smartness

Every analysis writes to KB; every analysis reads from KB. Cross-project reasoning emerges via retrieval. The LLM gets smarter project-by-project as the KB grows.

### 5. Async-first feedback loop

VaultLab keeps working rather than blocking the user with mid-flight questions. Open questions, design decisions, and clarifications go into **markdown documents in the KB** — not chat. The user reads them at their leisure (Obsidian opens via `bobby-kb open <path>`) and either edits the file or replies referencing it.

**The four channels:**
1. **`START_HERE.md` per project** — auto-maintained current state.
2. **`grill-<topic>-<date>.md`** — numbered open-question docs when N+ decisions are pending.
3. **`decisions-log.md` per project** — append-only record of design/scope decisions.
4. **Chat** — reserved for *immediately blocking* events only.

**Where blocking confirmation IS still required:**
- Destructive actions (delete, force push, send email, post to external services)
- IRB / PHI / compliance gates
- Cost-tier escalation (single LLM call > configured threshold)

**Parallel decomposition:** complex workflows fan out into parallel sub-workflows automatically (subagents, concurrent tool calls). The user does not orchestrate parallelism by hand.

**End every turn with one line:** if a grill doc, decisions-log entry, or START_HERE update was written, surface it as `bobby-kb open <path>` so the user can read it on their schedule.

### 6. Additive over user state, with maximum context

Every vaultlab primitive READS existing KB state before writing. Defaults to extending existing artifacts (arcs, figures, decks, analyses, audits) rather than redoing them. Pulls FULL context on every invocation — literature summaries, project state, prior decisions, recent commits, code-file structure, data-file schemas — even when the task seems narrow.

**Two complementary disciplines:**

1. **Additive operations.** A user invoking `/lit-arc cancer spatial` for the second time after a prior run should get an EXTENSION of the existing corpus, not a redo. A user asking for a marker dot-plot when one exists should get a VARIANT linked to the prior, not a duplicate. The state-aware defaults table in `READ_FIRST.md` Step 3.5 documents the branching: `--fresh` / `--extend` / `--branch` / `--query-existing` / `--variant`.

2. **Maximum context per invocation.** Even when the task is "refactor this script" — which seems literature-orthogonal — the primitive scans `<kb>/Wiki/Summaries/` for any paper that mentions a relevant analytical pattern, scans `<project>/decisions-log.md` for prior conventions, scans recent commits for related work. Side context surfaces unique vaultlab value: *"Your manuscript draft references this function; Schurch 2020 uses a similar pattern."*

**Implementation rule:** every artifact-producing primitive (`run_lit_arc`, `build_deck`, `figure_from_data`, `plan_deep_think_round`, `cite_audit`, `code_review`, `eda`) starts with a `state_aware_preflight()` call that returns the cross-domain context. The primitive's mode (`--fresh` / `--extend` / etc.) is then a function of that state, not a user-supplied default.

**Anti-pattern to avoid:** stateless primitives that fan out work without checking what's already in the KB. The metabolism dogfood run hit this — friction #3 (resolver picked default KB), friction #7 (collaborator commits silently missed), and the core dispatch failure mode (writing a free-form doc when an existing concept doc covered the question) all trace to "didn't read state first."

### 7. Context preservation invariant (sessions never zero-shoot)

**No vaultlab session re-starts from zero.** Every Claude Code session that touches a vaultlab project must, before answering the user's first task, glob the project's KB directory and report what relevant prior work exists. If nothing is reported, that's a bug — refuse to proceed until the agent confirms the glob ran. The KB IS the persistence layer; there's no in-memory state to lose.

**Required reads on session start:**

1. `<kb>/<project>/START_HERE.md` — daily brief, newest day on top. Tells the agent what was happening, what's blocked, what to do next.
2. `<kb>/<project>/decisions-log.md` — append-only design + scope decisions. Tells the agent which methods are already canonical (e.g., *"we use spearman after Round 8"*).
3. `<kb>/<project>/Output/` glob — what artifacts already exist for this project's topic.
4. `<kb>/Wiki/Concepts/<related-topics>` — concept docs that may overlap the current ask.
5. **For collaborative projects:** `git log <branch>..origin/<base> --since='14d'` — what commits other authors pushed since the last session.

**Required reads on every artifact-producing primitive** (per READ_FIRST.md Step 3.5): glob the canonical output paths for prior runs on the same topic + branch on state (`--fresh` / `--extend` / `--branch` / `--query-existing` / `--variant`).

**For spawned sub-agents:** when an orchestrator spawns analyst / critic / synthesizer sub-agents (via `plan_deep_think_round`, `plan_ensemble_critic`, etc.), the system prompt for each MUST include:
- The relevant KB excerpts (per-paper Tier-A summaries, decisions log, prior concept docs) loaded as context
- The explicit instruction *"this is what the project has already done; do NOT redo it; build on it"*
- The output schema so the sub-agent's work feeds back into the KB cleanly

**Anti-pattern to refuse:** any sub-agent invocation whose system prompt is just the role's task description without the KB context preamble. That's the path to "the agent suddenly forgot all about the previous work" — Bobby's stated worst-case. Refuse to invoke until the preamble is present.

### 8. Methods are lifted from accredited published work, never invented

**vaultlab's value comes from disciplined orchestration of established methods, not from novel techniques.** When implementing any new orchestrator, primitive, or recipe, the rule is:

1. **Identify the published source first.** What paper / well-tested OSS project / prior gstack-style harness did this pattern? Cite it.
2. **Document the lineage explicitly.** New module → entry in `INSPIRATIONS.md` with `CODE` / `PATTERN` / `CONCEPT` / `TOOL` classification. New recipe → `<recipe>.md` cites ≥3 anchor papers. New role → `roles/<name>/prompt.md` cites the original methodology.
3. **If you can't cite a source, that's a smell.** Means we're either re-inventing or operating outside the discipline. Either find the source or flag it for design review.

**Established sources we draw from:**

| Pattern | Source | Where it lives in vaultlab |
|---|---|---|
| Multi-agent meeting (analyst → critic → synthesizer + bounded loops + structured-JSON-only) | virtual-lab (Swanson et al., *Nature* 2025; Zou group, Stanford) | `runner/meetings.py`, `workflows/crosstalk.py` |
| Plan → execute → verify → refine inner loop with reflection-round caps | AI-Scientist (Sakana AI) | `runner/reflection.py`, `workflows/deep_think.py` |
| Wiki-grows-with-work + LLM-maintains-the-wiki | Karpathy's LLM Wiki gist | `kb/`, `Wiki/Concepts/`, `Wiki/Summaries/` |
| Per-paper grounded summaries with `[pN]` page-marker citations | PaperQA2 (FutureHouse) | `research/summarize.py` |
| Hover-to-see-quote citation UX | NotebookLM (Google) | `citations/` |
| Multi-source literature search + cross-source dedup | paperclip-MCP, scverse practice | `research/sources/`, `research/unified_search.py` |
| Recipe library — figures with cited published examples | scverse / scanpy gallery, bioconductor vignettes, squidpy | `figures/recipes/` |
| Markdown-as-instruction-files Claude Code skill bundle | gstack (Garry Tan) | `.claude/commands/`, `roles/<name>/prompt.md` |

When you build something new, this table grows by one row. Refuse to ship a new orchestrator without an `INSPIRATIONS.md` entry.

**Why this matters for adoption:** the PI's 2026-05-06 framing was *"helping with analysis and coming up with literature review, figures and image understanding"* — and a lab member trying vaultlab needs to be able to TRUST the methods. *"Why use vaultlab's lit-arc instead of writing it yourself?"* gets the answer: *"Because the picker uses the same content-aware ranking pattern from virtual-lab, the multi-agent crosstalk is bounded by the protocol from AI-Scientist, the citation grounding mirrors PaperQA2 + NotebookLM. Each piece has a track record elsewhere; vaultlab is the integration."*

### 9. Centralized memory is the flagship

What separates VaultLab from PaperQA / scanpy / FutureHouse / scverse / Aider is the unified memory layer. Six channels stitched into one place the LLM reads:

1. **Knowledge base** (Obsidian markdown — `Sources/`, `Wiki/`, `Output/`)
2. **Meeting transcripts** (local-Whisper or cloud → auto-ingested into KB)
3. **Inbox + calendar + work log** (Outlook / Gmail / Google Calendar / lab Google Doc work log)
4. **Local files** (anything Claude Code can `Read()`)
5. **Project state files** (`START_HERE.md`, `decisions-log.md`, grill docs)
6. **Per-user locations registry** (`~/.config/vaultlab/locations.toml` — the index that lets all six channels find each other)

When extending VaultLab, every new feature must answer: *"How does this read from / write to centralized memory?"* If a feature only operates on its own private state, that's a smell.

## Top-level structure

```
src/vaultlab/                       # The package
  __init__.py                       # Slim barrel (~10 symbols)
  cli/                              # CLI entry point — one .py + .md per subcommand
  meetings.py                       # Meeting, Agenda, Mode, Role
  roles/<role>/{role.py, prompt.md} # Agent role definitions
  runner/                           # ClaudeCodeRunner, bounded_loop, verifiers
  workflows/                        # Multi-agent workflow types (one .py + .md per type)
  research/                         # Literature: papers + sources + paperclip + smart_search + extract
  citations/                        # NotebookLM-style citation verification
  kb/                               # Knowledge base + Obsidian setup + ingest + semantic search
  figures/                          # Construction from your data: panel, collage, recipes, corpus
  slides/                           # Deck generation (FLAGSHIP): layouts, themes, understand, annotate
  manuscript/                       # ManuscriptProject; markdown-persisted state
  data/<modality>/                  # Wet-lab data: codex, maldi, scrnaseq, spatial, imaging, flow
  stats/                            # Statistical wrappers (scanpy/scipy/statsmodels with hedged voice)
  plan/                             # Pre-registration drafting
  evaluate/                         # Benchmarks: hallucinations, cluster_naming, figure_captions
  context/                          # Research-companion CONTEXT pipes (NEW for companion mode):
    google/                         #   Google Workspace — Docs, Sheets, Drive, Gmail, Calendar (cross-platform)
    outlook/                        #   Outlook Classic — email, calendar, contacts, tasks (Windows-only)
  patterns.py                       # EvidenceBundle, CascadeWatchdog
  provenance/                       # Per-output provenance receipts
  parsers/                          # LLM output parsing
  status/                           # /research-status implementation
  config/                           # ProjectConfig, .vaultlab-project.json loading
  context/                          # RAG context assembly
  errors/                           # retry, degraded, llm_recover decorators
  prompts/                          # Prompt loader
  observability/                    # rich progress + JSONL trace
  cache/                            # Content-addressable caches

.claude/                            # Ships with the repo
  commands/*.md                     # Slash commands
  skills/vaultlab/*.md              # Skill bundle (auto-loaded by Claude Code)

docs/                               # Browsable on GitHub; openable in Obsidian
examples/{pbmc3k,visium_brain,codex_hubmap_tonsil}/  # Case studies
templates/                          # Contributor scaffolds
tests/                              # pytest

.vaultlab-project.json              # Per-project config (NOT committed for individual projects;
                                    #  this repo's own version stays committed)
```

## Common tasks

### Add a new figure recipe
1. Copy `templates/recipe/` to `src/vaultlab/figures/recipes/<new_recipe>/`
2. Fill in `<new_recipe>.py` (Python implementation) and `<new_recipe>.md` (description + ≥3 paper references)
3. Add the recipe's `corpus/sources.json` entry under the recipe name
4. Add a unit test in `tests/test_vaultlab_figures/`

### Add a new agent role
1. Copy `templates/role/` to `src/vaultlab/roles/<new_role>/`
2. Fill in `role.py` (thin loader) and `prompt.md` (the actual prompt content)
3. Register in `vaultlab/roles/__init__.py`
4. Add to `tests/test_vaultlab/test_role_invariants.py`

### Add a new slash command
1. Copy `templates/slash_command/` to `.claude/commands/<new-command>.md`
2. Fill in: description, inputs, outputs, implementation, test plan
3. Run `vaultlab claude validate` to lint

### Add a new data modality
1. Copy `templates/data_modality/` to `src/vaultlab/data/<new_modality>/`
2. Fill in: ingest, qc, processing modules + sibling `.md` docs
3. Add tests in `tests/test_vaultlab_data/`

## Best-practice rules for Claude Code sessions on this repo

These are non-obvious rules that prevent confusing failure modes. Follow them.

### One KB per chat session

Don't talk about multiple knowledge bases / projects in the same Claude Code chat. vaultlab's context retrieval scopes to the default KB; mixing causes the LLM to conflate findings from different projects.

If a user wants to switch projects mid-chat, suggest opening a new chat. If they insist, use `vaultlab kb switch <name>` and announce the switch explicitly.

### One project per `.vaultlab-project.json`

Every research project gets its own config + KB folder. If a project has multiple manuscripts (main paper + methods companion), use the `manuscripts:` field in the config; do NOT create one config covering multiple projects.

### Auto-update START_HERE on meaningful work

After completing a meaningful task (rendering a figure, drafting a section, running an analysis pipeline), call `vaultlab.kb.start_here.update_start_here(slug, activity, files_to_read_next=...)` so the project's START_HERE.md stays current. Bobby never manually edits it.

### Hedged voice is a feature, not a bug

If you (Claude) catch yourself writing *"X is Y"* in scientific output, stop and rewrite as *"X is consistent with Y"* or *"data are compatible with Y"* (see AGENTS.md). Don't ship overclaimed conclusions.

## What to NOT do

- Do **not** embed prompts as triple-quoted strings in Python (META PRINCIPLE #1)
- Do **not** add fields to `.vaultlab-project.json` schema without versioning (forward-compat)
- Do **not** change role identifiers (prompts can change; identifiers cannot)
- Do **not** use unhedged voice in LLM-generated outputs
- Do **not** introduce a new top-level package without justification (high bar; see `AGENTS.md`)
- Do **not** create new top-level files at the repo root without a clear reason
- Do **not** commit `.h5ad`, `.tiff`, `.zarr/`, generated `Output/` artifacts (see `.gitignore`)

## Testing

```bash
pytest tests/                              # all tests
pytest tests/test_vaultlab_research/       # one subpackage
pytest tests/test_vaultlab/test_role_invariants.py  # specific test
pytest -m "not llm"                         # skip tests that hit a real LLM API
```

## Architecture grill (design history)

The full design rationale lives at `G:/My Drive/Knowledge/vaultlab/Sources/Notes/architecture-grill-2026-04-26/` (KB renamed from `ailab` on 2026-04-28). The master plan is `99-MASTER-PLAN-vaultlab-shared-design.md`. Read these only when wanting to understand WHY a decision was made; for normal coding, this CLAUDE.md + AGENTS.md is enough.

## Per-user auto-memory

VaultLab has a per-user memory layer at `~/.config/vaultlab/user_memory/`. When the user gives important feedback or VaultLab learns a non-obvious calibration that should persist across sessions, write it via `vaultlab.context.user_memory.remember(category, name, description, content)`. Future sessions read it back so the system inherits prior tuning instead of relearning each chat.

**At the start of any non-trivial session, check the index:**

```python
from vaultlab.context.user_memory import recall_all
index_text, _ = recall_all()  # the always-loaded summary
```

The `MEMORY.md` index is one line per memory; dive into specific entries when relevant.

**Categories:**

- `feedback` — corrections + confirmations the user made. Lead with the rule, then `**Why:**` and `**How to apply:**`.
- `preference` — workflow / style choices.
- `pattern` — design decisions that worked, reusable in similar contexts.
- `project` — project-specific calibration.

**When to write:** any time the user corrects or confirms in a way that's non-obvious from the code. Save what is applicable to future conversations.

**When NOT to write:** ephemeral task state (use `START_HERE.md`); code patterns derivable from the repo (read it instead); anything the user explicitly asks to forget.

## When in doubt

When in doubt, read `AGENTS.md` for invariants. When AGENTS.md doesn't cover it, consult the architecture grill master plan. When that doesn't cover it either, write a grill doc via `vaultlab.kb.feedback.open_question` (Invariant 10) and proceed with sensible defaults — don't block the chat.
