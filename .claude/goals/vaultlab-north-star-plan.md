# Vaultlab North-Star Implementation Plan

> **For agentic workers:** This plan is a CATALOG of `/goal` invocations, not a single-session execution sequence. Each sub-goal below is one autonomous `/goal "<outcome>"` run with its own `.claude/goals/<slug>.md` file. Steps inside each sub-goal are at `/goal`-runner granularity (4-hour caps), not 2-5 minute TDD steps. The executing agent uses `superpowers:test-driven-development` and `superpowers:systematic-debugging` INSIDE each sub-goal as needed.

**Strategic reference:** `~/Downloads/vaultlab/.claude/goals/vaultlab-north-star.md`

**Goal:** Decompose the 12-month north-star (adoption by biology labs as the audit-grade research-companion harness) into 20 ordered, executable sub-goals.

**Architecture:** Five phases gated by dependency: (1) enforce red lines + audit-manifest contract; (2) close pipeline gaps including the last missing nature-skill and the SPEC backlog; (3) build composability surface for external adoption; (4) complete Thariq's HTML-pattern coverage; (5) quality + maintenance.

**Tech Stack:** Python (`vaultlab.*`), pytest, GitHub Actions, Claude Code slash commands & skills, Obsidian-readable KB on Google Drive, paperclip MCP.

---

## How to use this plan

1. Open this file. Pick the next unblocked sub-goal (top-down within a phase, dependencies satisfied).
2. Invoke `/goal "<one-line outcome>"` (copy the `Invocation` line). The `/goal` runner creates `.claude/goals/<slug>.md`, derives context from this plan + the north-star spec, and runs autonomously.
3. When the sub-goal's `## EVIDENCE` is populated, return here and pick the next.
4. Sub-goals within a phase can run in parallel if their `Depends on:` list permits.

---

## Phase 1 — Foundation: enforce the red lines + onboarding bar

**Why first:** Adoption is impossible without the trust promises being mechanically enforced. The strategic spec's red lines are aspirational until the CI invariant tests exist. Same for the <30-min onboarding criterion.

### Sub-goal 1.1: Wire CI invariant tests for the 4 red lines

**Slug:** `wire-redline-invariant-tests`
**Invocation:** `/goal "wire CI invariant tests that fail if any of the 4 vaultlab red lines is crossed"`
**Advances:** Red Lines #1-4 (all four) + Criterion #2 (audit-grade enforced)
**Depends on:** none
**Cap:** max-hours: 4

**Success criteria:**
1. New test file `tests/invariants/test_red_lines.py` contains four test classes, one per red line. *Proof:* file exists, pytest collects 4+ tests.
2. **No-fabrication test:** A property-style test that runs `vaultlab.citations.audit` on a fixture containing a fake DOI and asserts a critical-tier violation is raised. *Proof:* test green; mutate the fixture to a real DOI → test still green; mutate fabrication-detection logic → test fails.
3. **No-silent-failures test:** Every artifact-producing entrypoint (`vaultlab.research.lit_arc`, `vaultlab.slides.build_from_plan`, `vaultlab.figures.assemble`, `vaultlab.manuscript.polish`, `vaultlab.citations.audit`, `vaultlab.kb.dossier`, `vaultlab.workflows.crosstalk`) writes a companion `<name>.audit.json` manifest. Test enumerates entrypoints + asserts manifest existence post-call. *Proof:* test fails if any entrypoint is missing manifest write.
4. **No-data-loss test:** A dry-run flag exists on every destructive operation (write/overwrite/delete); test parametrizes over destructive ops and asserts dry-run produces no filesystem change. *Proof:* pytest output.
5. **No-vendor-lock-in test:** A test enumerates output file extensions across the example workflows and asserts membership in `{.md, .pptx, .png, .svg, .html, .json, .csv, .yaml}`. *Proof:* pytest output.
6. CI is configured to run `pytest tests/invariants/` on every push. *Proof:* `.github/workflows/*.yml` diff.

**Files to create/modify:**
- Create: `tests/invariants/__init__.py`, `tests/invariants/test_red_lines.py`, `tests/invariants/fixtures/` (with fake-DOI fixture, sample audit-manifest expectations)
- Modify: `.github/workflows/ci.yml` (or existing CI file) to run the invariant suite
- Reference (read-only): existing `tests/citations/test_auditor.py`, `tests/slides/test_audit.py`, `tests/figures/test_contract.py` for similar patterns

**Non-obvious context:** Many entrypoints already emit audit reports; the gap is that not all do, and there's no test that enforces it. Discover gaps by parameterizing the test over a list of entrypoints; failures are actionable.

---

### Sub-goal 1.2: Audit-manifest contract — every artifact has a `.audit.json` sidecar

**Slug:** `audit-manifest-contract`
**Invocation:** `/goal "every artifact-producing function in vaultlab writes a companion .audit.json with check results"`
**Advances:** Criterion #2 + Red Line #2 (no silent failures)
**Depends on:** 1.1 (the invariant test from 1.1 will tell us exactly which entrypoints are missing manifest writes)
**Cap:** max-hours: 4

