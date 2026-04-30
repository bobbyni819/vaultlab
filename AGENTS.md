# AGENTS.md — Contributor invariants and conventions

This file defines the invariants every code change must preserve. **Read this before opening a PR.** When in doubt, the rules below override convenience.

vaultlab is in active alpha development; some invariants may evolve, but each change to AGENTS.md must be discussed in an issue before merging.

---

## Output routing conventions — where every artifact lives

Every VaultLab artifact has a documented canonical home. Agents and contributors do not invent paths, do not fall back to "wherever feels right," and do not silently overwrite work owned by other commands. The five rules below are the contract.

### 1. The principle — canonical paths only

Every output writes to a path returned by a helper in `src/vaultlab/kb/paths.py` (see the module docstring at `src/vaultlab/kb/paths.py:1-29`). **Never build path strings by hand.** Path-builders return `pathlib.Path` and do not `mkdir` — call `paths.ensure_parent(p)` (`src/vaultlab/kb/paths.py:370`) before writing.

The three-layer rule:

- `Sources/` — immutable inputs (raw PDFs, search-result stubs, manual notes)
- `Wiki/` — LLM-written content (per-paper summaries, cross-source concepts, project state)
- `Output/` — generated artifacts for delivery (slides, reports, run-id directories)

Full conventions reference: `G:/My Drive/Knowledge/vaultlab/Sources/Notes/kb-output-conventions-2026-04-29.md`.

### 2. The path matrix — artifact → canonical path → owner → frontmatter contract

Cite this matrix when wiring a new command or auditing an existing one. Every row's path is built by the named helper; every owner is the slash command (or onboarding step) that writes the artifact.

| Artifact | Canonical path | Helper (`vaultlab.kb.paths`) | Owner | Required frontmatter |
|---|---|---|---|---|
| Raw PDF | `Sources/Papers/<doi-slug>.pdf` | `pdf_path` (`paths.py:138`) | `/lit-arc`, `/lit-report` (Phase 5 acquisition) | n/a (binary) |
| Full-text markdown | `Sources/Papers/<doi-slug>.md` | `fulltext_md_path` (`paths.py:143`) | acquisition waterfall | `doi`, `title`, `source` |
| Article stub | `Sources/Articles/<doi-slug>.md` | `article_stub_path` (`paths.py:148`) | `/lit-arc`, `/lit-report` (Phase 3) | `doi`, `title`, `year`, `abstract` |
| Search session log | `Sources/Notes/lit-search-<query-slug>-<date>.md` | `search_log_path` (`paths.py:153`) | `/lit-arc`, `/lit-report` (Phase 2) | `topic`, `seeds_count`, `date` |
| Per-paper summary | `Wiki/Summaries/<doi-slug>.md` | `summary_path` (`paths.py:169`) | `/lit-arc`, `/lit-report` (Phase 6, via `summarize.write_summary_to_kb`) | `doi`, `tier`, `tldr`, `key_findings` |
| Lineage arc | `Wiki/Concepts/<topic-slug>-lineage-<date>.md` | `concept_path(..., kind="lineage")` (`paths.py:174`) | `/lit-arc` (Phase 7) | `topic`, `date`, `n_total`, `n_tier_a` |
| Deep-research report | `Wiki/Concepts/<topic-slug>-report-<date>.md` | `concept_path(..., kind="report")` (`paths.py:174`) | `/lit-report` (Phase 9) | `topic`, `date`, `audit_passed`, `audience` |
| Project landing page | `Wiki/Projects/<slug>/START_HERE.md` | `project_state_path` (`paths.py:198`) | `/onboard-project` (Phase 6); refreshed by `/lit-arc` (Phase 9) via `_safe_merge_start_here` | `schema: vaultlab-start-here/v1`, `managed_by`, `slug` |
| Project decisions log | `Wiki/Projects/<slug>/decisions-log.md` | `project_decisions_path` (`paths.py:209`) | `/onboard-project` (Phase 7); appended by every later command | `schema`, `slug` |
| Project intake copy | `Wiki/Projects/<slug>/intake.md` | `project_intake_path` (`paths.py:220`) | `/onboard-project` (Phase 5) | mirrored from `<project>/project_intake.md` |
| Project papers manifest | `Wiki/Projects/<slug>/papers.md` | `project_papers_path` (`paths.py:238`) | `/lit-arc` (Phase 9) | `schema`, `slug`, `last_run` |
| Project lineage pointer | `Wiki/Projects/<slug>/lineage.md` | `project_lineage_pointer_path` (`paths.py:255`) | `/lit-arc` (Phase 9) | `schema`, `slug` |
| Slide deck | `Output/<slug>/<deck-name>.pptx` | `deck_path` (`paths.py:282`) | `/build-deck` | n/a (binary; sidecars carry metadata) |
| Deck plan | `Output/<slug>/deck_plan.md` | `deck_plan_path` (`paths.py:296`) | `/build-deck` (currently unused; reserved) | `topic`, `target_slide_count` |
| Figure asset | `Output/<slug>/figures/<fig-id><suffix>` | `figure_path` (`paths.py:301`) | `/build-deck` | n/a (binary) |
| Citation evidence | `Output/<slug>/citations/<file-slug>.evidence.json` | `evidence_path` (`paths.py:318`) | `/cite audit` | n/a (JSON) |
| Run directory | `Output/<slug>/runs/<run-id>/` | `run_dir` (`paths.py:332`) | every orchestrator that runs a meeting | n/a (directory) |
| Per-turn role output | `<run-dir>/turn-<n>-<role-id>.md` | `turn_path` (`paths.py:347`) | `crosstalk.write_crosstalk_artifacts` | `role`, `round`, `meeting` |
| Meeting transcript | `<run-dir>/transcript.md` | `transcript_path` (`paths.py:360`) | `crosstalk.write_crosstalk_artifacts` | `meeting`, `mode`, `n_rounds` |
| Project config (cwd-side) | `<project>/.vaultlab-project.json` | (in `vaultlab.onboarding.config.save_config`) | `/onboard-project` (Phase 8) | schema `vaultlab-project/v1` |

