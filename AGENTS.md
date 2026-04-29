# AGENTS.md — Contributor invariants and conventions

This file defines the invariants every code change must preserve. **Read this before opening a PR.** When in doubt, the rules below override convenience.

vaultlab is in active alpha development; some invariants may evolve, but each change to AGENTS.md must be discussed in an issue before merging.

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