**Success criteria:**
1. Every entrypoint identified in 1.1's no-silent-failures test now writes a manifest. *Proof:* invariant test green.
2. New module `vaultlab.audit.manifest` defines `AuditManifest` dataclass + `write_manifest(artifact_path, checks: list[Check])` helper. *Proof:* module + signature match.
3. Manifest schema is documented in `vaultlab/audit/SKILL.md` and matches the schema used by every entrypoint. *Proof:* schema doc + at least one example manifest checked into `examples/manifests/`.
4. Tiered policy is encoded: critical failures raise; warnings are recorded but allow write. *Proof:* unit test parameterizing severity.

**Files to create/modify:**
- Create: `src/vaultlab/audit/__init__.py`, `src/vaultlab/audit/manifest.py`, `src/vaultlab/audit/SKILL.md`, `tests/audit/test_manifest.py`, `examples/manifests/lit_arc_example.audit.json`
- Modify: each entrypoint identified in 1.1 to import `write_manifest` and call it before/with the artifact write

**Non-obvious context:** Multiple existing modules already use ad-hoc audit dicts (figures.contract, citations.auditor, slides.audit). This sub-goal unifies them under one schema without breaking existing consumers. The unified schema must support both critical (raise) and warning (record) severities.

---

### Sub-goal 1.3: Per-module standalone integration tests

**Slug:** `per-module-standalone-integration-tests`
**Invocation:** `/goal "add per-module standalone integration tests that prove every vaultlab module works without prior vaultlab state"`
**Advances:** Criterion #3 (plug-in companion)
**Depends on:** none (can parallel 1.1, 1.2)
**Cap:** max-hours: 4 (may need extension if many modules; split per package if so)

**Success criteria:**
1. Each public module (`vaultlab.research`, `vaultlab.figures`, `vaultlab.citations`, `vaultlab.slides`, `vaultlab.manuscript`, `vaultlab.kb`, `vaultlab.workflows`, `vaultlab.report`) has one test file `tests/<module>/test_standalone.py`. *Proof:* 8 files exist.
2. Each test starts from a fresh `tmp_path` fixture (no shared state), imports the module cold, and runs an end-to-end task. *Proof:* tests pass when run in isolation with `pytest --forked`.
3. Each test asserts: input → output artifact + companion manifest. *Proof:* test bodies.
4. CI runs the standalone suite with `pytest tests/*/test_standalone.py --forked` (no shared state contamination). *Proof:* CI config diff.

**Files to create/modify:**
- Create: 8 × `tests/<module>/test_standalone.py`
- Modify: CI config to include the standalone matrix
- Reference: each module's existing tests for the realistic end-to-end shape

**Non-obvious context:** "Standalone" means: a fresh user, no KB, no prior vaultlab artifacts. The test must demonstrate that a researcher who installs vaultlab and immediately calls (say) `vaultlab.figures.assemble(...)` gets a working result without first running anything else.

---

### Sub-goal 1.4: `vaultlab demo` command + bundled sample data

**Slug:** `vaultlab-demo-command`
**Invocation:** `/goal "ship a vaultlab demo CLI command that produces a real audit-clean artifact from sample data in <5 min"`
**Advances:** Criterion #4 (<30-min first artifact)
**Depends on:** 1.2 (manifests must exist)
**Cap:** max-hours: 4

**Success criteria:**
1. `vaultlab demo` is registered as a CLI entry point in `pyproject.toml`. *Proof:* `pip install -e .` + `vaultlab demo --help` works.
2. Sample data (2-3 small public-domain PDFs or DOIs + a topic prompt) ships in `src/vaultlab/data/demo/`. *Proof:* directory exists; <5 MB total.
3. Running `vaultlab demo` from any directory produces an audit-clean output in `./vaultlab-demo-out/` containing: a 5-slide journal-club deck OR a 3-paper lit-arc HTML OR an audited citation report. *Proof:* sample run output committed to `examples/demo-run/`.
4. Total runtime <5 minutes on a typical laptop. *Proof:* time-stamped run log.
5. README features `vaultlab demo` as the first thing a new user runs. *Proof:* README diff.

**Files to create/modify:**
- Create: `src/vaultlab/cli/demo.py`, `src/vaultlab/data/demo/<sample files>`, `examples/demo-run/<reference output>`
- Modify: `pyproject.toml` (entry point), `README.md`, `src/vaultlab/cli/__init__.py`

**Non-obvious context:** Sample PDFs must be public-domain or CC-licensed (PubMed Central OA subset is safe). Avoid paywalled papers. The demo must work with ZERO API keys — use cached fixtures or paperclip's free tier.

---

### Sub-goal 1.5: Scripted clean-VM onboarding test

**Slug:** `clean-vm-onboarding-test`
**Invocation:** `/goal "scripted onboarding test that runs on a clean Docker container and verifies pip install vaultlab → demo artifact in <30 min"`
**Advances:** Criterion #4 (proof)
**Depends on:** 1.4
**Cap:** max-hours: 4

**Success criteria:**
1. `Dockerfile.onboarding` exists at repo root with a clean Python 3.11 base image. *Proof:* file exists.
2. A GitHub Actions workflow `.github/workflows/onboarding.yml` builds the container, runs `pip install vaultlab` (from PyPI when tagged, from `.` otherwise), then `vaultlab demo`, and asserts the demo artifact exists + audit-clean. *Proof:* workflow runs green.
3. Workflow records and asserts total wall-clock time < 1800 s (30 min). *Proof:* workflow log + time-stamped step.
4. README documents how to reproduce the onboarding test locally. *Proof:* README diff.

**Files to create/modify:**
- Create: `Dockerfile.onboarding`, `.github/workflows/onboarding.yml`, `scripts/measure_onboarding.sh`
- Modify: `README.md`