If you need a path that isn't on this matrix, **add a helper to `vaultlab.kb.paths` first**, then use it. Do not hand-roll a path with the intent to "just this once."

### 3. The additive rule — no destructive writes without an explicit ask

Unless the user explicitly requested a destructive overwrite, agents APPEND, MERGE, or REFRESH-IN-PLACE. Defaults:

- **Append** to logs and journals (`decisions-log.md`, search logs).
- **Merge** new information into existing structure (e.g. add new papers to a corpus; do not rebuild).
- **Refresh-in-place** sections owned by the current run; preserve sections written by other commands.

The exemplar is `_safe_merge_start_here` in `src/vaultlab/research/lineage.py:679-796`. It detects when an onboarding-managed `START_HERE.md` is present (signals `managed_by: vaultlab.onboarding.project_init` or `schema: vaultlab-start-here/v1`, `lineage.py:673-676`) and instead of clobbering, appends or refreshes a single `## Lineage runs` section while preserving the onboarding-side body. New code that writes into shared files SHOULD follow this pattern: detect prior content, scope the write to the section the current command owns, and emit a provenance receipt that records `merged_with_onboarding: <bool>` (see `_safe_merge_start_here` lines 719-749 for the receipt-emit shape).

### 4. The provenance rule — every terminal artifact gets sidecars

Every terminal artifact (`.pptx`, lineage arc, report, `START_HERE.md`, etc.) writes BOTH:

- `<output>.provenance.json` — machine-readable receipt
- `<output>.method.md` — human-readable methods narrative

Both are produced by `vaultlab.provenance.write_receipts(output_path, ProvenanceRecord(...))` at `src/vaultlab/provenance/_writer.py:30-74`. The function also appends one line per write to `<dir>/.vaultlab-provenance.jsonl` for cheap "find all outputs matching X" queries (`_writer.py:108-119`).

Reference call sites:

- Lineage arc: `src/vaultlab/research/lineage.py:2008-2026` (`run_lit_arc` Phase 8)
- Deep-research report: `src/vaultlab/research/report.py:1357-1391` (`run_lit_report` Phase 10)
- Project START_HERE refresh: `src/vaultlab/research/lineage.py:719-749` (best-effort sidecar inside `_safe_merge_start_here`)

