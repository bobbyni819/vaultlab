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

## The six core commitments (META PRINCIPLES)

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

### 6. Centralized memory is the flagship

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

### Build a slide deck for a topic

The 2026-05-03 Path-A architecture (Bobby's "use Claude as the brain" rule):

1. **DON'T** post-populate figures onto text-only slides. Generate `figure`
   slides directly with all four R3 elements baked in (title + figure +
   caption + citation_source).

2. **Use the helpers** — they reduce per-deck authoring burden 3-5×:

   ```python
   from vaultlab.research.notes_from_summary import (
       load_summary, speaker_notes_from_summary,
   )
   from vaultlab.research.figure_picker import pick_best_figure_for_doi
   from vaultlab.research.deck_cache import deck_decision

   # For a paper cited across multiple decks, get the cached decision
   d = deck_decision("10.1038_s41586-022-05672-3")  # Sorin 2023
   # → DeckDecision(doi, figure_path, speaker_notes, citation, cached_at)

   # OR fresh per-paper:
   record = load_summary("10.1038_s41586-022-05672-3")
   notes = speaker_notes_from_summary(record, hook="...", key_claim="...",
                                       transition="...")
   figure = pick_best_figure_for_doi("10.1038_s41586-022-05672-3")
   ```

3. **Slide-spec shape** for `figure` slides:

   ```python
   {
       "type": "figure",
       "title": "<descriptive sentence — e.g., 'Spatial neighbourhoods, "
                "not cell frequencies, predict LUAD survival'>",
       "image_path": str(figure_path),
       "caption": "<≤110 char single-line caption>",
       "citation_source": record.citation_footer(),  # 'Sorin et al. 2023 | Nature'
       "bullets": ["≤4 short bullets, ≤45 chars each"],
       "speaker_notes": notes,  # 3-tier: mental_map + script + extended_walkthrough
       "layout": "auto",  # or "figure_only" / "figure_above_bullets" — default auto-picks
   }
   ```

4. **Build + audit** in one call:

   ```python
   from vaultlab.slides.deck import build_from_plan
   from vaultlab.slides.audit import audit_deck

   result = build_from_plan(plan_dict, "out.pptx")
   # → result["pptx"], result["argument_graph"] (sidecar markdown)

   audit = audit_deck(result["pptx"])
   assert audit.severity == "ok"
   ```

5. **The argument-graph sidecar** (`<deck>.argument-graph.md`) is auto-
   written next to the deck. It lists every slide's hook / key_claim /
   transition so the speaker can audit logical flow without scrolling.

6. **Reference deck**: `Output/_demos/advisor-package-2026-04-30/car_t_30min_v13.pptx`
   built by `bobby-tools/scripts/generate_car_t_decks.py` is the gold-standard.

See `scripts/_rebuild_*_2026_05_03.py` for working examples of all four
deck patterns (multi-lung short/review + spatial-tx short/review).

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