**Non-obvious context:** This test is also Criterion #4's evidence — its green CI run IS the proof that the bar is met. Keep the workflow cheap (cache pip wheels) so it can run on PRs.

---

## Phase 2 — Pipeline gap fills: last nature-skill + SPEC backlog

**Why second:** Phase 1 enforces the existing surface. Phase 2 expands the surface to cover known gaps. Without these, vaultlab is incomplete; with them, it covers the full research-artifact lifecycle.

### Sub-goal 2.1: Absorb nature-reader → `vaultlab.research.full_reader`

**Slug:** `absorb-nature-reader`
**Invocation:** `/goal "absorb nature-reader skill into vaultlab.research.full_reader for bilingual figure-aware full-paper Markdown"`
**Advances:** Criterion #2 (audit-grade — reader output is verifiable) + completes nature-skills coverage
**Depends on:** 1.2 (audit manifest contract)
**Cap:** max-hours: 4

**Success criteria:**
1. New module `vaultlab.research.full_reader` with public API: `build_paper_reader(pdf_path: Path | str, *, target_lang: str = "zh-CN", out_dir: Path) -> Path`. *Proof:* module + signature.
2. Output is `paper.md` with: full English + target-language translation interleaved by paragraph; figures/tables embedded near the prose that introduces them; stable anchor IDs (`S001`, `F001`, `T001`, `C001`) on every block. *Proof:* example output for a real OA paper checked into `examples/full-reader/`.
3. Reader writes a `paper.audit.json` manifest with provenance (source DOI/path, extraction method, translation model, block counts). *Proof:* manifest in example output.
4. No-fabrication rule: every block has a source anchor; the test mutates the source PDF and asserts anchors change. *Proof:* unit test.
5. Integration with existing `vaultlab.research` corpus: `full_reader` can consume a paperclip-ID instead of a PDF path. *Proof:* test exercising paperclip path.
6. SKILL.md alongside the module documents when to use it vs `batched_reader` vs `abstract_recall`. *Proof:* file exists.

**Files to create/modify:**
- Create: `src/vaultlab/research/full_reader.py`, `src/vaultlab/research/full_reader.md` (SKILL.md), `tests/research/test_full_reader.py`, `examples/full-reader/<example paper>/`
- Reference: `C:/Users/bobby/Downloads/nature-skills/skills/nature-reader/SKILL.md` for the original rules

**Non-obvious context:** Nature-reader's rule set is what we're absorbing. Notable rules: translate for meaning not style; preserve equations/units/citation markers; keep figures near the discussion that introduces them; don't collapse into bullets. The vaultlab implementation must use the existing `vaultlab.figures.extract` for figure handling and `vaultlab.research.batched_reader` infrastructure for the LLM calls.

---

### Sub-goal 2.2: SPEC-C — KB retrieval upgrade (frontmatter-first + bidirectional wikilinks)

**Slug:** `spec-c-kb-retrieval-upgrade`
**Invocation:** `/goal "execute SPEC-C: upgrade vaultlab.kb retrieval with frontmatter-first lookup, auto-indexes, and bidirectional wikilinks"`
**Advances:** Criterion #2 (KB retrieval is part of audit grounding) + plug-in composability
**Depends on:** none
**Cap:** max-hours: 4

**Success criteria:**
1. `vaultlab.kb.retrieve` has a new `retrieve_by_frontmatter(filter: dict, kb: str) -> list[Path]` function. *Proof:* signature + test.
2. Auto-index builder `vaultlab.kb.build_indexes(kb)` generates `_Index.md`, `_Catalog.md`, and `_BackLinks.md` from frontmatter scanning. *Proof:* indexes appear in a fixture KB after invocation.
3. Bidirectional wikilink tracker: for every `[[Target]]` reference, the target's `_BackLinks.md` lists the referrer. *Proof:* test exercising forward + back resolution.
4. CLI: `bobby-kb index --kb <name>` calls the new builder. *Proof:* CLI test.
5. Retrieval cascade is documented in `vaultlab/kb/SKILL.md`: corpus → frontmatter → indexes → wikilink walk → cumulative recall. *Proof:* SKILL.md update.

**Files to create/modify:**
- Create / modify: `src/vaultlab/kb/retrieve.py`, `src/vaultlab/kb/build_indexes.py`, `src/vaultlab/kb/SKILL.md`, `tests/kb/test_retrieve.py`, `tests/kb/test_build_indexes.py`
- Modify: `src/vaultlab/kb/cli.py` to wire the new commands

**Non-obvious context:** Bobby's "researcher pathway thinking" feedback memory is binding here — every primitive uses layered retrieval simulating a human researcher with deep project knowledge. Don't shortcut to "agent reads 3 things"; the full cascade matters.

---

### Sub-goal 2.3: SPEC-D — KB-setup as primitive

**Slug:** `spec-d-kb-setup-primitive`
**Invocation:** `/goal "execute SPEC-D: add vaultlab.kb.setup + vaultlab.kb.lint primitives so a new KB can be scaffolded and validated in code"`
**Advances:** Criterion #3 (plug-in companion) + Criterion #4 (onboarding speed)
**Depends on:** 2.2 (uses the new index builder)
**Cap:** max-hours: 4

