# vaultlab.roles

The cast of agent personas vaultlab puts on when it needs an expert to draft, challenge, interpret, or audit something — each one a plain-language prompt on disk, not a Python string.

Plain-language companion: the "Multi-agent meetings (crosstalk)" section of `vaultlab-subsystems.md` (in the KB) explains the panel these roles staff. Architectural sketch: see the `vaultlab.roles` entry in [`docs/architecture.md`](../../../docs/architecture.md).

## What it is

When vaultlab pressure-tests a finding, drafts a methods paragraph, or audits a deck, it does not ask "the LLM" in the abstract — it asks a *named role* with a specific posture: a Data Analyst who refuses to describe numbers from memory, a Methods Critic who hunts for confounds, a Rigor Auditor who checks every claim resolves to a real summary. This package is where those roles live. Each role is a directory holding two files — a markdown `prompt.md` (the verbatim system prompt the LLM sees) and a `metadata.yaml` sidecar (name, mode, focus areas, evaluation criteria, output format) — so a scientist can iterate on a role's behaviour by editing markdown without touching code (vaultlab Invariant 7: markdown is the user-facing interface). The runner and the workflows (`crosstalk`, `deep_think`) load these roles and stage them into bounded multi-agent meetings; the audit slash commands load them one at a time to grade an artifact. The roles themselves are inert prompt+metadata bundles — they describe a posture, they do not call an LLM.

## Public surface

From `vaultlab.roles.__init__` (`__all__`):

- `Role` — the canonical agent-persona dataclass (re-exported from `vaultlab.runner.models`); holds the system prompt plus metadata and renders a per-task prompt via `prompt_for(...)`.
- `load_role(role_id)` — load one role by its directory name into a `Role`.
- `list_roles()` — sorted list of the role ids discoverable on disk.
- `load_all_roles()` — load every discoverable role into a `dict[role_id -> Role]`.
- `ROLE_TEMPLATES` — lazy dict-style view over every role on disk (deferred scan; supports `in`, `[]`, `.get`, `.items()`).
- `roles_for(meeting_type, mode=...)` — the canonical role *cast* for a named meeting type (`reasoning`, `deep_think`, `team_meeting`, `critique`, `visual_deep_think`, `critiqued_<role>`, …); swaps analyst/critic by `Mode` (data-analysis vs literature-review).
- `enforce_hedge(text)` — deterministic hedged-voice checker; scans text for a narrow, high-precision set of overclaiming phrases (`proves`, `demonstrates that`, …) and returns one flag per occurrence.
- `RoleNotFoundError` — raised when `load_role` is handed an unknown role id.

From `vaultlab.roles._invoke` (the SPEC-B audit-role auto-loader; imported directly, not re-exported by the package barrel):

- `prepare_audit(role_id, artifact_path, ...)` — assemble a complete `AuditPrompt` bundle for an audit role: loads the role, reads the artifact, pulls the matching journal guidelines, and (best-effort) the project KB-context preamble.
- `AuditPrompt` — the assembled invocation bundle; `assembled_user_prompt()` renders the artifact + journal rules + KB context as one user-prompt string.
- `aggregate_audits(reports)` — combine the JSON verdicts of several audit roles on one artifact into a single worst-case `AggregatedAudit`.
- `AggregatedAudit` — the combined per-artifact verdict (per-role verdicts, worst-case verdict + evidence axis, issue counts).
- `available_journal_yaml()` / `load_journal_guideline_yaml(basename)` / `load_journal_guideline_md(...)` — locate and load the bundled journal-guideline rules (yaml) and KB-side prose (md).
- `META_AGENT_ROLES` — the tuple of role ids that follow the SPEC-B audit contract (`journal_reviewer`, `expert_reviewer`, `adoption_evaluator`, `publication_guideline_compliance`).
- `JOURNAL_TARGET_DEFAULTS` — map from a project's target-journal slug to the shared guideline basename (Cell-family → `cell`, etc.).
- `AuditPreparationError` — raised when an audit prompt can't be assembled.

### The roles on disk

Each is a `<role_id>/{prompt.md, metadata.yaml}` pair. Two `mode`s: data-analysis roles and literature-review roles (the latter swapped in automatically when a meeting runs over a paper corpus).