Receipts are best-effort metadata, never a hard gate — wrap the call in `try/except` and log via `logger.exception` if a write fails (see the lineage example at `lineage.py:744-749`). New orchestrators MUST add `write_receipts` calls for any terminal artifact they emit; bypassing this violates the AGENTS.md mandate (and is currently flagged as an open gap for the deck builder, per the pipeline-integration-map audit `F-6` in `G:/My Drive/Knowledge/vaultlab/Sources/Notes/pipeline-integration-map-2026-04-30.md`).

### 5. The state-check rule — read the KB before any LLM call

Every slash command's first action — before any LLM call, before any orchestrator invocation — is reading the relevant KB state at the canonical paths. The standard checks, in order:

1. **Project config (cwd-side):** walk `cwd → cwd.parent → ...` for `<project>/.vaultlab-project.json`. If found, `slug` and `kb_root` from it WIN over topic-derived defaults. (Today this handoff is convention-only — see pipeline-integration-map finding `F-1` — and orchestrator-side resolution is the recommended fix.)
2. **Prior project pages:** read `Wiki/Projects/<slug>/START_HERE.md` (`project_state_path`), `papers.md` (`project_papers_path`), and `decisions-log.md` (`project_decisions_path`). If present, the command treats them as authoritative state — additive merges only.
3. **Prior corpus:** read existing `Wiki/Summaries/<doi-slug>.md` files for the project's known DOIs. Re-running a command on the same project should fetch the delta, not rebuild.
4. **Prior arcs / reports:** check for `Wiki/Concepts/<topic-slug>-{lineage,report}-<date>.md`. Same-day reruns reuse the existing artifact unless the user asked for a fresh run.
5. **Last-run timestamp:** read the most recent `<output>.provenance.json` sidecar in the project's `Output/<slug>/` tree to learn what was generated, with what params, and how long ago.

If any of these reads fail (file missing, parse error), surface the gap as part of the command's preflight summary — don't silently fall through to a fresh-rebuild path.

---

## The eleven invariants

### Invariant 1 — Data-first Analyst

The `data_analyst` role MUST execute Bash/Python to load data before stating any finding. The prompt template includes the rule: *"Never describe data without loading it first."* Do **NOT** soften this rule.

### Invariant 2 — Adversarial vs Round-Table mode separation

Meeting modes have distinct execution semantics:
- `ADVERSARIAL` — roles run sequentially, each seeing prior outputs; later roles critique earlier ones
- `ROUND_TABLE` — roles run in parallel, blind to each other; outputs merged after

Do not blend these modes. Do not introduce a "hybrid" mode without explicit design discussion.

### Invariant 3 — KB-mediated summaries

Full transcripts go to `<kb>/Output/<project>/runs/<run_id>/`. Only **compact summaries** (max 2000 tokens) pass between agents in a meeting. The full transcript is the audit trail; the summary is the working state.

### Invariant 4 — ChainLink provenance

Every finding gets a ChainLink record for every agent turn that touched it. Only `record_meeting()` and `record_turn()` write ChainLinks — no other code touches them. This is foundational; do not bypass.

### Invariant 5 — Output routing split

- **Private reasoning** (intermediate findings, draft outputs, transcripts) → `<kb>/...` (Google Drive; private to user)
- **Final outputs** (publication figures, submitted manuscripts, finalized decks) → user-controlled output paths (often the project repo or Box folder)

The split is enforced by `vaultlab.config.ProjectConfig`.

### Invariant 6 — Role-mode consistency

`Mode.DATA_ANALYSIS` selects Analyst variants (`data_analyst`, `methods_critic`).
`Mode.LITERATURE_REVIEW` selects Surveyor variants (`literature_surveyor`, `literature_critic`).

Do not mix variants across modes. Each role has a documented `applicable_modes` field; tests in `test_role_invariants.py` enforce this.

### Invariant 7 — Markdown is the interface; Python is the engine

All prompts, role definitions, workflow descriptions, slash command bodies, and skill bundles are **markdown files** in the repo. Python contains: orchestration logic, data structures, runners, parsers, loaders. Python does NOT contain prompt content as embedded strings.

If you find yourself writing a triple-quoted prompt in a `.py` file, **stop** — the content goes in a sibling `.md`.

### Invariant 8 — KB ↔ repo boundary

- **Repo** holds: Python code, slash commands, skills, role prompts, tests, AGENTS.md, README.md, CLAUDE.md, per-package READMEs, `docs/`
- **KB** holds: papers, notes, wiki articles, summaries, generated outputs, manuscripts, figures, provenance, findings