**Success criteria:**
1. `vaultlab.kb.setup(name: str, root: Path = ...) -> Path` scaffolds a new KB at `root/<name>/` with the canonical directory tree (`Sources/Articles/`, `Sources/Papers/`, `Sources/Notes/`, `Wiki/Concepts/`, `Wiki/Summaries/`, `Output/`, `.obsidian/`). *Proof:* test creates KB in `tmp_path`, asserts tree.
2. `vaultlab.kb.lint(kb: str) -> LintReport` runs structural + content checks: required directories, frontmatter shape, broken wikilinks, stale concept pages, dangling sources. *Proof:* unit test with fixture KB.
3. CLI: `bobby-kb init` and `bobby-kb lint` wrap the primitives. *Proof:* CLI tests.
4. Setup writes a `_KB-Architecture-Spec.md` to the new KB based on a template at `src/vaultlab/data/kb_template/`. *Proof:* template + generated file.

**Files to create/modify:**
- Create: `src/vaultlab/kb/setup.py`, `src/vaultlab/kb/lint.py`, `src/vaultlab/data/kb_template/`, `tests/kb/test_setup.py`, `tests/kb/test_lint.py`
- Modify: `src/vaultlab/kb/cli.py`

**Non-obvious context:** The lint primitive is also load-bearing for the audit-grade promise — a malformed KB produces malformed downstream artifacts. Wire lint into `vaultlab demo` and the onboarding test if practical.

---

### Sub-goal 2.4: SPEC-E — Crosstalk invocation policy

**Slug:** `spec-e-crosstalk-policy`
**Invocation:** `/goal "execute SPEC-E: define when crosstalk round-tables fire and when they don't, with a documented invocation policy"`
**Advances:** Criterion #3 (composability) + cost discipline
**Depends on:** none
**Cap:** max-hours: 4

**Success criteria:**
1. `vaultlab.workflows.crosstalk` exposes a `should_invoke(context: CrosstalkContext) -> bool` policy function. *Proof:* signature + tests.
2. Policy rules are documented in `vaultlab/workflows/crosstalk_policy.md`: heuristics for when round-tables add value (e.g., high-stakes synthesis, contested evidence) vs when single-pass reasoning suffices (e.g., format conversion, mechanical transforms). *Proof:* doc.
3. `should_invoke` is called by every entrypoint that previously invoked crosstalk unconditionally. *Proof:* grep + test.
4. Cost-tracking sidecar `crosstalk.audit.json` records: was crosstalk invoked, why/why not, token cost. *Proof:* manifest example.

**Files to create/modify:**
- Create: `src/vaultlab/workflows/crosstalk_policy.py`, `src/vaultlab/workflows/crosstalk_policy.md`, `tests/workflows/test_crosstalk_policy.py`
- Modify: every entrypoint that calls crosstalk (grep for `crosstalk(` to enumerate)

**Non-obvious context:** Bobby's `feedback_pipeline_run_through_tier_b` memory says crosstalk is part of the pipeline, not a gated luxury — so the policy is "fire by default for synthesis, skip for mechanical." Don't over-gate.

---

### Sub-goal 2.5: SPEC-F — Task-weight dispatch (lightweight vs heavy routing)

**Slug:** `spec-f-task-weight-dispatch`
**Invocation:** `/goal "execute SPEC-F: add a task-weight dispatcher that routes lightweight tasks to Sonnet/Haiku and heavy tasks to Opus"`
**Advances:** Cost discipline + Criterion #4 (speed)
**Depends on:** none
**Cap:** max-hours: 4

**Success criteria:**
1. `vaultlab.workflows.dispatch.classify(task: TaskSpec) -> Weight` returns `light | medium | heavy`. *Proof:* signature + tests.
2. Each weight maps to a default model selection. Mapping is configurable via `~/.config/vaultlab/dispatch.json`. *Proof:* config example.
3. Every entrypoint using LLM calls accepts an optional `weight: Weight = None` (auto-classify if None). *Proof:* signature updates.
4. Dispatch decisions are logged in the audit manifest (model used + weight rationale). *Proof:* manifest field.

**Files to create/modify:**
- Create: `src/vaultlab/workflows/dispatch.py`, `src/vaultlab/workflows/dispatch.md`, `tests/workflows/test_dispatch.py`, `examples/configs/dispatch.json`
- Modify: LLM-calling entrypoints (`batched_reader`, `full_reader`, `crosstalk`, `polish`, `respond`, `narrate_finding`, etc.) to pass weight

**Non-obvious context:** Heuristics: light = format conversion, simple extraction; medium = single-paper summarization; heavy = cross-paper synthesis, manuscript polish, response letters. Defaults are tunable per user; don't hardcode model names beyond a default.

---

### Sub-goal 2.6: SPEC-A — Result-analysis pipeline

**Slug:** `spec-a-result-analysis-pipeline`
**Invocation:** `/goal "execute SPEC-A: result-analysis pipeline that consumes a project's data files and produces figures + methods text + audit"`
**Advances:** Criterion #5 (composability — net-new use case) + Criterion #2
**Depends on:** 1.2 (manifest), 2.5 (dispatch)
**Cap:** max-hours: 4 (consider splitting if scope balloons)

