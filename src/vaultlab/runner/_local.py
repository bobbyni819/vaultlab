"""LocalRunner — executes meetings against the Claude API directly.

This is the secondary-priority API surface. The main pipeline lives inside
Claude Code and uses ``ClaudeCodeRunner``; this module is for callers who
want to drive the engine from pure Python without a Claude Code session.

Design choices:

- The default mode is **dry-run**: the runner does NOT call the API. It
  fills each turn with a stub output so the full pipeline (record → save →
  parse → set_rating) can be exercised without LLM cost. Use
  ``LocalRunner(client=...)`` to run for real once you're ready.
- The real runner uses the ``anthropic`` SDK. We never import it directly;
  the caller passes the constructed client. This keeps ``anthropic`` from
  being a hard dependency of vaultlab.
- Same interface as ``ClaudeCodeRunner.plan(...)`` — returns a ``RunPlan`` —
  but also provides ``.execute(plan)`` which fills outputs in-place.

Lifted from ``bobby_ailab._local_runner``. Behaviourally identical.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol

from vaultlab.runner._claude_code import AgentSpec, ClaudeCodeRunner, RunPlan


class _AnthropicClient(Protocol):
    """Structural protocol — the real ``anthropic.Anthropic()`` matches."""

    def __getattr__(self, name: str) -> Any: ...


@dataclass
class LocalRunnerConfig:
    """Tunables for ``LocalRunner.execute()``."""

    model: str = "claude-opus-4-7"
    max_tokens: int = 8192
    temperature: float = 0.2
    dry_run_stub: Callable[[AgentSpec], str] = lambda spec: (
        f"[DRY RUN] {spec.role_name} would run with {len(spec.tools)} tools. "
        f"Prompt length: {len(spec.prompt)} chars."
    )


class LocalRunner(ClaudeCodeRunner):
    """Executes meetings via the Claude API instead of the Agent tool.

    Inherits planning from ``ClaudeCodeRunner``, so plans are identical
    between surfaces — only the execution differs.

    Example (dry run — no API key needed)::

        runner = LocalRunner(kb_path="/tmp", command_name="deep-think")
        plan = runner.plan(meeting, task=agenda)
        runner.execute(plan)  # dry-run: fills stubs
        # now plan.turns[*].output is populated

    Example (real)::

        import anthropic
        client = anthropic.Anthropic(api_key="...")
        runner = LocalRunner(kb_path="/tmp", command_name="x", client=client)
        runner.execute(plan)  # calls the API
    """

    def __init__(
        self,
        kb_path: str,
        command_name: str,
        client: Optional[_AnthropicClient] = None,
        config: Optional[LocalRunnerConfig] = None,
        **runner_kwargs: Any,
    ) -> None:
        super().__init__(
            kb_path=kb_path, command_name=command_name, **runner_kwargs
        )
        self._client = client
        self._config = config or LocalRunnerConfig()

    @property
    def is_dry_run(self) -> bool:
        return self._client is None

    def execute(self, plan: RunPlan) -> RunPlan:
        """Execute each step in the plan and fill turn outputs in place.

        Returns the plan re-rendered with real outputs substituted (the same
        semantic as calling ``plan.inject_prior_outputs(plan.turns)`` after
        each step).
        """
        for step in plan.steps:
            output = self._run_step(step)
            plan.turns[step.step_index].output = output
            plan = plan.inject_prior_outputs(plan.turns)
        return plan

    def _run_step(self, step: AgentSpec) -> str:
        if self._client is None:
            return self._config.dry_run_stub(step)
        response = self._client.messages.create(
            model=self._config.model,
            max_tokens=self._config.max_tokens,
            temperature=self._config.temperature,
            messages=[{"role": "user", "content": step.prompt}],
        )
        # Anthropic SDK returns a Message with .content: list of blocks.
        blocks = getattr(response, "content", [])
        if not blocks:
            return ""
        text_parts: list[str] = []
        for block in blocks:
            text = getattr(block, "text", None)
            if text is None and isinstance(block, dict):
                text = block.get("text")
            if text:
                text_parts.append(text)
        return "\n".join(text_parts)


__all__ = [
    "LocalRunner",
    "LocalRunnerConfig",
]