Rule of thumb: if a file describes how vaultlab works, it goes in the repo. If a file is research output, it goes in the KB.

### Invariant 9 — Slash command layer pattern

Slash commands fall into two categories:

**Pure capability commands** — single-purpose; call directly into a capability subpackage. Examples: `/lit-search`, `/cite audit`, `/figure-gen`.

**Orchestrated commands** — multi-agent meetings or plan-execute-verify-refine loops. Use `vaultlab.runner` + `vaultlab.workflows`. Examples: `/research-pipeline`, `/deep-think`, `/build-deck`.

Bypass orchestration when one tool call answers the user's intent. Use orchestration when the intent requires multiple agent perspectives or iterative refinement.

### Invariant 10 — Async-first feedback loop

Open questions and design decisions go to **markdown documents in the KB**, not blocking chat questions. The four channels (in priority order):

1. `START_HERE.md` per project — auto-maintained current state.
2. `grill-<topic>-<date>.md` — numbered open-question docs when N+ decisions are pending.
3. `decisions-log.md` per project — append-only design/scope record.
4. Chat — reserved for *immediately blocking* events only.

Every command, role, or workflow that completes meaningful work MUST update at least one of channels 1–3. End-of-turn summary must surface unread KB docs as `bobby-kb open <path>` so the user can read on their schedule.

**Locked boundary (decisions made 2026-04-29):**

| Action | Blocking? |
|---|---|
| Sending email | ✅ Block — leaves the user's machine |
| Sending Teams / Slack / external chat message | ✅ Block — affects the user's reputation; "make you seem weird" |
| Appending to the work-log Google Doc | ❌ NOT blocking — that's the whole point of `/update`; documenting is fine |
| Writing to a NEW or existing KB markdown file | ❌ NOT blocking — log to `decisions-log.md` |
| Writing to a local file the user named | ❌ NOT blocking |
| Writing processed datasets to user's default cloud storage (Box / Drive) | ❌ NOT blocking when the destination is the user's existing data home |
| `restore_snapshot` / file deletion / force push / git reset --hard | ✅ Block (see Invariant 5 + `vaultlab.kb.snapshot`) |
| IRB / PHI / compliance-gate work | ✅ Block (regardless of cost) |
| **Cost gating** | ❌ NEVER block on cost — vaultlab assumes users have Claude Code subscriptions; runtime cost should not gate work |

**Parallel decomposition is unbounded.** Complex workflows fan out into as many parallel sub-workflows as the model + tools support. The user does not orchestrate parallelism by hand. The only constraint is that each parallel branch MUST do real semantic reading of its inputs, not surface-skim — Invariant 2 still applies.

### Invariant 11 — Pluggable adversary / judge model

The runner supports user-selected models for the adversary, judge, and verifier roles via `~/.config/vaultlab/models.toml`. Defaults are sensible (Claude family), but users MUST be able to plug in OpenAI, Gemini, local Llama, etc. without editing source.

`vaultlab.runner.judge_for(role)` returns the configured model handle. Role implementations call this — they do not hardcode `claude-sonnet-4-6` or any other identifier. `applicable_modes` and capability requirements (vision, long context, tool use) are declared in the role's `prompt.md` frontmatter so the config layer can warn on incompatible substitutions.

---

## Quality bars (enforced in CI + code review)

### Hedged voice for LLM-generated interpretations

When generating interpretations or hypotheses, vaultlab roles MUST hedge.

**Use:** *"consistent with"*, *"suggests"*, *"consider testing"*, *"may indicate"*, *"is compatible with"*, *"warrants further investigation."*

**Never use:** *"is"*, *"proves"*, *"demonstrates"*, *"shows that"*, *"we conclude."*

When confidence is low, say so explicitly: *"Confidence is low because [reason]."*

When sources are unavailable: *"I cannot verify this against literature in the current KB."*

The `vaultlab.roles._guardrails.enforce_hedge()` checker flags assertions that should be hedged. Do not disable it.

### Anti-laziness on semantic reading

Every LLM prompt template includes anti-laziness rules:
1. **Quote** exact text/data supporting any claim accepted
2. If you cannot quote, the claim is `NOT_FOUND`
3. Read every passage in full; do not skim
4. When uncertain, say `INSUFFICIENT_EVIDENCE` — never fabricate confidence