**Success criteria:**
1. `vaultlab.analysis.pipeline.run(project_dir: Path) -> AnalysisResult` consumes a project directory containing data (CSV/Parquet) + a config, runs stats descriptions, generates figures via `vaultlab.figures.contract`, drafts a methods paragraph, and emits an audit manifest. *Proof:* signature + integration test.
2. The pipeline does NOT run user analysis code; it consumes pre-computed results (i.e., respects the "layer above analysis" scope philosophy). *Proof:* scope check in test.
3. Methods text is grounded: every statistical claim cites a column + sample size. *Proof:* methods.audit.json shape.
4. Sample project shipped at `examples/result-analysis/` showing the pipeline running on synthetic data. *Proof:* example dir.

**Files to create/modify:**
- Create: `src/vaultlab/analysis/__init__.py`, `src/vaultlab/analysis/pipeline.py`, `src/vaultlab/analysis/stats.py`, `src/vaultlab/analysis/methods.py`, `tests/analysis/test_pipeline.py`, `examples/result-analysis/`
- Reference: existing `vaultlab.figures.contract` for figure generation contract

**Non-obvious context:** Strict scope discipline — vaultlab does NOT fit models, train pipelines, or generate analyses. It CONSUMES tidy results (CSV, Parquet) and produces figures + text + audit. The boundary is enforced by accepting only "post-analysis" file types as input.

---

## Phase 3 — Composability surface (external adoption enablers)

**Why third:** With foundation enforced and pipelines complete, adoption now needs the public-facing surface — examples, contribution guidance, testimony channel, a tagged release.

### Sub-goal 3.1: `examples/` directory with 3 Bobby-authored seed workflows

**Slug:** `examples-seed-workflows`
**Invocation:** `/goal "build 3 end-to-end Bobby-authored example workflows in examples/ that demonstrate composing vaultlab primitives"`
**Advances:** Criterion #5 (composability proven, seed half)
**Depends on:** 1.4 (demo command shows the pattern)
**Cap:** max-hours: 4

**Success criteria:**
1. `examples/journal-club/` — end-to-end: paper DOI → lit-arc → journal-club deck → audit report. Each step is a callable Python script. *Proof:* directory + reference output.
2. `examples/manuscript-section/` — end-to-end: figures dir + bullet outline → manuscript section + citation audit. *Proof:* directory + reference output.
3. `examples/citation-cleanup/` — given a draft manuscript, run `citations.audit` + suggest fixes. *Proof:* directory + reference output.
4. Each example has a `README.md` walking through what the example does, what primitives it composes, and how to adapt it. *Proof:* READMEs.
5. Each example's outputs are committed (small enough to commit) to serve as the "reference target" for users adapting the example. *Proof:* reference outputs in dir.

**Files to create/modify:**
- Create: 3 directories under `examples/` each with `run.py`, `README.md`, `inputs/`, `expected-outputs/`
- Modify: top-level `examples/README.md` to index all examples

**Non-obvious context:** These are SEED examples — they make the threshold for external contribution lower because new contributors can copy the structure. Naming + structure consistency matters; don't get clever.

---

### Sub-goal 3.2: CONTRIBUTING.md with three-example rule

**Slug:** `contributing-md-with-three-example-rule`
**Invocation:** `/goal "write CONTRIBUTING.md establishing the three-example rule for new primitives + describing how to contribute examples, primitives, and bug fixes"`
**Advances:** Criterion #5 (enables non-Bobby contributions) + scope discipline
**Depends on:** 3.1
**Cap:** max-hours: 2 (smaller goal)

**Success criteria:**
1. `CONTRIBUTING.md` at repo root explains: how to set up dev env; how to add a new example workflow; how to add a new primitive (requires ≥3 concrete use cases — the three-example rule); how to file a bug report; how to use Discussions vs Issues. *Proof:* file exists with each section.
2. New issue templates in `.github/ISSUE_TEMPLATE/`: "I used vaultlab for X" (testimony), "Bug report," "Primitive request (with three-example justification)." *Proof:* templates exist.
3. Three-example rule is cross-referenced from the strategic spec's scope philosophy section. *Proof:* link.
4. `README.md` links prominently to CONTRIBUTING.md and Discussions. *Proof:* README diff.

**Files to create/modify:**
- Create: `CONTRIBUTING.md`, `.github/ISSUE_TEMPLATE/testimony.md`, `.github/ISSUE_TEMPLATE/bug.md`, `.github/ISSUE_TEMPLATE/primitive-request.md`
- Modify: `README.md`

**Non-obvious context:** This is also the start of Criterion #1 (adoption signal received) infrastructure — the testimony template is literally how the first signal will arrive.

---

### Sub-goal 3.3: Public testimony channel (Discussions enabled + README link)

**Slug:** `public-testimony-channel`
**Invocation:** `/goal "enable GitHub Discussions on vaultlab repo, pin a welcome thread, and link prominently from README"`
**Advances:** Criterion #1 (adoption signal — the channel for it to arrive on)
**Depends on:** 3.2
**Cap:** max-hours: 2

**Success criteria:**
1. GitHub Discussions enabled on `github.com/bobbyni819/vaultlab`. *Proof:* URL works.
2. Pinned welcome thread invites: "tell us how you used vaultlab," "ask about adapting primitives," "share examples." *Proof:* thread URL.
3. README has a prominent badge / link block above the fold pointing to Discussions + the "tell us how you used vaultlab" issue template. *Proof:* README diff.
4. The `## EVIDENCE` section of the north-star spec is updated to link the Discussions URL (so the channel is the literal proof-collection mechanism). *Proof:* spec diff.

