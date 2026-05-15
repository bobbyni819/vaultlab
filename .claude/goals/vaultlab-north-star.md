# /goal: Vaultlab adopted by biology labs as the audit-grade research-companion harness

_Created: 2026-05-14_
_Working dir: `~/Downloads/vaultlab` + `G:/My Drive/Knowledge/vaultlab`_
_Type: STRATEGIC — north-star reference. Sub-goals invoke `/goal` against this file._

## CONTEXT

- **Project:** vaultlab — Claude-Code-native composable framework of audit-grade research primitives. Library + harness + KB companion.
- **Stack:** Python (`vaultlab.*`), Claude Code slash commands & skills (`.claude/commands/*`, `.claude/skills/*`), Obsidian-readable KB (`G:/My Drive/Knowledge/vaultlab/`), paperclip MCP for paper corpus.
- **Current state (2026-05-14):** v0.0.3 tagged on PyPI; v0.0.4 in flight on `main` (12 commits ahead, awaiting tag). 1734 tests passing. Latest canonical state doc: `Sources/Notes/system-state-2026-05-12.md`.
- **Repo:** `github.com/bobbyni819/vaultlab` (public). PyPI: `pypi.org/project/vaultlab/`.
- **Audience:** wet-lab biology teams running Claude Code via a PI/postdoc + comp-bio PhDs. Explicitly NOT ML/CS researchers crossing into biomed — staying biology-domain anchored.
- **Constraints:** no PHI/PII/IRB-restricted data through vaultlab; no Hickey-Lab-branded templates in public repo; bobby.ni@duke.edu never hardcoded as default.

## WHAT VAULTLAB IS

A Claude-Code-native composable framework of audit-grade research primitives. Researchers plug it into **any stage** of their work — paper triage, figure assembly, decks, manuscripts, response letters, citation audits — and get reviewer-defensible artifacts back. Primitives compose; users (or agents) assemble them for whatever purpose the existing capabilities can serve.

It is a **library + harness**, not a fixed-purpose application.

## SUCCESS CRITERIA (all must be true)

| # | Criterion | Measurable | Proof type |
|---|---|---|---|
| 1 | Adoption signal received | ≥1 unsolicited testimony from a non-Bobby account: "we used vaultlab for X" | Archived email / forwarded message / GitHub issue URL / tweet permalink in `## EVIDENCE` |
| 2 | Audit-grade enforced | 0 critical-tier audit violations in the full integration test sweep; every artifact-producing function writes a `<name>.audit.json` manifest before/with its output | pytest run output + sample manifests checked into `examples/` |
| 3 | Plug-in companion | Every public-API module is end-to-end runnable without prior vaultlab state | Per-module standalone integration test starting from a fresh fixture; all green |
| 4 | Time-to-first-artifact ≤30 min | New user runs `pip install vaultlab` cold on a clean machine and produces a non-trivial audit-clean artifact in ≤30 min using copy-paste README commands. "Non-trivial" = one of: 5-slide journal-club deck, 3-paper lit-arc, audited manuscript section, or citation audit on a real paper | Scripted onboarding test on a clean Docker/VM hits the bar; recorded log |
| 5 | Composability proven | ≥3 example workflows in `examples/` authored by someone other than Bobby (commit author ≠ Bobby) | git log of `examples/` directory showing non-Bobby author attribution |
| 6 | Final deliverable runs without errors | `pytest` green on full test suite at the time of north-star evaluation | last test run output |
| 7 | Public proof exists | All evidence is shareable / linkable / inspectable | `## EVIDENCE` section below populated |

## CAPS

