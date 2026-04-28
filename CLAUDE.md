# CLAUDE.md — vaultlab repo entrypoint

This file is the first thing Claude Code reads when opening the vaultlab repo. Treat it as the source of truth for how to navigate, modify, and extend vaultlab.

## What vaultlab is

`vaultlab` is a **research companion** for biological scientists — an open-source capability layer for Claude Code that integrates literature search, citation verification, wet-lab data analysis, figure generation, manuscript drafting, slide deck creation, AND life-context (Google Docs/Sheets/Drive/Gmail/Calendar, Outlook on Windows).

**Companion mode, not autonomous mode.** vaultlab does NOT generate research questions in a vacuum, run robots, or submit papers. It accompanies the user through whatever they're actually doing today — analysis, drafting, lit review, deck-building — with full context of their work pulled from KB + Google + Outlook.

**Architecture philosophy:** capability layer FOR Claude Code, NOT a competing harness. Users invoke vaultlab via slash commands, CLI, or direct Python imports — Claude Code handles orchestration.

## Reading order to understand the system

When opening this repo, read in this order:

1. 📖 [`README.md`](README.md) — what vaultlab is + how to install + 5-min demo
2. 📖 [`AGENTS.md`](AGENTS.md) — invariants and conventions (REQUIRED reading before any code change)
3. 📖 [`docs/architecture.md`](docs/architecture.md) — full architectural spec
4. 🛠️ Per-package READMEs in `src/vaultlab/<package>/README.md` (when working on that package)
5. 🛠️ Per-role prompts in `src/vaultlab/roles/<role>/prompt.md` (when working on agent roles)
6. 🛠️ Per-recipe docs in `src/vaultlab/figures/recipes/<recipe>.md` (when adding figures)
7. 📖 Slash command definitions in `.claude/commands/*.md` (when invoking features)

Legend: 🛠️ = read + edit if applicable. 📖 = read only.

## The four core commitments (META PRINCIPLES)

These are non-negotiable. Every architectural decision serves them.

### 1. Markdown is the user-facing interface; Python is the engine

Slash commands, role prompts, workflow descriptions, skills, recipe docs, layout templates — all are markdown files. **If you find yourself writing a triple-quoted prompt in a `.py` file, that's a bug — the content goes in a sibling `.md`.**

### 2. Anti-laziness on semantic reading

Every LLM call must REQUIRE quoted evidence. Surface-skim is the enemy. Multi-pass reading for complex tasks. Hedged voice always — *"consistent with X"* never *"is X."*

### 3. Result-oriented agentic loop

User says *"draft methods"* → vaultlab plans + runs internal meetings/critiques/verifications → returns finished result. Bounded loop (max 3 iterations) with internal verifiers (citation, numeric, cross-doc, hedge enforcement).

### 4. KB is the smartness

Every analysis writes to KB; every analysis reads from KB. Cross-project reasoning emerges via retrieval. The LLM gets smarter project-by-project as the KB grows.

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

## When in doubt

When in doubt, read `AGENTS.md` for invariants. When AGENTS.md doesn't cover it, consult the architecture grill master plan. When that doesn't cover it either, ask Bobby — and update one of these docs with the answer so future you (or future Claude) doesn't ask twice.