- `data_analyst` — loads the data with real code and reports exact values, distributions, and outliers; no hedging, no remembering numbers.
- `domain_expert` — interprets findings in biological terms, proposes mechanism, connects findings across the run.
- `methods_critic` — the data-analysis critic: challenges significance, null comparisons, and confounds.
- `synthesizer` — weaves the panel's findings into a narrative arc with a priority ranking.
- `narrator` — turns a finding into plain-English narrative for a KB concept page.
- `figure_lead` — plans which panels group together and the visual hook (brainstorm cast).
- `figure_reader` — reads an existing figure image: visual patterns, block structure, sign reversals.
- `team_lead` (display name "Principal Investigator") — frames a team meeting and drives the group to a decision.
- `literature_surveyor` — the literature-mode analyst: search, DOI verification, paper-relevance rating.
- `literature_critic` — the literature-mode critic: source quality, consensus, replication.
- `rigor_auditor` — final-gate audit; checks every claim resolves to a `[[doi-slug]]` summary, page markers resolve, references are cited, claim language matches evidence tier. JSON-only output.
- `journal_reviewer` / `expert_reviewer` / `adoption_evaluator` / `publication_guideline_compliance` — the SPEC-B audit roles (see `META_AGENT_ROLES`): grade an artifact the way a journal reviewer, a PI/advisor, a fresh new user, or a deterministic figure-guideline checker would, emitting structured JSON.

## How it fits

- **Reads from disk only.** A role is built entirely from its `prompt.md` + `metadata.yaml`; `load_*` is pure file I/O projected into the `Role` dataclass. The audit auto-loader additionally reads the bundled journal-guideline yaml (`vaultlab/data/journal_guidelines/`), optional KB-side guideline prose (`<kb_root>/External/journal-guidelines/`), and — when a project is onboarded — the KB-context preamble from `vaultlab.runner.kb_context.compose_preamble`.
- **Consumed by the runner and workflows.** `roles_for(...)` hands a cast to `vaultlab.runner.meetings` / `vaultlab.workflows.crosstalk` / `vaultlab.workflows.deep_think`, which call `Role.prompt_for(context, task, prior_outputs)` to render each turn's system prompt. The audit slash commands (`/journal-reviewer-audit`, `/expert-reviewer-audit`, `/adoption-evaluator-audit`, `/publication-guideline-audit`) use `prepare_audit` → `AuditPrompt.assembled_user_prompt()`.
- **Pipeline position.** This is the orchestration layer's persona library: it sits between the runner (which executes meetings) and the prompt content on disk. Role *identifiers* are an API contract — prompts may change, ids may not.

## What it does NOT do

- It does not call an LLM or run a meeting — a `Role` is an inert prompt+metadata bundle; `vaultlab.runner` does the calling.
- It does not embed prompt text in Python; the prompt lives in the sibling `prompt.md`, and a triple-quoted prompt in a `.py` here would be a bug (Invariant 7).
- `enforce_hedge` does not rewrite text or parse grammar — it flags a deliberately narrow set of overclaiming phrases (high precision over recall) and leaves the fix to the caller.
- `aggregate_audits` does not re-audit anything; it only combines verdict JSON that the audit roles already produced.

## Files

- `__init__.py` — the public barrel: `Role`, `load_role`, `list_roles`, `load_all_roles`, `ROLE_TEMPLATES`, `roles_for`, `enforce_hedge`, plus the `_MEETING_TYPE_ROLES` cast table.
- `_loader.py` — discovers `<role_id>/` directories, parses `prompt.md` + `metadata.yaml`, and builds `Role` instances; defines `RoleNotFoundError`.
- `_invoke.py` — the SPEC-B audit-role auto-loader: `prepare_audit`, `AuditPrompt`, `aggregate_audits`, journal-guideline loaders, `META_AGENT_ROLES`.
- `_guardrails.py` — `enforce_hedge` plus the `BANNED_ASSERTIONS` / `ALLOWED_HEDGES` reference lists.
- `<role_id>/prompt.md` — the verbatim system prompt for each role (the file you edit to change behaviour).
- `<role_id>/metadata.yaml` — name, mode, icon, focus areas, evaluation criteria, output format, allowed tools.

## See also

- [`../runner/README.md`](../runner/README.md) — the `Role` dataclass home (`runner/models.py`), `Meeting`/`Agenda`/`Mode`, and the meeting executor that calls these roles.
- `../workflows/crosstalk.py` + `../workflows/deep_think.py` — the workflows that stage role casts into bounded multi-agent meetings (`../workflows/crosstalk_policy.md` documents the panel-vs-single-pass policy).
- [`docs/architecture.md`](../../../docs/architecture.md) — the `vaultlab.roles` architectural entry and the orchestration diagram.
- `READ_FIRST.md` (repo root) — when to run `methods_critic` vs `rigor_auditor`, and the role-pass-before-ship discipline.
- Individual `<role_id>/prompt.md` files — the source of truth for what each persona actually does.