**Files to create/modify:**
- Modify (on GitHub): repo settings → Discussions enable; create welcome thread
- Modify (in repo): `README.md`, `.claude/goals/vaultlab-north-star.md` (EVIDENCE section), KB mirror at `Sources/Notes/vaultlab-north-star-2026-05-14.md`

**Non-obvious context:** Discussions enablement is GitHub-side, not code-side. The /goal runner needs `gh` CLI auth working. If `gh` is missing the runner should `## BLOCKED` and ask Bobby to enable manually.

---

### Sub-goal 3.4: Tag and release v0.0.5

**Slug:** `tag-release-v005`
**Invocation:** `/goal "tag and release vaultlab v0.0.5 after Phase 1-3 sub-goals land, with a release-notes summary of the audit-enforcement + nature-reader + composability surface"`
**Advances:** Criterion #1 (a tagged release is what users `pip install`) + Criterion #4
**Depends on:** 1.1-1.5, 2.1, 3.1-3.3 all complete; tests green
**Cap:** max-hours: 2

**Success criteria:**
1. All Phase 1-3 sub-goals' goal files show ✅ on every criterion. *Proof:* spot-check goal files.
2. Full test suite green: `pytest` from a clean checkout. *Proof:* CI run.
3. `CHANGELOG.md` v0.0.5 section describes audit-manifest contract + nature-reader + examples + Discussions. *Proof:* CHANGELOG diff.
4. Git tag `v0.0.5` pushed; Trusted Publisher pipeline builds + uploads to PyPI. *Proof:* pypi.org/project/vaultlab/0.0.5/ resolves.
5. README badge updated to v0.0.5. *Proof:* README diff.

**Files to create/modify:**
- Modify: `CHANGELOG.md`, `pyproject.toml` (version), `README.md`
- Git: tag + push

**Non-obvious context:** Per Bobby's prior workflow, tags go to PyPI via Trusted Publisher. Don't skip git hooks. If hooks fail, fix and re-tag.

---

## Phase 4 — HTML pattern completion (Thariq's 20 patterns)

**Why fourth:** The HTML system is built (Track A, 7 consumers). Phase 4 closes coverage of the 20 patterns from the v0.0.4 plan that haven't been mapped yet. This is a strength-multiplier, not a foundation.

### Sub-goal 4.1: Audit which of Thariq's 20 patterns are already implemented

**Slug:** `html-pattern-coverage-audit`
**Invocation:** `/goal "audit which of the 20 HTML-effectiveness patterns are implemented in vaultlab.report and which remain gaps"`
**Advances:** Plan refinement (gives 4.2 a precise target)
**Depends on:** none
**Cap:** max-hours: 2

**Success criteria:**
1. New doc `docs/html-pattern-coverage.md` lists all 20 patterns from `G:/My Drive/Knowledge/vaultlab/Output/Plans/html-and-nature-skills-2026-05-12.html` (Section 8). *Proof:* doc.
2. Each pattern marked: ✅ implemented (with file ref), ⚠️ partial (with gap), ❌ missing. *Proof:* coverage table.
3. Top-5 highest-fit-for-vaultlab unimplemented patterns identified with rationale. *Proof:* prioritization section.
4. Output mirrored to KB at `G:/My Drive/Knowledge/vaultlab/Sources/Notes/html-pattern-coverage-2026-05-14.md`. *Proof:* mirror file.

**Files to create/modify:**
- Create: `docs/html-pattern-coverage.md`, KB mirror
- Reference (read-only): `G:/My Drive/Knowledge/vaultlab/Output/Plans/html-and-nature-skills-2026-05-12.html` section 8, `src/vaultlab/report/_components.py`

**Non-obvious context:** This audit feeds 4.2. The "highest-fit" filter is biology research-artifact relevance — patterns like "expandable evidence rows" and "two-way editor handoff" score high; abstract design patterns less so.

---

### Sub-goal 4.2: Implement top-5 unimplemented HTML patterns

**Slug:** `html-patterns-top5-implementation`
**Invocation:** `/goal "implement the top-5 unimplemented HTML patterns identified in the coverage audit"`
**Advances:** Criterion #5 (richer composable surface)
**Depends on:** 4.1
**Cap:** max-hours: 4

**Success criteria:**
1. 5 new components added to `vaultlab.report._components`. *Proof:* component count diff in `_components.py`.
2. Each new component has: a public function, a doc string, a unit test, and an example in the report SKILL.md. *Proof:* test count diff + SKILL.md diff.
3. At least 2 existing consumers (e.g., lit-arc HTML, deck-audit HTML) adopt at least one of the new components where it improves clarity. *Proof:* consumer file diffs.
4. Coverage doc updated to show those 5 patterns as ✅. *Proof:* doc diff.

