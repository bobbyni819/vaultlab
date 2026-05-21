# NEXT_STEPS — doc-vs-code gaps to fix or build

Compiled 2026-05-21 from a read-only audit of the orchestration layer, the
analysis→methods pipeline, and the figure-recipe system. Every item is grounded in a
real `file:line`.

**The pattern:** `CLAUDE.md`, `AGENTS.md`, and `docs/architecture.md` describe an
*aspirational* system. The orchestration core and the 11 figure recipes are real and
solid. Much of the connective tissue the docs present as built — audit gates, verifiers,
the stats package, the recipe corpus — is placeholder, unwired, or absent.

Each item below has a **disposition**:
- **DOC** — code is fine; the doc is wrong. Just edit the doc. (→ `fix/doc-accuracy` branch)
- **BUILD** — the doc describes something real and wanted; it isn't built. Implement it.
- **DECIDE** — code and doc genuinely disagree on intent; Bobby must pick which is right.

> Per `AGENTS.md`, any change to `AGENTS.md` itself must be discussed in a GitHub issue
> first. Open that issue before starting the DOC items that touch `AGENTS.md`.

---

## A. Bugs — broken things that need a fix

### A1. Broken public API in the package barrel — DECIDE
`src/vaultlab/__init__.py:20-21` documents `from vaultlab.meetings import …` and
`from vaultlab.runner import …, bounded_loop`. Neither the top-level `meetings` module
nor `bounded_loop` exists (`runner/__init__.py:68-95` `__all__` has no `bounded_loop`;
the real module is `runner/meetings.py`). It's inside a docstring, so import does not
crash — but it advertises public API that does not exist.
**Action:** either fix the docstring to name real symbols, or, if `bounded_loop` was
meant to be a real export, build it. Decide which.

### A2. `rigor_audit` cannot audit a methods doc — BUILD
`READ_FIRST.md`'s dispatch table says "Methodology doc → `rigor_auditor` before ship."
But `rigor_audit()` (`workflows/crosstalk.py:632-700`) only accepts `audit_kind` of
`arc`, `deck`, or `report` (`crosstalk.py:656`) — `methods` is rejected. The documented
workflow is impossible to run.
**Action:** add `methods` as a valid `audit_kind`, or wire a methods-specific audit path.

### A3. Analysis-pipeline output ignores the canonical KB path — DECIDE
`CLAUDE.md` says artifacts land in `<kb>/Output/<project>/`. `run_pipeline`
(`analysis/pipeline.py:142-269`) writes to `<project_dir>/out/` instead — no KB routing.
`AGENTS.md`'s path matrix also says every output uses a `vaultlab.kb.paths` helper.
**Action:** decide whether the analysis pipeline should route to the KB (then build it)
or whether `<project_dir>/out/` is intentional (then fix the docs).

### A4. Invariant 3 is not enforced — DECIDE
`AGENTS.md` Invariant 3: "only compact summaries (max 2000 tokens) pass between agents in
a meeting." `adversarial_inject` (`runner/meetings.py:393-422`) injects each prior turn's
**full, untruncated output** into later prompts (`meetings.py:421`). No truncation exists
anywhere in the within-meeting path.
**Action:** either implement the 2000-token summarisation step, or strike the claim from
Invariant 3. (Full-text passing may well be the better behaviour — decide deliberately.)

---

## B. Unbuilt — features the docs describe that do not exist yet

### B1. The `vaultlab/stats/` package — BUILD
`CLAUDE.md` and `architecture.md` describe `stats/` with `de`, `power`, `effect`, `blind`
modules. `src/vaultlab/stats/__init__.py:1` is literally
`"""Placeholder. Will be populated by migration commits."""`. No such modules exist.
The real stats code (`analysis/stats.py`) is **descriptive-only** by explicit design
(`stats.py:5-6`: "No hypothesis tests — vaultlab CONSUMES analysis results").
**Action:** decide if `stats/` is genuinely wanted. If not, remove it from the docs
(DOC). If yes, BUILD it — but reconcile with the "vaultlab consumes, does not compute"
principle first.

### B2. `enforce_hedge()` hedged-voice checker — BUILD
`AGENTS.md:215` names `vaultlab.roles._guardrails.enforce_hedge()` as the checker that
flags unhedged assertions. The function and its module do not exist anywhere in `src/`.
Hedged voice is currently a prompt-level convention only — nothing deterministic checks
generated text.
**Action:** BUILD `enforce_hedge()` (banned/allowed word lists, a checker function),
then wire it into the analysis pipeline and role outputs.

### B3. Numeric verifier — BUILD
`CLAUDE.md` / `architecture.md` list "numeric" as one of four internal verifiers. Only
citation (`citations/verifier.py`) and claim/cross-doc (`research/claim_verification.py`)
are real code. Numeric discipline exists only as prompt instructions
(e.g. `deep_think.py:155`).
**Action:** BUILD a numeric verifier module, or downgrade the doc claim to "prompt-level
only" (DOC).

### B4. LLM/role-driven methods drafting — BUILD
The `/run-analysis` flow's `compose_methods_paragraph` (`analysis/methods.py:24-112`) is
pure string-templating — its own docstring says "no LLM call in this iteration"
(`methods.py:2-3`). The docs imply a role drafts the methods paragraph.
**Action:** BUILD the role/prompt-driven drafting step, OR adjust the docs to describe
the template approach as intentional.

### B5. `state_aware_preflight()` in the analysis pipeline — BUILD
`CLAUDE.md` commitment #6: "every artifact-producing primitive starts with a
`state_aware_preflight()` call." `run_pipeline` never reads KB state and never branches
`--fresh`/`--extend`.
**Action:** BUILD the preflight call into `run_pipeline` (and audit other primitives for
the same gap).

