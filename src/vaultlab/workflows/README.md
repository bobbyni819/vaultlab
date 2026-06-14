# vaultlab.workflows

Packages a multi-role agent meeting into a structured plan a slash command (or a Python script) can execute — and runs it.

Plain-language subsystem framing: see the "Multi-agent meetings (crosstalk)" section of `G:/My Drive/Knowledge/vaultlab/Wiki/Concepts/vaultlab-subsystems.md` (this package is the engine behind that "small internal panel of role-playing experts who draft, challenge, and reconcile" story). Architecture context: `docs/architecture.md` (the `vaultlab.workflows` node sits below `vaultlab.runner` and fans out into research / citations / figures / slides / manuscript).

## What it is

This is the orchestration layer. A *workflow* takes a research task — "assess these findings," "pick the best papers for an arc," "plan this deck," "draft the synthesis" — and assembles the right cast of agent roles (Analyst, Domain Expert, Methods Critic, Synthesizer, and friends) into a `WorkflowPlan`: a meeting configuration plus one executable step per agent turn plus a provenance stub. Builder functions (`plan_*`) construct the plan without ever calling an LLM; runners (`run_workflow`, `run_workflow_with_reflection`) execute it, feeding each step's real output into the prompts of later steps so the conversation actually accumulates. It exists because vaultlab's quality comes from disciplined multi-pass reasoning — an analyst proposing, a critic challenging, a synthesizer reconciling — rather than a single-shot answer; the patterns here are lifted from virtual-lab (the meeting shape) and AI-Scientist (the reflection loop and the critic ensemble). The `agent_fn` you hand a runner *is* the LLM — inside a Claude Code session it's a closure that spawns the Agent tool; in tests it's a deterministic stub — so this module holds no SDK calls of its own.

## Public surface

Data classes and receipts:

- `WorkflowPlan` — what every builder returns: the `Meeting`, the executable `RunPlan`, a `Provenance` stub, and an optional canonical output path for the "final" file.
- `DeepThinkEnsembleBundle` — the four-phase ensemble-critic bundle (pre-critic / N critics / meta-review / synthesis) as separate plans, with `all_plans` to flatten them in execution order.
- `Provenance` — the YAML-frontmatter receipt written above each workflow output (who generated it, mode, topic, round, tags, structured `params`).
- `CrosstalkResult` — the structured outcome of an adversarial meeting: the synthesizer's parsed `final_output`, the per-turn `rounds` transcript, runtime, a `crosstalk_status` (one of the literal strings `"complete"`, `"converged"`, `"incomplete (timeout)"`, `"fallback (callback failed)"` — match on the full string, not a truncated form), `critic_spread`, and a recurring-concern `meta_review` checklist.
- `DeckPlanTask` — the prepared, LLM-ready deck-plan task (prompt + system prompt + JSON schema + corpus inputs); produced without calling an LLM.
- `RunnerCallback` / `PlanGeneratorCallback` — callback type aliases for "the thing that runs a meeting" and "the thing that turns a deck-plan task into JSON" (both are the LLM).
- `TaskSpec` / `Weight` — describe a unit of LLM work and the three model tiers (`light` / `medium` / `heavy`).
- `MAX_N_ROUNDS` (5) / `MEETING_TIMEOUT_SECONDS` (600) / `PROVENANCE_INDEX` / `WEIGHT_TO_DEFAULT_MODEL` — the hard caps and lookup tables the rest of the package reads.

Runners:

- `run_workflow` — execute a `WorkflowPlan` step-by-step, writing each output with provenance and injecting prior outputs forward; supports `resume=True` to pick up a crashed run from the files already on disk.
- `run_workflow_with_reflection` — same, but wraps the final (or named) step in a draft-refine-or-stop reflection loop (AI-Scientist pattern).
- `run_deep_think_with_ensemble_critic` — execute a `DeepThinkEnsembleBundle` end-to-end, wiring each phase's output into the next.

Builders (each returns a single `WorkflowPlan`, a bundle, or a `(plans, merge/meta-plan)` tuple — noted per entry; none call an LLM):