**Files to create/modify:**
- Modify: `src/vaultlab/report/_components.py`, `src/vaultlab/report/_css.py`, `src/vaultlab/report/_js.py`, `src/vaultlab/report/SKILL.md`
- Modify: ≥2 consumers under `src/vaultlab/*/`*_html.py`
- Modify: `tests/report/test_components.py` (or split into per-component tests)
- Modify: `docs/html-pattern-coverage.md`

**Non-obvious context:** Don't add components for the sake of feature count. Each new pattern must demonstrably improve a real consumer. The "≥2 consumers adopt" criterion enforces this.

---

### Sub-goal 4.3: Update vaultlab.report SKILL.md with full pattern catalog

**Slug:** `report-skill-md-pattern-catalog`
**Invocation:** `/goal "update vaultlab.report SKILL.md with a complete pattern catalog matching the coverage audit"`
**Advances:** Criterion #2 (discoverability) + Criterion #5 (composability)
**Depends on:** 4.2
**Cap:** max-hours: 2

**Success criteria:**
1. SKILL.md has a "Patterns" section listing every implemented pattern with: short description, when-to-use, code example, screenshot/HTML preview path. *Proof:* SKILL.md diff.
2. Patterns are grouped by use case (status, comparison, narrative, decision-support, editor). *Proof:* section structure.
3. Each pattern entry cross-links to the relevant consumer that uses it. *Proof:* links resolve.

**Files to create/modify:**
- Modify: `src/vaultlab/report/SKILL.md`

**Non-obvious context:** This is the doc that future LLM/Claude-Code sessions read when deciding how to compose HTML outputs. Quality here pays compounding dividends.

---

## Phase 5 — Quality + maintenance (existing pending backlog)

**Why last:** These items were on the v0.0.4 plan but didn't make the cut. They're polish-class — meaningful improvements but not adoption-blocking. Sequenced last so Phase 1-4 reach completion first.

### Sub-goal 5.1: SPEC-B — 4 meta-agent roles

**Slug:** `spec-b-meta-agent-roles`
**Invocation:** `/goal "execute SPEC-B: add 4 meta-agent roles (journal_reviewer, pi_evaluator, adoption_evaluator, publication_guideline_compliance)"`
**Advances:** Composability (new agent surface)
**Depends on:** 2.4 (crosstalk policy), 2.5 (dispatch)
**Cap:** max-hours: 4

**Success criteria:**
1. 4 new role prompts under `src/vaultlab/roles/<role_name>/prompt.md` + `role_card.json`. *Proof:* dirs exist.
2. Each role has a unit test exercising the role on a fixture input. *Proof:* test count.
3. Roles are documented in `vaultlab/roles/SKILL.md` with when-to-invoke guidance. *Proof:* SKILL.md.
4. At least one workflow consumes one new role (e.g., manuscript polish optionally invokes `publication_guideline_compliance`). *Proof:* consumer diff.

**Files to create/modify:**
- Create: `src/vaultlab/roles/journal_reviewer/`, `pi_evaluator/`, `adoption_evaluator/`, `publication_guideline_compliance/` (this last one exists, audit + ensure consistency)
- Modify: `src/vaultlab/roles/SKILL.md`, `tests/roles/`

**Non-obvious context:** `publication_guideline_compliance` already exists (per grep result). Audit and complete it; don't recreate.

---

### Sub-goal 5.2: Slide templates — investor_pitch, lab_meeting, conference_talk, journal_club

**Slug:** `slide-templates-four-new`
**Invocation:** `/goal "add 4 slide templates: investor_pitch, lab_meeting, conference_talk, journal_club"`
**Advances:** Criterion #5 (richer composable surface for wet-lab teams)
**Depends on:** none
**Cap:** max-hours: 4

**Success criteria:**
1. 4 new modules under `src/vaultlab/slides/templates/<name>.py`. *Proof:* files exist.
2. Each template defines: section sequence, default slide types, time-budget hints, target audience. *Proof:* module shape.
3. Each template has a SKILL.md fragment describing when to use it. *Proof:* docs.
4. Each template has a unit test producing a sample deck plan. *Proof:* test count.
5. README's "use cases" section lists all available templates. *Proof:* README diff.

**Files to create/modify:**
- Create: 4 × `src/vaultlab/slides/templates/<name>.py`, 4 × `tests/slides/templates/test_<name>.py`
- Modify: `src/vaultlab/slides/templates/__init__.py`, `README.md`

**Non-obvious context:** `prelim_qual` template already exists — match its shape. Use real wet-lab + comp-bio conventions; don't invent generic structures.

---

### Sub-goal 5.3: Remaining slide layouts — equation, table, comparison-table, acknowledgments-grid

**Slug:** `slide-layouts-four-new`
**Invocation:** `/goal "add 4 slide layouts: equation, table, comparison-table, acknowledgments-grid"`
**Advances:** Criterion #5
**Depends on:** none
**Cap:** max-hours: 4

**Success criteria:**
1. 4 new layout functions in `vaultlab.slides.layouts`. *Proof:* signatures + tests.
2. Each layout respects the hard slide rules (Roboto, 28/24/18pt min, no overlap). *Proof:* audit run.
3. Each layout has a unit test producing a sample slide. *Proof:* test count.
4. `verify_slide_layouts` audit recognizes the new layouts. *Proof:* audit test.

**Files to create/modify:**
- Modify: `src/vaultlab/slides/layouts.py` (or split per layout if it's grown unwieldy)
- Modify: `src/vaultlab/slides/audit.py` to recognize new layouts
- Modify: `tests/slides/`

**Non-obvious context:** Bobby's "slide hard rules" feedback memory is binding. Audit BEFORE opening any deck for Bobby.

---

### Sub-goal 5.4: Self-review slide pass — read each rendered slide and critique

**Slug:** `slide-self-review-pass`
**Invocation:** `/goal "add a self-review pass that reads each rendered slide and critiques it against the hard rules + story-arc audit"`
**Advances:** Criterion #2 (audit-grade slides)
**Depends on:** 5.3
**Cap:** max-hours: 4

**Success criteria:**
1. `vaultlab.slides.self_review.review_deck(pptx_path) -> ReviewReport` runs per-slide checks: title length, bullet density, figure presence, overlap, color contrast, story-arc continuity. *Proof:* signature + tests.
2. Review report is emitted as HTML via the existing `audit_html` consumer. *Proof:* example output.
3. CLI: `vaultlab slides review <pptx>` calls the primitive. *Proof:* CLI test.

**Files to create/modify:**
- Create: `src/vaultlab/slides/self_review.py`, `tests/slides/test_self_review.py`
- Modify: `src/vaultlab/slides/cli.py`, `src/vaultlab/slides/audit_html.py` (extend if needed)

**Non-obvious context:** Bobby's existing `verify_slide_layouts` audit + `story-arc audit` together give most of this. The new layer is the unified review report that combines them per-slide.

---

### Sub-goal 5.5: Granular custom-figure handling (single plot, not multi-panel)

**Slug:** `granular-custom-figure-handling`
**Invocation:** `/goal "add granular custom-figure handling for single plots so figures.contract correctly handles non-multi-panel figures"`
**Advances:** Criterion #2 (figure audit fidelity)
**Depends on:** none
**Cap:** max-hours: 4

**Success criteria:**
1. `vaultlab.figures.contract` correctly detects single-panel vs multi-panel figures. *Proof:* parametrized unit test.
2. Single-panel figures are NOT panel-detected (don't try to subdivide). *Proof:* test case.
3. Layout dispatch uses the panel/single distinction. *Proof:* test.
4. Figure SKILL.md documents the distinction. *Proof:* doc diff.

**Files to create/modify:**
- Modify: `src/vaultlab/figures/contract.py`, `src/vaultlab/figures/detect.py` (or wherever panel detection lives)
- Modify: `tests/figures/test_contract.py`

**Non-obvious context:** Current panel-detection assumes ≥2 panels. The fix is to detect single-plot figures and skip the panel-cut step entirely.

---

## Cross-cutting concerns

These apply to EVERY sub-goal above; they're not their own sub-goals.

- **Each sub-goal's goal file** (auto-created by `/goal`) inherits CONTEXT from the strategic spec at `.claude/goals/vaultlab-north-star.md`. The runner SHOULD read it.
- **Each sub-goal** must finish with a green pytest run + a commit + a push.
- **Each sub-goal** must update the `## PROGRESS` section in the strategic spec when its EVIDENCE is populated.
- **Each sub-goal** that affects the public API should bump `CHANGELOG.md` under an "Unreleased" section; v0.0.5 release (sub-goal 3.4) cuts that into a tagged section.
- **Bobby's feedback memories apply throughout** (concise output, audit before opening decks, KB-state-aware, no skimping on tokens, etc.). The /goal runner inherits these.

