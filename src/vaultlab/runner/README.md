# vaultlab.runner

The orchestration heart: turns a multi-role "meeting" into an ordered sequence of agent prompts, and (optionally) executes them — so a slash command can run an internal panel of analyst / critic / synthesizer roles instead of answering in one pass.

Plain-language subsystem write-up: the "Multi-agent meetings (crosstalk)" entry in `G:/My Drive/Knowledge/vaultlab/Wiki/Concepts/vaultlab-subsystems.md`. Architectural placement: `docs/architecture.md` (the `vaultlab.runner` node — fed by the slash command + Claude Code session, feeding `vaultlab.roles`, `vaultlab.workflows`, and `vaultlab.runner.verifiers`).

## What it is

When a vaultlab task is genuine reasoning work — synthesizing across papers, drafting a methods paragraph, reasoning through a results table — vaultlab does not answer in a single shot. It convenes a small internal panel: a role proposes, one or more critics attack it, and a synthesizer reconciles the disagreement into a structured final answer. `vaultlab.runner` is the machinery that *plans* that panel. It takes a `Meeting` (a topic + a list of roles + a mode that says how those roles relate) and renders it into a `RunPlan`: an ordered list of `AgentSpec` steps, each carrying the exact prompt that role should receive, the tools it's allowed, and the output path its answer should land in.

The runner deliberately splits *planning* from *execution*. The prompt-building layer is pure Python and LLM-agnostic — it never makes a model call. Two executors fill that interface: `ClaudeCodeRunner` produces a plan that an in-session slash command follows by spawning the Agent tool once per step (this is the main path, since the active LLM is Claude Code itself); `LocalRunner` inherits the same planner but drives the steps against the Anthropic API directly (defaulting to a no-cost dry-run stub), for callers who want to run the engine from pure Python without a Claude Code session. Between steps, completed outputs are fed back into later prompts so each speaker sees what the earlier speakers actually said — the critique is grounded in the real draft, not a generic checklist.

The meeting structure, agendas, and team layout are adopted as a PATTERN from virtual-lab (Swanson et al., *Nature* 2025; Zou group, Stanford); the refinement loop is from AI-Scientist (Sakana AI); the temperature tuning is from virtual-lab's creative-vs-consistent split. See `INSPIRATIONS.md` for the full lineage.

## Public surface

Exported from the package barrel (`vaultlab.runner.__all__`):

**Runner surface**
- `ClaudeCodeRunner` — planner for in-session slash commands; `.plan(meeting, task)` returns a `RunPlan` the command executes via the Agent tool.
- `LocalRunner` — same planner, but `.execute(plan)` runs each step against the Anthropic API (or, with no client, fills deterministic dry-run stubs).
- `LocalRunnerConfig` — tunables for `LocalRunner.execute()`: model, `max_tokens`, temperature, and the dry-run stub function.
- `RunPlan` — a meeting rendered into an executable sequence of steps, plus `inject_prior_outputs()` to re-render later prompts once earlier turns have real outputs.
- `AgentSpec` — the spec for one agent invocation: role, prompt, allowed tools, output path, step index, and a temperature hint.
- `DEFAULT_TOOLS_BY_ROLE` — the conservative per-role tool allow-lists (a role gets `Bash` only if its work genuinely runs code).
- `render_plan_as_instructions` — render a `RunPlan` as human-readable markdown for debugging / preview.