- `plan_deep_think_round` — one classic round: Analyst → Domain Expert → Methods Critic → Synthesizer.
- `plan_round_from_critic_tests` — auto-build the next round's agenda from the prior round's priority-tagged (`[CRITICAL]`/`[HIGH]`/...) Critic tests.
- `plan_deep_think_with_ensemble_critic` — the same cycle but with N independent critics and an Area Chair meta-reviewer in place of the single Critic.
- `plan_ensemble_critic` — N independent Methods Critics + one strictest-wins (Area Chair) meta-reviewer. Unlike the single-plan builders above, it returns a two-element tuple `(critic_plans, meta_plan)` — `list[WorkflowPlan]` of the N critic runs plus one `WorkflowPlan` for the meta-review; run the critics (ideally in parallel), collect their outputs, then run the meta-plan over them.
- `plan_synthesis` — the Synthesizer alone over existing session findings (re-narrate without redoing the analysis).
- `plan_parallel_runs` — N independent deep-thinks at higher temperature + one Synthesizer merge ("pick the best of each, not the average"). Also returns a two-element tuple `(parallel_plans, merge_plan)` — `list[WorkflowPlan]` of the N parallel runs plus one `WorkflowPlan` for the merge; run the parallel plans, feed their outputs forward, then run the merge.
- `plan_brainstorm_figures` — FigureLead + Critic propose the canonical `figure-plan.md`.
- `plan_narrate_finding` — Narrator writes one finding's KB concept page (one finding per file).
- `plan_lit_dive` — Literature Surveyor drives paperclip's stateful search → map → reduce workflow.

Crosstalk meetings (drop-in replacements for the single-shot picker / arc / deck-plan callbacks, with matching `final_output` schemas):

- `adversarial_picker_meeting` — Surveyor proposes top-N picks, critic challenges, synthesizer chooses.
- `adversarial_arc_meeting` — Analyst drafts the history/development/SOTA lineage arc, critics challenge, synthesizer integrates.
- `adversarial_deck_plan_meeting` — Narrator + FigureLead + Methods Critic plan the deck; synthesizer emits the typed slide plan.
- `rigor_audit` — final-gate review by the `rigor_auditor` role; returns `{"passed": bool, "issues": [...]}` (claim grounding, page markers, references cited, overclaiming).
- `write_crosstalk_artifacts` — write a meeting's transcript + per-turn files into a run directory.
- `append_decisions_log_entry` — append a one-block-per-meeting record to a project's `decisions-log.md`.

Deck-plan generation (content-aware; the LLM reasons about the story arc, a deterministic renderer executes it):

- `prepare_deck_plan_task` — build a `DeckPlanTask` from a corpus + summaries + figures (no LLM call).
- `deck_plan_response_schema` — the JSON schema the LLM's deck-plan response must match.
- `render_plan_from_response` — validate the LLM's JSON, drop invalid slides, auto-append a references slide, emit the dict-plan `vaultlab.slides.build_from_plan` consumes.
- `generate_deck_plan` — top-level orchestrator: prepare → callback → render, with a mechanical bucket-leader fallback when no `plan_callback` is supplied.

Crosstalk policy (pure, deterministic — decides whether the round-table fires at all):

- `should_invoke` — fire crosstalk by default for synthesis-shaped tasks, skip for mechanical/extraction ones.
- `skip_reason` — the human-readable reason recorded on a run's provenance when crosstalk is skipped.
- `CrosstalkContext` — the typed input to those decisions (task kind, evidence-source count, optional explicit round budget).

Task-weight dispatch (route LLM work to a model tier):

- `classify` — classify a `TaskSpec` into `light` / `medium` / `heavy`.
- `model_for_weight` / `model_for_task` — resolve the configured model id for a weight (or a whole task), honouring `~/.config/vaultlab/dispatch.json`.

Provenance plumbing:

- `write_with_provenance` — write a markdown file with a frontmatter receipt, append to the JSONL index, and emit the canonical sidecars.
- `read_provenance` — parse the frontmatter receipt back out of a file.

## How it fits

A builder reads the project's context off the `cfg` it's handed and, for stateful builders, globs prior work — the session summary (`Output/research-session.json`), branch notes, and the latest `synthesis-*.md` — so a meeting starts from what the project already knows rather than from zero. Every analyst/critic/synthesizer prompt is wrapped with the KB-context preamble (`vaultlab.runner.kb_context.prepend_preamble`) so spawned sub-agents inherit the project's prior findings — CLAUDE.md commitment #7. The meeting machinery itself (`Meeting`, `Agenda`, `build_meeting`, the role rotation, `ClaudeCodeRunner`) lives in `vaultlab.runner` and `vaultlab.roles`; this package composes those primitives into task-shaped plans.

