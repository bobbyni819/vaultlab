# `vaultlab.runner.kb_context`

KB-context preamble for spawned sub-agents. Closes CLAUDE.md commitment #7 — the context-preservation invariant — by providing a single canonical helper that any orchestrator calls before spawning sub-agents to ensure they all start with the project's known state loaded.

## Public surface

```python
from vaultlab.runner.kb_context import (
    compose_preamble,
    KbContextBundle,
    KbStateUnreadable,
)

preamble: str = compose_preamble(
    project_slug="metabolism",
    role="methods_critic",            # optional — appears in preamble header
    max_tokens=4000,                  # default budget
)
```

The returned string is meant to be **prepended to the sub-agent's system prompt**. Any orchestrator that spawns sub-agents (`plan_deep_think_round`, `plan_ensemble_critic`, the new `/find-analogs`, `/next-analysis`, `/debug`, `/code-review`, `/explore-data` commands, etc.) must call `compose_preamble()` first and stitch the result into every sub-agent's system prompt.

## What's in the preamble

1. **Header** — project slug + spawned role (if given)
2. **`START_HERE.md`** — project daily brief, newest day on top
3. **`decisions-log.md`** — design + scope decisions from the last 30 days
4. **Top-N Tier-A summaries** — keyword-relevance-ranked against project topic; default 5
5. **Most-recent `Output/*.md`** — last 3 by mtime; first 300 chars each
6. **Reminder footer** — explicit "build on prior work, don't redo it" instruction

Each section gets a slice of the token budget (`max_tokens // 3` for START_HERE, etc.). Truncation is **hedged**: an explicit `[<section> truncated — N tokens dropped]` marker is left in place so the sub-agent knows it isn't seeing everything.

## Refusal-to-proceed mechanism

`compose_preamble()` raises `KbStateUnreadable` when:

- The project directory doesn't exist
- `<project>/START_HERE.md` is missing or unreadable

Callers MUST refuse to spawn sub-agents in this case rather than silently fall through to no-context invocation. This is the architectural guarantee that prevents "the agent suddenly forgot all about the previous work" — Bobby's stated worst case.

Anti-pattern: catching the exception and proceeding without context. If this happens, file a bug.

## Token budget

Default 4000 tokens (≈16000 chars). Approximate via 4-chars-per-token heuristic — no tokenizer dependency. Budget split roughly:

- START_HERE: `max_tokens // 3` (~1300)
- decisions-log: `max_tokens // 4` (~1000)
- Tier-A summaries: `max_tokens // 4` (~1000), divided across N summaries
- Recent outputs: remainder (~700), divided across N outputs

Larger budgets (e.g., 8000-12000 tokens) are reasonable for the most-deep tasks (full manuscript drafts, longer deep-think rounds). Pass via `max_tokens=`.

## Inspection — `return_bundle=True`

When you need to inspect what was loaded (e.g., for the `/context-check` slash command), pass `return_bundle=True` to get a `KbContextBundle` dataclass with structured fields. The string preamble is what gets prepended to system prompts; the bundle is for diagnostics.

## Lineage

| Pattern | Source |
|---|---|
| KB-prepended-as-system-prompt for sub-agents | virtual-lab "team_lead distributes shared context to all role-agents" (Swanson Nature 2025; Zou group, Stanford) |
| Refuse-to-proceed when context can't be loaded | AI-Scientist verifier-driven termination + PaperQA2 refuse-to-ship-without-evidence |
| Token-budget truncation with hedged voice | LiteLLM context-window-fitting patterns |

## When to call

Every artifact-producing orchestrator that spawns sub-agents calls this. The pattern:

```python
from vaultlab.runner.kb_context import compose_preamble, KbStateUnreadable

def my_orchestrator(project_slug: str, ...):
    try:
        preamble = compose_preamble(project_slug, role="analyst")
    except KbStateUnreadable as e:
        # Refuse to spawn — surface error to user
        raise RuntimeError(f"Cannot spawn analyst: {e}") from e

    analyst_system_prompt = preamble + "\n\n" + role_specific_instructions
    # ... spawn sub-agent with this system prompt
```

## When NOT to call

- For pure-capability primitives that don't spawn sub-agents (e.g., direct calls to `vaultlab.figures.recipes.marker_dot_plot.render`) — those don't need a preamble; they consume their explicit kwargs only.
- For one-shot LLM calls where the user has already provided full context in their message and there's no project to inherit from.

## Tests

Recommended test coverage:

- Happy path: project with START_HERE + decisions-log + Tier-A summaries + outputs → preamble has all sections
- Missing START_HERE → `KbStateUnreadable`
- Missing decisions-log → preamble omits the section without raising
- Token-budget truncation triggers correct hedged-voice marker
- `return_bundle=True` returns a fully-populated `KbContextBundle`