### Citation 3-tier integrity

All citations in vaultlab-generated content go through 3-tier verification:
- **Tier 1** — PMID/DOI exists via API check
- **Tier 2** — abstract semantic match via embedding + Claude judgment
- **Tier 3** — exact quote from full text + page number

Citations not reaching at least Tier 2 are marked `WEAKLY_SUPPORTED` and flagged for review. Citations reaching Tier 1 only are marked `NOT_VERIFIED`. **Never silently downgrade verification level.**

### Reproducibility receipts

Every output (figure, manuscript section, slide deck) writes BOTH:
- `<output>.provenance.json` — machine-readable (input hashes, code version, params, seed, model, timestamps)
- `<output>.method.md` — human-readable narrative for paper methods sections

These are written automatically by `vaultlab.provenance`. Do not bypass.

### Forward-compatibility commitments

vaultlab v0.1 promises:
1. `.vaultlab-project.json` schema is **additive only**
2. Per-run `manifest.json` schema is **additive only**
3. KB folder layout is **additive only**
4. Slash command names are **stable** (deprecation warnings before removal)
5. Role identifiers are **stable** (prompts can change; identifiers cannot)
6. Output folder naming (`runs/<run-id>/`) is **stable**

Do not break these without an issue + version bump discussion.

---

## Code conventions

### Python

- **Python:** 3.12+ (target last 2 minor versions: 3.12, 3.13)
- **Type hints:** strict on public API (`mypy --strict`); loose internals (`vaultlab._internal.*`)
- **Data models:** `pydantic.BaseModel` for configs, EvidenceRecord, Paper, Citation, Manifest, LayoutPreset, Recipe, IngestedItem
- **Pure dataclasses:** for value types with no validation needs (e.g., `PassageLocation`)
- **Imports:** explicit submodule imports preferred over star imports; `__init__.py` barrels are slim (~10 symbols)
- **Linting:** `ruff` with the config in `pyproject.toml`
- **Formatting:** `ruff format` (PEP 8 with 100-char line length)

### Markdown

- **Frontmatter:** YAML frontmatter on every role prompt, recipe doc, layout template, slash command, skill, agenda template
- **Required fields:** `title`, `type`, plus type-specific fields (e.g., `recipe_name`, `data_signature` for recipes)
- **Anti-laziness reminders:** every role prompt's "Process" section includes the four anti-laziness rules

### Tests

- **Coverage target:** 80% on public API
- **No real LLM calls in CI** by default. Mark tests that hit real APIs with `@pytest.mark.llm`; CI runs `pytest -m "not llm"`.
- **Mocked LLM responses:** use `tests/fixtures/mock_responses/` snapshots
- **Golden eval suites:** `tests/fixtures/{hallucination,cluster_naming,figure_caption}_test_set.json` — snapshot-tested with `temperature=0`
- **Every recipe / role / data modality template** ships with a unit test scaffold

---

## When to add a new top-level subpackage

Default is "make it a subpackage of an existing one." Adding a new subpackage requires meeting **at least 2 of these 3 criteria**:

1. **Cohesive concept** that doesn't fit any existing subpackage
2. **Reusable outside vaultlab** (could plausibly be extracted into its own package)
3. **>2000 LOC + own external dependencies + own data model + own tests**

Adding a new top-level subpackage requires an issue + PR review.

---

## Contribution workflow

1. **Open an issue** before any non-trivial PR
2. **Use templates** in `.github/ISSUE_TEMPLATE/`
3. **Fork or create a feature branch** from `main`
4. **Sign off commits** with DCO: `git commit -s` (adds `Signed-off-by:` footer)
5. **Run tests + lint locally** before pushing
6. **Open PR** with clear description; reference issue
7. **CI must pass** (tests, mypy, ruff, dco-check, vaultlab-claude-validate)
8. **One reviewer approves** before merge
9. **Squash-merge to `main`**

For full contributor guide, see [`docs/contributing.md`](docs/contributing.md).

---

## When this file is wrong

If you encounter a real situation where an invariant in this file blocks legitimate work, **open an issue first** to discuss before bending the rule. The rule may need refinement; the discussion is the audit trail.