Downstream, the crosstalk meetings are wired straight into the pipelines: `adversarial_picker_meeting` / `adversarial_arc_meeting` back `/lit-arc` via `vaultlab.research.picker` and `vaultlab.research.lineage`; `adversarial_deck_plan_meeting` and the `generate_deck_plan` family feed `vaultlab.slides.build_from_plan` for `/build-deck`; `rigor_audit` is the final gate before a deck or methods doc ships. Every output carries a `Provenance` receipt (frontmatter in the `.md` plus a JSONL index plus the `vaultlab.provenance` sidecars), and a meeting's decision can be appended to the project's `decisions-log.md` — so the KB stays the audit trail.

## What it does NOT do

- It does **not** call an LLM or any model SDK. The `agent_fn` / `runner_callback` / `plan_callback` you supply *is* the LLM; this package only builds the prompts and routes the structured results.
- It does **not** loop forever. Adversarial meetings are hard-capped at `MAX_N_ROUNDS` (5) and a 10-minute wall-clock per meeting; beyond that the runner returns a partial transcript rather than spiralling (the AI-Scientist diminishing-returns finding).
- The crosstalk **policy** (`should_invoke`) is instrumentation, not flow-control, for the deep-think bundle: that bundle always executes and records *why* crosstalk did or didn't fire on every phase's provenance, rather than silently skipping.
- It does **not** define the agent roles or the low-level meeting engine — those are `vaultlab.roles` and `vaultlab.runner`. This package only orchestrates them.

## Files

- `__init__.py` — the public barrel (the `__all__` documented above).
- `_models.py` — `WorkflowPlan` and `DeepThinkEnsembleBundle`.
- `_runner.py` — `run_workflow`, `run_workflow_with_reflection`, prior-output injection, and resume-from-disk.
- `_provenance.py` — the `Provenance` frontmatter receipt, `write_with_provenance`, `read_provenance`, and the JSONL index.
- `_utils.py` — internal helpers (slugify, session/branch/synthesis readers, `_inject_prior_context`).
- `deep_think.py` — `plan_deep_think_round`, `plan_round_from_critic_tests`, and the ensemble-critic bundle builder + runner.
- `crosstalk.py` — the adversarial-meeting executor, the picker / arc / deck-plan meeting builders, `rigor_audit`, and the transcript / decisions-log writers.
- `crosstalk_policy.py` — the pure fire-or-skip policy, the goal-risk safety pre-screen (`classify_goal_risk`), and adaptive round sizing (`rounds_for_spread`). Companion: `crosstalk_policy.md`.
- `deck_plan.py` — the content-aware deck-plan generator (task prep, schema, response renderer, mechanical fallback).
- `task_weight.py` — the `TaskSpec` → `Weight` → model-id dispatcher. Companion: `task_weight.md`.
- `synthesis.py` / `parallel.py` / `ensemble.py` / `narrative.py` / `lit.py` / `brainstorm.py` — the single-purpose builders.
- `reasoning_html.py` — renders a `CrosstalkResult` transcript as a browsable HTML view (internal; used by the audit-HTML skill).

## See also

- `../runner/` — the `Meeting` / `Agenda` / `ClaudeCodeRunner` engine these workflows compose, plus the reflection loop and verifiers.
- `../roles/` — the agent role definitions (Analyst, Domain Expert, Methods Critic, Synthesizer, FigureLead, Narrator, rigor_auditor, ...) the meetings instantiate.
- `../research/` — `picker` / `lineage` consume the picker and arc meetings; `summarize` feeds their corpus context.
- `../slides/` — `build_from_plan` consumes the deck-plan dict these builders emit.
- `../provenance/` — the canonical sidecar receipt form `write_with_provenance` also emits.
- `task_weight.md` / `crosstalk_policy.md` (this directory) — the SKILL-bundle docs for the two policy modules.
- `INSPIRATIONS.md` (repo root) — the virtual-lab / AI-Scientist lineage for the meeting, reflection, and ensemble patterns.