## Self-review check (per writing-plans skill)

**Spec coverage:** All 7 criteria + 4 red lines + scope philosophy + form + reproducibility + persona-driven defaults are mapped:
- C1 (adoption signal) → 3.2, 3.3
- C2 (audit-grade) → 1.1, 1.2, 2.1, 5.4, 5.5
- C3 (plug-in companion) → 1.3, 2.2, 2.3, 2.4, 5.1
- C4 (<30-min first artifact) → 1.4, 1.5, 2.3, 2.5, 3.4
- C5 (composability proven) → 2.6, 3.1, 4.2, 4.3, 5.1, 5.2, 5.3
- C6 (tests green) → enforced per-sub-goal
- C7 (public evidence) → strategic spec's PROGRESS/EVIDENCE updated per-sub-goal
- Red Lines 1-4 → 1.1, 1.2

**Placeholder scan:** No TBDs, no "implement appropriately." Every sub-goal has measurable success criteria with proof types.

**Type consistency:** Function names + paths used across sub-goals are internally consistent (e.g., `build_paper_reader` from 2.1 isn't redefined elsewhere; `AuditManifest` from 1.2 is referenced consistently).

## Execution handoff

Two execution options:

1. **Sub-goal at a time via `/goal`** (recommended). Bobby picks the next unblocked sub-goal from the catalog above and invokes `/goal "<one-line outcome>"`. The runner creates `.claude/goals/<slug>.md` and executes. This matches the autonomous-work mode Bobby designed `/goal` for.

2. **Inline execution via `superpowers:executing-plans`** — execute multiple sub-goals in one session with checkpoint reviews between them. Only choose this if Bobby wants a single long session and to skip per-sub-goal /goal-file creation.

**Recommendation: option 1.** Phase 1 sub-goals 1.1, 1.2, 1.3 can be parallelized; everything else is sequential within a phase. Start with 1.1.

## Files referenced

- Strategic spec: `~/Downloads/vaultlab/.claude/goals/vaultlab-north-star.md`
- This plan (canonical): `~/Downloads/vaultlab/.claude/goals/vaultlab-north-star-plan.md`
- KB mirror of plan: `G:/My Drive/Knowledge/vaultlab/Sources/Notes/vaultlab-north-star-plan-2026-05-14.md`
- HTML+nature-skills exploration: `G:/My Drive/Knowledge/vaultlab/Output/Plans/html-and-nature-skills-2026-05-12.html`
- nature-reader source: `C:/Users/bobby/Downloads/nature-skills/skills/nature-reader/SKILL.md`
- `/goal` runner: `~/.claude/commands/goal.md`
