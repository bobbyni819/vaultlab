# vaultlab.roles

The cast of agent personas vaultlab puts on when it needs an expert to draft, challenge, interpret, or audit something — each one a plain-language prompt on disk, not a Python string.

Plain-language companion: the "Multi-agent meetings (crosstalk)" section of `vaultlab-subsystems.md` (in the KB) explains the panel these roles staff. Architectural sketch: see the `vaultlab.roles` entry in [`docs/architecture.md`](../../../docs/architecture.md).

## What it is

When vaultlab pressure-tests a finding, drafts a methods paragraph, or audits a deck, it does not ask "the LLM" in the abstract — it asks a *named role* with a specific posture: a Data Analyst who refuses to describe numbers from memory, a Methods Critic who hunts for confounds, a Rigor Auditor who checks every claim resolves to a real summary. This package is where those roles live. Each role is a directory holding two files — a markdown `prompt.md` (the verbatim system prompt the LLM sees) and a `metadata.yaml` sidecar (id, name, mode, icon, focus areas, evaluation criteria, communication style, output format, allowed tools) — so a scientist can iterate on a role's behaviour by editing markdown without touching code (vaultlab Invariant 7: markdown is the user-facing interface). The runner and the workflows (`crosstalk`, `deep_think`, `ensemble`, `lit`) load these roles and stage them into bounded multi-agent meetings; the audit slash commands load them one at a time to grade an artifact. The roles themselves are inert prompt+metadata bundles — they describe a posture, they do not call an LLM.

## Public surface

From `vaultlab.roles.__init__` (`__all__`):

- `Role` — the canonical agent-persona dataclass (re-exported from `vaultlab.runner.models`); holds the system prompt plus metadata and renders a per-task prompt via `prompt_for(...)`.
- `load_role(role_id)` — load one role by its directory name into a `Role`.
- `list_roles()` — sorted list of the role ids discoverable on disk.
- `load_all_roles()` — load every discoverable role into a `dict[role_id -> Role]`.
- `ROLE_TEMPLATES` — lazy dict-style view over every role on disk (deferred scan; supports `in`, `[]`, `.get`, `.items()`).
- `roles_for(meeting_type, mode=...)` — the canonical role *cast* for a named meeting type. Nine built-in meeting types (`reasoning`, `synthesis`, `brainstorm`, `narrate`, `deep_think`, `team_meeting`, `critique`, `figure_read`, `visual_deep_think`) plus the `critiqued_<role>` form (pair any role with the auto-critic). Swaps the analyst and critic slots by `Mode`: data-analysis uses `data_analyst` + `methods_critic`; literature-review uses `literature_surveyor` + `literature_critic`. Raises `ValueError` on an unknown meeting type or an unknown `critiqued_` base.
- `enforce_hedge(text)` — deterministic hedged-voice checker; scans text for a narrow, high-precision set of overclaiming phrases (`proves`, `demonstrates that`, `we conclude that`, `clearly indicates`, …) and returns one human-readable flag per occurrence (with the offending phrase + character offset). It does NOT rewrite — the caller decides what to do. Already wired into the analysis interpretation pass (`vaultlab.analysis.pipeline` runs it alongside `verify_numeric` on each generated interpretation).
- `RoleNotFoundError` — raised when `load_role` is handed an unknown role id.

From `vaultlab.roles._invoke` (the SPEC-B audit-role auto-loader; imported directly, not re-exported by the package barrel):