### B6. `methods_critic` / `rigor_auditor` role pass wired into `/run-analysis` — BUILD
Both roles exist as prompts but are invoked only inside crosstalk meetings — never by the
analysis pipeline. `READ_FIRST.md` says a methodology doc gets a `rigor_auditor` pass
before ship. (Depends on A2 being fixed first.)
**Action:** BUILD the role-pass step into the analysis flow once A2 unblocks it.

### B7. Recipe `corpus/sources.json` — BUILD
`templates/recipe/README.md:8` and `CLAUDE.md` require each recipe to have an entry in
`vaultlab.figures.corpus/sources.json`. No `sources.json` file exists anywhere;
`figures/corpus/__init__.py` is the placeholder one-liner.
**Action:** BUILD the corpus subsystem (the `sources.json` schema + per-recipe entries),
or remove the requirement from the docs (DOC).

### B8. Recipe unit tests — BUILD
`AGENTS.md:280` says every recipe "ships with a unit test scaffold." There are **no
recipe tests** — `tests/test_vaultlab_figures/` covers contract/publication/report/etc.
but nothing under `recipes/`. All 11 recipes are real implementations; none are tested.
**Action:** BUILD a unit test per recipe.

### B9. The `templates/recipe/` scaffold — BUILD
`templates/recipe/` contains only a `README.md` — it self-describes as incomplete
("files will be added in migration commits"). New contributors have nothing to copy.
**Action:** BUILD the actual scaffold files (`<name>.py` + `<name>.md` stubs).

### B10. Recipe selection / dispatch layer — BUILD or DECIDE
There is no registry, no picker role, no data-signature matcher. A recipe is chosen by an
LLM reading the `.md` docs and hand-calling `render()`. No `figure_picker` role exists
(only `figure_lead` / `figure_reader`). The docs imply something more automatic.
**Action:** DECIDE whether convention-based selection is acceptable. If a coded dispatch
is wanted, BUILD a recipe registry + selector.

### B11. `FigureContract` ↔ recipe integration — BUILD or DECIDE
The 5-commitment `FigureContract` (`figures/contract.py`) and the 11 recipes are parallel
subsystems. Recipes never accept a `FigureContract`, never call `validate_contract`, and
use `save_fig` (PNG+PDF, 300 DPI) instead of the contract's `triple_export` (SVG+PDF+TIFF,
600 DPI). `contract.md:165` implies recipes "implement these rules."
**Action:** DECIDE if recipes should consume contracts. If yes, BUILD the integration so
recipes honour the export contract.

### B12. The ≥3-anchor-paper rule is unenforced — BUILD or DECIDE
`templates/recipe/README.md:57` says "Recipes without 3+ references fail review" — the
rule that makes recipes trustworthy (each one copies a layout from ≥3 real published
figures, not an AI guess). Nothing counts anchor papers: no code, no test, no CI check.
Recipes satisfy it by hand (e.g. `marker_dot_plot.py:29-33` has exactly 3 in its
`ANCHOR_PAPERS` tuple) but a recipe with zero would pass unnoticed.
**Action:** BUILD a check that counts each recipe's `ANCHOR_PAPERS` and fails CI when
`< 3`, or DECIDE it stays a manual review convention (then reword the doc to say so).

---

## C. Doc-only fixes — code is correct, docs are wrong (→ `fix/doc-accuracy`)

These need no code change — just edit the doc. Low-risk, do them first.

| # | Doc location | Wrong claim | Correct it to |
|---|---|---|---|
| C1 | `CLAUDE.md`, `architecture.md` package maps | `meetings.py` at package root | `runner/meetings.py` |
| C2 | `CLAUDE.md` commitment #3 | "bounded loop, max 3 iterations" (one cap) | three caps: crosstalk 5 (`crosstalk.py:86`), reflection 3 (`reflection.py:90`), deep-think 4 (`research/session.py:153`) |
| C3 | `deep_think.py:9` docstring, `roles/__init__.py:118`, `CLAUDE.md` | deep-think is a "round-table" | it runs under `MeetingMode.ADVERSARIAL` (sequential) — "round-table" is misleading |
| C4 | `templates/recipe/README.md`, `CLAUDE.md` "Add a recipe" | recipes are directories `recipes/<name>/<name>.py` | recipes are flat files `recipes/<name>.py` |
| C5 | `CLAUDE.md`/`architecture.md` verifier list | 4 internal verifiers all built | only citation + claim are code; numeric + hedge are prompt-only (until B2/B3 land) |
| C6 | `AGENTS.md:280` | every recipe ships a unit test | currently false — reword, or leave until B8 lands |
| C7 | `AGENTS.md:215` | `enforce_hedge()` exists | currently false — reword, or leave until B2 lands |

---

## Suggested order of work

1. **Open the GitHub issue** describing this whole gap list (mandatory before touching
   `AGENTS.md`).
2. **`fix/doc-accuracy` branch** — knock out section C. Pure doc edits, zero risk, makes
   the docs honest immediately.
3. **`feat/lab-dashboard` branch** — the polished HTML screen (separate, unrelated work).
4. **Triage A + B with Bobby.** The DECIDE items especially — several "bugs" might be
   intentional design that the docs simply over-promised. Don't BUILD until intent is
   confirmed; the doc may be what's wrong, not the code.

**Do not assume the docs are the source of truth.** In several cases (A3, A4, B1, B4) the
*code* may be the correct intent and the *doc* is the thing to fix. Confirm before building.
