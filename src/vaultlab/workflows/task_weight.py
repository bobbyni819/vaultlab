"""SPEC-F task-weight dispatch.

Route LLM tasks to model tiers by task weight:

* ``light``  — fast/cheap model (e.g., Haiku, GPT-4o-mini)
* ``medium`` — balanced model (e.g., Sonnet)
* ``heavy``  — premium model (e.g., Opus, GPT-4-turbo)

The default mapping uses Claude model IDs declared in the user's global
CLAUDE.md (``claude-haiku-4-5`` / ``claude-sonnet-4-6`` / ``claude-opus-4-7``)
and is overridable via ``~/.config/vaultlab/dispatch.json`` (or the
``VAULTLAB_DISPATCH_CONFIG`` environment variable, for tests and CI).

Decision rules (see :func:`classify`):

* format conversion / simple extraction → ``light``
* single-paper summarization → ``medium``
* cross-paper synthesis / manuscript polish / response letters → ``heavy``
* batch work over more than five inputs → ``heavy``
* explicit ``requires_synthesis=True`` → ``heavy``

Typical usage::

    from vaultlab.workflows.task_weight import TaskSpec, model_for_task

    spec = TaskSpec(kind="summarize", n_inputs=1)
    model_id = model_for_task(spec)  # "claude-sonnet-4-6" by default

The companion ``task_weight.md`` SKILL document describes the task kinds,
weights, and override mechanism for human readers.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Weight = Literal["light", "medium", "heavy"]

# Public weight literal values, exposed so callers can introspect the
# allowed set without importing ``typing.get_args`` themselves.
WEIGHT_VALUES: tuple[Weight, ...] = ("light", "medium", "heavy")


@dataclass
class TaskSpec:
    """Describes a unit of LLM work for the dispatcher to classify.

    Attributes
    ----------
    kind
        Short task identifier — e.g. ``"polish"``, ``"summarize"``,
        ``"extract"``, ``"synthesize"``, ``"convert"``. Unknown kinds are
        treated as medium-weight by default.
    n_inputs
        How many documents / papers / figures feed this task. Used by the
        "large batch upgrades to heavy" rule.
    output_kind
        ``"text"``, ``"json"``, or ``"code"``. Informational — does not
        currently affect classification but is preserved for future use
        and for provenance logging.
    requires_synthesis
        When True, the task always classifies as ``heavy`` regardless of
        other fields. Use this when the caller knows cross-evidence
        reasoning is required (e.g. literature arc).
    """

    kind: str
    n_inputs: int = 1
    output_kind: str = "text"
    requires_synthesis: bool = False


WEIGHT_TO_DEFAULT_MODEL: dict[Weight, str] = {
    "light": "claude-haiku-4-5",
    "medium": "claude-sonnet-4-6",
    "heavy": "claude-opus-4-7",
}


# Task kinds that always classify as ``heavy``. These are the ones that
# benefit from the most capable model — multi-paper synthesis, manuscript
# polish, deep-think reasoning, response letters, etc.
_HEAVY_KINDS: frozenset[str] = frozenset(
    {
        "polish",
        "respond",
        "manuscript_draft",
        "deep_think",
        "synthesize",
        "synthesis",
    }
)

# Task kinds that always classify as ``light``. These are mechanical /
# extraction / formatting tasks where a cheap fast model is sufficient.
_LIGHT_KINDS: frozenset[str] = frozenset(
    {
        "extract",
        "convert",
        "format",
        "render",
    }
)

# Task kinds that classify as ``medium`` when there is exactly one input.
# A batch (n_inputs > 5) of these still upgrades to ``heavy``.
_MEDIUM_KINDS: frozenset[str] = frozenset(
    {
        "summarize",
        "single_paper_read",
        "abstract_only",
    }
)


def classify(task: TaskSpec) -> Weight:
    """Classify a task into one of ``light``/``medium``/``heavy``.

    Decision order:

    1. ``requires_synthesis=True`` → ``heavy``
    2. ``kind`` in :data:`_HEAVY_KINDS` → ``heavy``
    3. ``kind`` in :data:`_LIGHT_KINDS` → ``light``
    4. ``kind`` in :data:`_MEDIUM_KINDS` with ``n_inputs == 1`` → ``medium``
    5. ``n_inputs > 5`` → ``heavy`` (batch work)
    6. Otherwise → ``medium`` (safe default)
    """

    if task.requires_synthesis:
        return "heavy"
    if task.kind in _HEAVY_KINDS:
        return "heavy"
    if task.kind in _LIGHT_KINDS:
        return "light"
    if task.n_inputs > 5:
        return "heavy"
    if task.kind in _MEDIUM_KINDS and task.n_inputs == 1:
        return "medium"
    return "medium"


def _resolve_config_path(config_path: Path | None) -> Path:
    if config_path is not None:
        return config_path
    env_override = os.environ.get("VAULTLAB_DISPATCH_CONFIG", "")
    if env_override:
        return Path(env_override)
    return Path.home() / ".config" / "vaultlab" / "dispatch.json"


def model_for_weight(weight: Weight, config_path: Path | None = None) -> str:
    """Resolve the ``model_id`` for a :data:`Weight`.

    Honors a user override file at ``~/.config/vaultlab/dispatch.json``
    (or the path supplied via ``config_path`` / the
    ``VAULTLAB_DISPATCH_CONFIG`` environment variable). The override file
    is a JSON object mapping ``"light"`` / ``"medium"`` / ``"heavy"`` to
    model identifier strings; unknown keys are ignored and missing keys
    fall back to the defaults in :data:`WEIGHT_TO_DEFAULT_MODEL`.

    Malformed JSON or unreadable files fall back to defaults silently —
    the dispatcher is best-effort and must never crash the caller's
    pipeline.
    """

    resolved = _resolve_config_path(config_path)
    mapping: dict[Weight, str] = dict(WEIGHT_TO_DEFAULT_MODEL)
    if resolved.exists():
        try:
            user_map = json.loads(resolved.read_text(encoding="utf-8"))
            if isinstance(user_map, dict):
                for key, value in user_map.items():
                    if key in mapping and isinstance(value, str) and value:
                        mapping[key] = value  # type: ignore[index]
        except (json.JSONDecodeError, OSError):
            pass  # fall back to defaults
    return mapping[weight]


def model_for_task(task: TaskSpec, config_path: Path | None = None) -> str:
    """Sugar: classify ``task`` and resolve the configured model id."""

    return model_for_weight(classify(task), config_path)


__all__ = [
    "TaskSpec",
    "WEIGHT_TO_DEFAULT_MODEL",
    "WEIGHT_VALUES",
    "Weight",
    "classify",
    "model_for_task",
    "model_for_weight",
]