- `prepare_audit(role_id, artifact_path, ...)` — assemble a complete `AuditPrompt` bundle for an audit role: loads the role, reads the artifact, resolves the target journal (explicit arg → project config → `"cell"` default), pulls the matching journal-guideline yaml (`<journal>.yaml` + cross-cutting `_common.yaml`) plus optional KB-side prose, and (best-effort, when a project slug + KB root resolve) the project KB-context preamble via `runner.kb_context.compose_preamble`. KB context and journal prose are both best-effort — a missing file degrades to a thinner prompt rather than an error. Text artifacts (`.md/.txt/.yaml/.json/.py`) are read inline; binary/visual artifacts (`.png/.pdf/.pptx/.docx/.eps/.tiff`) become a `<binary-artifact …>` marker instructing the auditor to use vision/binary-aware tools. Raises `AuditPreparationError` for a missing role or missing artifact.
- `AuditPrompt` — the assembled invocation bundle (role, artifact text + resolved path, journal yaml, common yaml, journal prose, target journal, project slug, optional KB-context bundle); `assembled_user_prompt()` renders KB context + journal prose + enforceable yaml rules + common rules + the artifact + a closing task instruction (output ONLY the role's structured JSON) as one `---`-delimited user-prompt string.
- `aggregate_audits(reports)` — combine the JSON verdicts of several audit roles on one artifact into a single worst-case `AggregatedAudit`. Reads the verdict from whichever key the role used (`verdict`, `verdict_journal_style`, or — for `expert_reviewer` — synthesized from its two sign-off booleans), sums issue counts by severity across roles, and applies an *issue-count override*: if any role logged a `fail`/`major` issue, the aggregate verdict is downgraded even when each role rated itself "ship" (catches a role that lists problems but mis-rates its own verdict). Verdict ranking runs `reject < fail/bounce_risk < needs_major < needs_minor < ship_with_revisions < ship`; evidence ranking runs `inadequate < incomplete < solid < convincing < compelling < exceptional`.
- `AggregatedAudit` — the combined per-artifact verdict (per-role verdicts, worst-case verdict + worst-case evidence axis, issue counts by severity, role count).
- `available_journal_yaml()` / `load_journal_guideline_yaml(basename)` / `load_journal_guideline_md(...)` — locate and load the bundled journal-guideline rules (yaml) and KB-side prose (md).
- `META_AGENT_ROLES` — the tuple of role ids that follow the SPEC-B audit contract (`journal_reviewer`, `expert_reviewer`, `adoption_evaluator`, `publication_guideline_compliance`).
- `JOURNAL_TARGET_DEFAULTS` — map from a project's target-journal slug to the shared guideline basename (Cell-family → `cell`, etc.).
- `AuditPreparationError` — raised when an audit prompt can't be assembled.

### The roles on disk

Each is a `<role_id>/{prompt.md, metadata.yaml}` pair. Two `mode`s: data-analysis roles and literature-review roles (the latter swapped in automatically when a meeting runs over a paper corpus).

- `data_analyst` — loads the data with real code (Bash/Read) and reports exact values, distributions, and outliers; no hedging, no remembering numbers — every finding must cite data source + query + the exact command run.
- `domain_expert` — interprets findings in biological terms, proposes mechanism, connects findings across the run.
- `methods_critic` — the data-analysis critic: challenges significance, null comparisons, confounds, and multiple-testing; runs a *deep-verification* pass (decompose a claim into load-bearing sub-assumptions) and a *simulation* pass (walk the mechanism step by step for the artefact that could fake the result) lifted from the AI co-scientist (Gottweis 2025); rates each finding `ROBUST` / `NEEDS_VALIDATION` / `WEAK` / `UNSUPPORTED`.
- `synthesizer` — weaves the panel's findings into a manuscript narrative arc (lead vs supporting vs independent findings), does gap analysis, and ranks all findings into Tier 1/2/3.
- `narrator` — turns ONE finding into a self-contained plain-English KB concept page, folding in the domain expert's interpretation and the methods critic's verdict, citing exact values from the reasoning chain.
- `figure_lead` — plans which panels group together and the visual hook (brainstorm cast).
- `figure_reader` — reads an existing figure *image* (must Read the PNG/PDF — never describe an unseen figure): figure type, block structure, orderings/diagonals, sign reversals, outliers, anomalies; flags mislabeled/clipped/illegible axes.
- `team_lead` (display name "Principal Investigator") — frames a team meeting, synthesizes member input mid-meeting, and closes with a structured summary (Agenda / Team Member Input / Recommendation / Answers / Next Steps) — makes the final call even against team disagreement.
- `literature_surveyor` — the literature-mode analyst: real `vaultlab.research` search (never paper names from memory), DOI verification, per-paper relevance rating, consensus + gap analysis.
- `literature_critic` — the literature-mode critic: source quality, consensus, replication.
- `rigor_auditor` — final-gate audit; checks every "X showed Y" claim resolves to a `[[doi-slug]]` summary in `Wiki/Summaries`, every `[pN]` page marker resolves to a real PDF page, every reference is cited at least once, and claim language matches evidence tier (no overclaim). JSON-only output (`passed` + severity-tagged `issues`).
- `journal_reviewer` / `expert_reviewer` / `adoption_evaluator` / `publication_guideline_compliance` — the SPEC-B audit roles (see `META_AGENT_ROLES`): grade an artifact the way a Cell/Nature reviewer (7-check journal pass → `verdict` + `evidence_axis`), a PI/advisor (two-axis grant/paper sign-off + the expert questions a reader would ask), a fresh new user (first-30-minutes friction-list), or a deterministic figure-guideline checker (DPI / font sizes / colorblind-safe palette / hue count / panel-label convention / axis treatment / color space, all mechanical) would — each emitting role-specific structured JSON.

## How it fits

- **Reads from disk only.** A role is built entirely from its `prompt.md` + `metadata.yaml`; `load_*` is pure file I/O projected into the `Role` dataclass. The audit auto-loader additionally reads the bundled journal-guideline yaml (`vaultlab/data/journal_guidelines/`), optional KB-side guideline prose (`<kb_root>/External/journal-guidelines/`), and — when a project is onboarded — the KB-context preamble from `vaultlab.runner.kb_context.compose_preamble`.
- **Consumed by the runner and workflows.** `vaultlab.runner.meetings` re-exports `roles_for` and calls it inside `build_meeting` to resolve the default cast for a meeting type; the workflows then reach for the roles they need by name — `crosstalk.py` pulls specific entries out of `ROLE_TEMPLATES` (`narrator`, `figure_lead`, `methods_critic`, `synthesizer`, `rigor_auditor`), `deep_think.py` calls `load_role(...)`, and `ensemble.py` / `lit.py` likewise route through the package. All of them ultimately call `Role.prompt_for(session_context, task, prior_outputs)` to render each turn's system prompt (which wraps the role's `system_prompt`, the session context, prior agent outputs, the rendered `Agenda`, and the role's `output_format`). The audit slash commands (`/journal-reviewer-audit`, `/expert-reviewer-audit`, `/adoption-evaluator-audit`, `/publication-guideline-audit`) use `prepare_audit` → `AuditPrompt.assembled_user_prompt()`.
- **Slash commands this package backs.** The four SPEC-B audit roles map one-to-one to `/journal-reviewer-audit`, `/expert-reviewer-audit`, `/adoption-evaluator-audit`, and `/publication-guideline-audit` (each loads its role via `prepare_audit`). The data-analysis cast staffs the multi-agent commands `/explore-data`, `/next-analysis`, and `/debug` (analyst → domain_expert → methods_critic → synthesizer), while `/code-review` runs the `rigor_auditor` pass cross-referenced against the project decisions-log; `/lit-arc` and `/build-deck` stage role casts through the runner + workflows. `methods_critic` and `rigor_auditor` are the two roles `READ_FIRST.md` names directly for the role-pass-before-ship discipline.
- **Pipeline position.** This is the orchestration layer's persona library: it sits between the runner (which executes meetings) and the prompt content on disk. Role *identifiers* are an API contract — prompts may change, ids may not.

## What it does NOT do

- It does not call an LLM or run a meeting — a `Role` is an inert prompt+metadata bundle; `vaultlab.runner` does the calling.
- It does not embed prompt text in Python; the prompt lives in the sibling `prompt.md`, and a triple-quoted prompt in a `.py` here would be a bug (Invariant 7).
- `enforce_hedge` does not rewrite text or parse grammar — it flags a deliberately narrow set of overclaiming phrases (high precision over recall) and leaves the fix to the caller.
- `aggregate_audits` does not re-audit anything; it only combines verdict JSON that the audit roles already produced.
- `prepare_audit` does not require KB context or journal prose to succeed — both are best-effort. A missing journal-prose file or an un-onboarded project yields a thinner prompt, not an error; only a missing role or missing artifact raises `AuditPreparationError`.
- The loader does not validate `kb_outputs`, `tools_allowed`, or the prompt body against any schema beyond requiring `prompt.md` + `metadata.yaml` to exist and the yaml to parse as a mapping — role behaviour is governed by the prompt text, not by structural validation.

## Files

- `__init__.py` — the public barrel: `Role`, `load_role`, `list_roles`, `load_all_roles`, `ROLE_TEMPLATES`, `roles_for`, `enforce_hedge`, plus the `_MEETING_TYPE_ROLES` cast table.
- `_loader.py` — discovers `<role_id>/` directories, parses `prompt.md` + `metadata.yaml`, and builds `Role` instances; defines `RoleNotFoundError`.
- `_invoke.py` — the SPEC-B audit-role auto-loader: `prepare_audit`, `AuditPrompt`, `aggregate_audits`, journal-guideline loaders, `META_AGENT_ROLES`.
- `_guardrails.py` — `enforce_hedge` plus the `BANNED_ASSERTIONS` / `ALLOWED_HEDGES` reference lists.
- `<role_id>/prompt.md` — the verbatim system prompt for each role (the file you edit to change behaviour). Stripped of surrounding whitespace on load.
- `<role_id>/metadata.yaml` — `id`, `name`, `mode`, `icon`, `description`, `focus_areas`, `evaluation_criteria`, `communication_style`, `output_format`, `tools_allowed`. The loader fills sensible defaults for any missing key (name defaults to the title-cased directory name; mode to `data_analysis`). Note: some role yaml files also carry a `kb_outputs` hint (which `vaultlab.kb.paths` location a role's output is routed to); this key is documentation for the routing convention and is NOT loaded onto the `Role` dataclass.

## See also

- [`../runner/README.md`](../runner/README.md) — the `Role` dataclass home (`runner/models.py`), `Meeting`/`Agenda`/`Mode`, and the meeting executor that calls these roles.
- `../workflows/crosstalk.py` + `../workflows/deep_think.py` — the workflows that stage role casts into bounded multi-agent meetings (`../workflows/crosstalk_policy.md` documents the panel-vs-single-pass policy).
- [`docs/architecture.md`](../../../docs/architecture.md) — the `vaultlab.roles` architectural entry and the orchestration diagram.
- `READ_FIRST.md` (repo root) — when to run `methods_critic` vs `rigor_auditor`, and the role-pass-before-ship discipline.
- Individual `<role_id>/prompt.md` files — the source of truth for what each persona actually does.