**Meetings layer** (re-exported from `.meetings`)
- `build_meeting` — build a `Meeting` from a named meeting type (`reasoning`, `deep_think`, `synthesis`, `brainstorm`, `narrate`, `round_table`, `team_meeting`, `critique`, `critiqued_*`, `figure_read`, `visual_deep_think`, …) or an explicit role list; the type both picks the default roles (`roles_for`) and infers the `MeetingMode` (e.g. `reasoning`/`deep_think`/`brainstorm` → adversarial, `team_meeting` → team, any `critiqued_*` → critiqued).
- `compose_turns` — render a meeting into the ordered prompts each role receives, branching on meeting mode.
- `build_merge_meeting` — build a synthesizer meeting that merges the best components of N independent prior runs (with per-component provenance).
- `merge_outputs` — collect completed turns into a `MeetingResult` (validates that turn roles match the meeting's roles).
- `adversarial_inject` — rewrite adversarial prompts so each later turn sees the earlier turns' real outputs.
- `save_meeting` — write a meeting's full discussion as one consolidated markdown transcript.
- `wrap_context` / `wrap_contexts` — wrap context blocks in virtual-lab-style `[begin <label> N] … [end <label> N]` delimiters so an agent doesn't conflate multiple prior summaries.

**Data models** (re-exported from `.models`)
- `Meeting` — a multi-role session config: topic, mode, roles, session context, round, prior summary, optional agenda.
- `MeetingMode` — how roles relate to each other's outputs (`ROUND_TABLE`, `ADVERSARIAL`, `SYNTHESIS`, `INDIVIDUAL`, `TEAM`, `CRITIQUED`).
- `MeetingTurn` — one role's turn: its prompt, and (once executed) its output + output path.
- `MeetingResult` — the outcome of a meeting run: the topic, mode, round, the completed turns, and an optional synthesis.
- `Role` — the canonical agent persona: id, name, system prompt, description, focus areas, evaluation criteria, communication style, output format, project `mode`, and a per-role `tools_allowed` hint. `Role.prompt_for(session_context, task, prior_outputs)` renders the per-task prompt — system prompt, then a `CONTEXT:` block, an optional `PRIOR AGENT OUTPUTS:` block, the rendered agenda (or a bare `TASK:` line), and an optional `OUTPUT FORMAT:` block. (Loaded from `vaultlab.roles`; defined here as the shared shape — there is exactly one `Role` class in vaultlab.)
- `Agenda` — the shared frame injected into every prompt: statement, questions that must be answered, rules that must be followed, plus the investigation mode. `Agenda.from_task(topic, task)` lifts a free-form task string into a minimal agenda; `Agenda.render()` produces the agenda block (mode header + statement + numbered questions + numbered rules) that every role sees.
- `InvestigationMode` — `EXPLORATORY` (no committed direction; survey broadly, propose candidate directions, do not pretend conviction) vs `DIRECTED` (a direction exists; enrich, harden, and defend it rather than start over). Selected per-agenda; it changes the mode-header instruction prepended to every prompt.
- `Mode` — project reasoning mode (`DATA_ANALYSIS` vs `LITERATURE_REVIEW`) — selects which role variant runs.

**Internal verifier**
- `verify_numeric` — deterministically scan generated text (no LLM) for reported statistics — `p=…` values (including scientific notation like `p=5.88e-09`), `n=…` sample sizes (per-group `n=6/6` forms included), and `mean … ± … range [lo, hi]` descriptives — and flag internally inconsistent or implausible values: a p-value outside `[0, 1]`, a non-positive `n`, an inverted range (`lo > hi`), or a mean falling outside its own stated range. Returns one human-readable finding per problem (with the character offset), or an empty list when nothing looks wrong.

Several public helpers live in sibling modules but are **not** re-exported from the package barrel (import them from their module directly):

- `kb_context.compose_preamble` / `prepend_preamble` / `KbContextBundle` / `KbStateUnreadable` — assemble the project's known KB state into a token-budgeted preamble to prepend to a spawned sub-agent's system prompt, so no sub-agent starts from zero (CLAUDE.md commitment #7). The preamble bundles: the project's `START_HERE.md` daily brief, `decisions-log.md` entries from the last 30 days, the top-N Tier-A paper summaries ranked by keyword overlap with the project topic, and the most-recent `Output/*.md` files — each given a slice of a `max_tokens` budget (default 4000), with hedged `[<section> truncated — N tokens dropped]` markers when a section is cut. It resolves the project state the same way onboarding writes it (`<kb>/Wiki/Projects/<slug>/`, with a legacy flat `<kb>/<slug>/` fallback) and **raises `KbStateUnreadable`** when `START_HERE.md` is missing/unreadable, so callers refuse to spawn context-less sub-agents rather than silently guess. `prepend_preamble()` is the one-line, opt-in, safe-by-default hook orchestrators actually call (falsy slug or unreadable state → returns the original `session_context` unchanged + logs a warning, never kills the meeting); `compose_preamble(..., return_bundle=True)` returns the structured `KbContextBundle` for inspection (this is what `/context-check` prints). Has its own `kb_context.md`.
- `reflection.run_with_reflection` / `ReflectionResult` / `contains_done_signal` / `DONE_SIGNAL_DEFAULT` / `REFLECTION_PROMPT_TEMPLATE` — run an agent, then refine it up to N times (`max_reflections`, default 3), terminating early the moment the agent's draft contains an "I am done" signal (several phrasings recognised, e.g. *"I'm done"*, *"nothing to add"* — even on the very first draft). `ReflectionResult` keeps every draft, the iterations used, and whether it stopped early; `.final` returns the last non-empty draft. An optional `non_regression_guard` (default off, AI-co-scientist "additive evolution") refuses to adopt a refinement that drops a cited DOI, adds an unhedged claim, or adds a numeric inconsistency — keeping the prior best and recording the rejection reason in `ReflectionResult.rejected_refinements` (it reuses `enforce_hedge` + `verify_numeric` rather than an LLM judge).
- `_temperatures.temperature_for` (+ the public constants `CONSISTENT_TEMPERATURE` 0.2, `BALANCED_TEMPERATURE` 0.5, `CREATIVE_TEMPERATURE` 0.8, `ENSEMBLE_TEMPERATURE` 0.75 and the `TEMPERATURE_BY_MEETING_MODE` / `TEMPERATURE_BY_ROLE` tables) — pick the temperature for a role in a given meeting mode. Priority: `ensemble=True` wins (diverse critics for aggregation), then a per-role override (synthesizers/leads/narrators run cold, the figure lead runs hot for ideation), then the meeting-mode default (round-table creative, synthesis consistent, adversarial/team/critiqued balanced), then a consistent fallback. The planner calls it when building each `AgentSpec`'s `temperature` hint.

## How it fits

**Reads from:** `vaultlab.roles` — the role catalog (markdown + YAML on disk) loaded into the canonical `Role` shape; the caller's `session_context` string (typically assembled from the KB by `vaultlab.context` and, for spawned sub-agents, prefixed with the `kb_context` preamble); a `task` or structured `Agenda`. `kb_context` additionally reads the project's `START_HERE.md`, `decisions-log.md`, `Wiki/Summaries/` Tier-A cards, and `Output/*.md` directly off disk.

**Writes to:** nothing of its own directly — the planner returns a `RunPlan` in-process and the executing slash command is responsible for writing each turn's output to `step.output_path` under `<kb>/Output/`. `save_meeting` and `LocalRunner.execute` are the exceptions that touch disk / the API. The `RunPlan.session_updates` list tells the command what post-run bookkeeping to do (record the meeting, set ratings, save the team summary).

**Where it sits:** the orchestration layer between a slash command and the roles/workflows it drives. `vaultlab.workflows` (crosstalk, deep-think) build meetings and consume run plans; the slash commands in `.claude/commands/` are the executors. `verify_numeric` is wired into the analysis interpretation pass as one of the internal gates. This package was lifted largely intact from the predecessor `bobby_ailab` runner and kept behaviourally identical.

## What it does NOT do

- It does **not** call an LLM in the planning layer — `ClaudeCodeRunner`/`compose_turns`/`meetings` only *build* prompts. Active model calls happen via the Agent tool (in-session) or `LocalRunner` (direct API).
- It does **not** execute steps, write outputs, or feed turns back automatically for `ClaudeCodeRunner` — the executing slash command does that and must call `inject_prior_outputs()` between steps.
- It does **not** define the role personas — those live in `vaultlab.roles` (per CLAUDE.md META PRINCIPLE #1, the prompt text is markdown on disk, not Python strings here).
- It does **not** enforce hedged voice or check citations — those verifiers live in `vaultlab.roles._guardrails` (`enforce_hedge`) and `vaultlab.citations`; only the numeric verifier lives here.
- It does **not** run unboundedly — meeting rounds and reflection loops are capped (e.g. crosstalk's five-round hard cap is enforced upstream in `vaultlab.workflows`, not invented here).

## Files

- `__init__.py` — slim barrel; re-exports the runner surface, meetings layer, data models, and `verify_numeric`.
- `models.py` — the public data classes (`Meeting`, `MeetingMode`, `Agenda`, `Role`, `MeetingTurn`, `MeetingResult`, `Mode`, `InvestigationMode`) and `Role.prompt_for` / `Agenda.render`.
- `meetings.py` — `compose_turns` (mode-by-mode prompt construction), `build_meeting`, `build_merge_meeting`, `merge_outputs`, `adversarial_inject`, `wrap_context(s)`, `save_meeting`; the lazy `ROLE_TEMPLATES` proxy into `vaultlab.roles`.
- `_claude_code.py` — `ClaudeCodeRunner`, `RunPlan`, `AgentSpec`, `DEFAULT_TOOLS_BY_ROLE`, `render_plan_as_instructions`.
- `_local.py` — `LocalRunner` + `LocalRunnerConfig` (the direct-API / dry-run executor).
- `_temperatures.py` — `temperature_for`, the four named temperature constants, and the `TEMPERATURE_BY_MEETING_MODE` / `TEMPERATURE_BY_ROLE` tables (virtual-lab's creative-vs-consistent split).
- `verifiers.py` — `verify_numeric`, the deterministic numeric-consistency checker (p-value / sample-size / mean-range scanning).
- `reflection.py` — `run_with_reflection` + `ReflectionResult` + `contains_done_signal` + `DONE_SIGNAL_DEFAULT` + `REFLECTION_PROMPT_TEMPLATE` (AI-Scientist refine-until-done loop, with an optional AI-co-scientist non-regression guard).
- `kb_context.py` + `kb_context.md` — `compose_preamble` / `prepend_preamble` / `KbContextBundle` / `KbStateUnreadable`, the context-preservation preamble for spawned sub-agents.

## See also

- `src/vaultlab/roles/` — the role catalog this runner renders (markdown prompts + YAML); `_guardrails.enforce_hedge`.
- `src/vaultlab/workflows/` — crosstalk + deep-think orchestrators that build meetings and consume run plans (and enforce the round caps).
- `src/vaultlab/runner/kb_context.md` — the dedicated write-up for the sub-agent context preamble.
- `src/vaultlab/citations/README.md` — the citation verifier that pairs with `verify_numeric` as an output gate.
- `docs/architecture.md` — the `vaultlab.runner` architectural sketch (the result-oriented bounded-loop contract).
- `INSPIRATIONS.md` — the virtual-lab / AI-Scientist lineage entries for the meeting, reflection, and temperature patterns.
- Plain-language: the "Multi-agent meetings (crosstalk)" section of `vaultlab-subsystems.md` (KB).