- **Horizon:** 12 months from creation date (target: 2027-05-14 for criterion #1).
- **Sub-goals** (per module / per release) invoke `/goal` with their own shorter caps (typically `max-hours: 4`, `max-iters: 25`).
- This file is the **strategic reference** sub-goals are evaluated against.

## RED LINES (enforced invariants, with tests)

These are non-negotiable. Each is enforced in code, not aspiration. Each has a corresponding invariant test that fails CI if the red line is crossed.

1. **No fabrication of any kind.** Every DOI / PMID / arXiv-ID / author name / claim / figure data point traces to a verifiable source. Citations verify against CrossRef / PubMed / Semantic Scholar before the file is written. Synthetic illustrative content (e.g., demo cartoons) is explicitly flagged in caption AND manifest.
2. **No silent failures.** Every audit check writes to the artifact's manifest. Every refusal logs the reason. The user can always answer: "what did vaultlab check, what passed, what failed?" *Implementation note (2026-05-15): the "audit manifest" is implemented in vaultlab as the existing `vaultlab.provenance` receipts — `<output>.provenance.json` + `<output>.method.md` sidecars (see `src/vaultlab/provenance/`). Sub-goal 1.2's work is to ensure every artifact-producing entrypoint calls `write_receipts(...)`. The terms "audit manifest" and "provenance receipt" are aliases in vaultlab.*
3. **No user-data loss.** Operations are reversible. Caches and checkpoints survive crashes. Dry-run mode exists for any destructive command. Never overwrite existing user files without confirmation or backup.
4. **No vendor lock-in.** Outputs are open formats only: `.md`, `.pptx`, `.png`, `.svg`, `.html`, `.json`. No proprietary containers. No database requirements. The HARNESS layer (slash commands, skills) is Claude-Code-native; the OUTPUTS are not — a researcher with no Claude Code installed can open the .pptx in PowerPoint, read the .md in any editor, view the .png anywhere. Vaultlab produces artifacts the world can consume independently.

## SHIPPING POLICY (tiered audit)

When an artifact-producing function runs its audit:

- **CRITICAL failures** → hard refuse. File is NOT written. User sees an actionable error message naming the failed check and a remediation hint. Critical = fabrication-class, broken data lineage, red-line violation.
- **WARNING failures** → ship the artifact + companion `<name>.audit.json` listing what failed. User decides what to fix. Warning = cosmetic / style (bullet density, contrast, aspect ratio, color palette deviation).

Every artifact gets a manifest. No file is ever written without an associated audit record.

## SCOPE PHILOSOPHY

Vaultlab is the **LAYER ABOVE analysis**, not the analysis itself.

- **In scope:** any research-artifact production task the existing primitives + orchestration can serve. Paper triage, figure assembly, decks, manuscripts, response letters, citation audits, KB dossiers — and any future composable workflow.
- **Project-specific analysis code** (e.g., `lipid_xgboost`, `flu-sim` repos) lives in user repos and feeds vaultlab. Vaultlab consumes outputs to produce papers / figures / decks / letters.
- **New domains welcome** as long as the existing primitive + orchestration set can serve them. Bespoke new primitives are added only when ≥3 concrete use cases demand them (the "three-example rule" guards against premature abstraction).

## FORM

| Layer | What it is | Where it lives |
|---|---|---|
| Library | `vaultlab.*` Python primitives — composable, importable, documented | `~/Downloads/vaultlab/src/vaultlab/` |
| Harness | Slash commands & skills wrapping primitives for Claude Code use | `~/Downloads/vaultlab/.claude/commands/`, `~/Downloads/vaultlab/.claude/skills/` |
| KB companion | Obsidian-readable `Sources/`, `Wiki/`, `Output/` structure synced via Google Drive | `G:/My Drive/Knowledge/vaultlab/` |

## PERSONA-DRIVEN DEFAULTS

- **Docs in biology language**, not ML jargon
- **Examples are real workflows**, not toy demos
- **Wet-lab team flows are first-class:** lab-meeting deck, journal-club deck, manuscript draft, response letter, prelim/qual deck
- **Comp-bio extensibility is first-class:** importable primitives, documented APIs, hackable internals, three-example rule before abstraction
- **No API-key gates** on the happy path — CrossRef, paperclip MCP, public PubMed are the defaults

## REPRODUCIBILITY

**Audit-identical**, not byte-identical. Same input + same vaultlab version → same audit-clean structure + same provenance manifest. Bytes may vary slightly due to LLM variance. The AUDIT-GRADE invariants are deterministic and verifiable. Cache hits make repeat runs cheap.

## PROGRESS

### Plan (next sub-goals — invoke `/goal` against each)
1. ~~**Wire CI invariant tests** for each red line — fabrication, silent-failure, data-loss, lock-in. Without these, the red lines are aspirations.~~ ✅ **DONE 2026-05-14** — see `.claude/goals/wire-redline-invariant-tests.md`. Tests: 6 pass / 2 xfail (documenting gaps for sub-goal 1.2 + a small followup). CI: `.github/workflows/invariants.yml`. Followups: (a) flip `test_every_artifact_entrypoint_writes_manifest` to a passing assertion via sub-goal 1.2's audit-manifest contract; (b) add `dry_run` params to `context.user_memory.forget` + `context.meetings.ingest_transcript`.
2. **Per-module standalone integration tests** (success criterion #3) — fresh-fixture, end-to-end, no upstream state. One per public-API module.
3. **`vaultlab demo` command** — a single command that produces a real audit-clean artifact from sample data shipped in the package. Enables the <30-min onboarding test.
4. **Scripted onboarding test** (success criterion #4) — clean-VM CI job that times `pip install` → first artifact.
5. **`examples/` directory** with at least Bobby-authored seed workflows showing primitive composition. Invite external contributions.
6. **Three-example rule documented** in `CONTRIBUTING.md` — new primitives only when ≥3 concrete use cases.
7. **Public testimony channel** — GitHub Discussions enabled + a "tell us how you used vaultlab" issue template + a link in the README.

## EVIDENCE

_To be populated as criteria are satisfied._

- 🟡 Criterion #1 (adoption signal): channel LIVE at https://github.com/bobbyni819/vaultlab/discussions — welcome thread #1 published inviting testimonies (Announcements category). Awaiting first non-Bobby contribution. NOTE: pinning requires UI click (GitHub GraphQL exposes `PinnedDiscussion` type but no public mutation to create one); Bobby to pin manually at https://github.com/bobbyni819/vaultlab/discussions/1.
- 🟡 Criterion #2 (audit-grade enforced): partial — invariant test framework wired in CI (2026-05-14, `tests/test_vaultlab_invariants/test_red_lines.py` + `.github/workflows/invariants.yml`). 6 pass / 2 xfail. Universal `.audit.json` sidecar enforcement still pending sub-goal 1.2.
- ⏳ Criterion #3 (plug-in companion): partial — most modules work standalone; per-module fresh-fixture tests not yet added
- ⏳ Criterion #4 (<30-min onboarding): pending — scripted clean-VM test not yet wired
- ⏳ Criterion #5 (composability proven): pending — `examples/` has Bobby-authored seeds only
- ⏳ Criterion #6 (final deliverable runs): green at creation (1734 tests passing as of 2026-05-12)
- ⏳ Criterion #7 (public proof exists): this file is the registry

### Files / paths referenced by this spec
- Vaultlab repo: `~/Downloads/vaultlab`
- KB: `G:/My Drive/Knowledge/vaultlab`
- Latest state doc: `G:/My Drive/Knowledge/vaultlab/Sources/Notes/system-state-2026-05-12.md`
- `/goal` runner: `~/.claude/commands/goal.md`
