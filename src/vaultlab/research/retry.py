"""Retry-with-feedback wrapper for LLM callbacks.

Pattern lifted from AI-Scientist's ``perform_experiments.py:52-60``: when
an LLM-driven step fails (raises, returns malformed output, returns
empty), capture the error context (stderr / exception message /
schema-violation reason), truncate it to a safe length, and feed it
back into a retry call so the LLM can self-correct. Bounded retries
avoid runaway loops.

Vaultlab's spin: surface this as a generic wrapper any callback can opt
into. Today the most relevant callsite is
:func:`vaultlab.research.claim_verification.verify_paragraph_claims` —
when a verifier raises, the current code silently logs and returns
``unverifiable`` for every claim, which means the caller gets no
useful feedback about what went wrong. Wrapping the callback with
``retry_with_feedback`` gives it one more chance with the error context
visible.

Design
------

* Generic over the callback shape — works for any
  ``Callable[[T], dict]`` where T is a task with a ``prompt`` field
  the wrapper can append feedback to.
* Bounded retries (default 1; AI-Scientist also defaults to 1
  retry-with-feedback per failure).
* Feedback is truncated to ``max_feedback_chars`` (default 1500,
  matching AI-Scientist) — long stack traces don't blow the LLM's
  context budget.
* Distinguishes three failure modes:
  * **EXCEPTION** — callback raised
  * **EMPTY** — callback returned None or empty dict
  * **VALIDATION** — caller-supplied ``validate`` returned a
    non-empty error string
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

logger = logging.getLogger(__name__)


__all__ = [
    "RetryAttempt",
    "RetryResult",
    "retry_with_feedback",
    "truncate_feedback",
]


T = TypeVar("T")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


DEFAULT_MAX_FEEDBACK_CHARS = 1500


def truncate_feedback(text: str, *, max_chars: int = DEFAULT_MAX_FEEDBACK_CHARS) -> str:
    """Truncate ``text`` to the last ``max_chars`` characters.

    The TAIL is kept (not the head) — error messages typically have the
    relevant context near the end (the actual exception, the
    last-rendered output the LLM produced before failing). Heads tend
    to be boilerplate.
    """
    if len(text) <= max_chars:
        return text
    return "[...truncated...]\n" + text[-max_chars:]


# ---------------------------------------------------------------------------
# Result data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetryAttempt:
    """One retry attempt's outcome.

    Attributes:
        attempt: 1-indexed attempt number.
        succeeded: True if the callback returned a non-empty dict that
            passed validation.
        failure_mode: ``""`` on success; otherwise one of
            ``"exception"`` / ``"empty"`` / ``"validation"``.
        error_text: Truncated feedback that would be (or was) fed back
            on the next attempt. Empty on success.
    """

    attempt: int
    succeeded: bool
    failure_mode: str = ""
    error_text: str = ""


@dataclass
class RetryResult(Generic[T]):
    """Outcome of a :func:`retry_with_feedback` call.

    Attributes:
        response: The final callback response, or ``None`` if every
            attempt failed.
        attempts: List of :class:`RetryAttempt` records, oldest first.
        succeeded: Convenience flag — ``True`` if the last attempt
            succeeded.
    """

    response: dict[str, Any] | None = None
    attempts: list[RetryAttempt] = None  # type: ignore[assignment]
    succeeded: bool = False

    def __post_init__(self) -> None:
        if self.attempts is None:
            self.attempts = []


# ---------------------------------------------------------------------------
# Main wrapper
# ---------------------------------------------------------------------------


def retry_with_feedback(
    callback: Callable[[T], Any],
    task: T,
    *,
    max_retries: int = 1,
    validate: Callable[[Any], str] | None = None,
    apply_feedback: Callable[[T, str], T] | None = None,
    max_feedback_chars: int = DEFAULT_MAX_FEEDBACK_CHARS,
) -> RetryResult:
    """Call ``callback(task)`` with bounded retry on failure.

    On each failure, the wrapper truncates the error context to
    ``max_feedback_chars`` and (if ``apply_feedback`` is supplied) builds
    a new task with the error appended to the task's prompt. The next
    attempt sees the prior error and can self-correct.

    Args:
        callback: The function to call. Receives a task; returns a
            dict (typically JSON-shaped). Empty dicts and None count
            as failures.
        task: The initial task to pass to the callback. Must be a
            mutable dataclass-like object with a ``prompt`` attribute
            if you want feedback applied automatically; otherwise pass
            ``apply_feedback`` to control how feedback flows in.
        max_retries: Maximum number of RETRY attempts (the initial call
            doesn't count). Default 1, matching AI-Scientist's pattern.
            With ``max_retries=0`` you get no retries — equivalent to
            calling the callback directly with try/except.
        validate: Optional validator. Receives the callback response;
            returns ``""`` for valid responses or a non-empty error
            string. When non-empty, the response is treated as a
            failure and fed back into the next attempt.
        apply_feedback: Optional builder for the next-attempt task.
            Receives ``(prior_task, feedback_text)`` and returns a NEW
            task with the feedback woven in. When ``None``, the wrapper
            tries to set ``task.prompt = task.prompt + "\\n\\n" + feedback``
            via dataclass-replace and falls back to passing the
            original task unchanged if that fails.
        max_feedback_chars: Cap on feedback text length per attempt.

    Returns:
        A populated :class:`RetryResult` with the final response (if
        any) and the list of attempts.
    """
    if max_retries < 0:
        max_retries = 0

    attempts: list[RetryAttempt] = []
    current_task = task
    last_response: dict[str, Any] | None = None

    total = 1 + int(max_retries)
    for i in range(1, total + 1):
        try:
            raw = callback(current_task)
        except Exception as exc:  # noqa: BLE001 — we want to capture any failure
            err = truncate_feedback(
                f"PRIOR ATTEMPT RAISED: {type(exc).__name__}: {exc}",
                max_chars=max_feedback_chars,
            )
            attempts.append(
                RetryAttempt(
                    attempt=i,
                    succeeded=False,
                    failure_mode="exception",
                    error_text=err,
                )
            )
            if i == total:
                break
            current_task = _next_task(current_task, err, apply_feedback)
            continue

        # Treat None / empty dict as failure (the callback "returned nothing useful")
        if not isinstance(raw, dict) or not raw:
            err = truncate_feedback(
                "PRIOR ATTEMPT RETURNED EMPTY OR NON-DICT RESPONSE. "
                "The expected shape is a JSON object matching the "
                "task's response_schema. Return the structured object.",
                max_chars=max_feedback_chars,
            )
            attempts.append(
                RetryAttempt(
                    attempt=i,
                    succeeded=False,
                    failure_mode="empty",
                    error_text=err,
                )
            )
            if i == total:
                break
            current_task = _next_task(current_task, err, apply_feedback)
            continue

        # Optional caller-supplied validation
        if validate is not None:
            verdict = validate(raw) or ""
            if verdict:
                err = truncate_feedback(
                    f"PRIOR ATTEMPT FAILED VALIDATION: {verdict}",
                    max_chars=max_feedback_chars,
                )
                attempts.append(
                    RetryAttempt(
                        attempt=i,
                        succeeded=False,
                        failure_mode="validation",
                        error_text=err,
                    )
                )
                if i == total:
                    break
                current_task = _next_task(current_task, err, apply_feedback)
                continue

        # Success
        attempts.append(RetryAttempt(attempt=i, succeeded=True))
        last_response = raw
        return RetryResult(
            response=last_response, attempts=attempts, succeeded=True
        )

    return RetryResult(response=None, attempts=attempts, succeeded=False)


# ---------------------------------------------------------------------------
# Internal — task feedback application
# ---------------------------------------------------------------------------


def _next_task(
    task: Any, feedback: str, apply_feedback: Callable[[Any, str], Any] | None
) -> Any:
    """Return a new task with the feedback appended.

    Strategy:

    1. If ``apply_feedback`` is supplied, defer to it.
    2. Else try ``dataclasses.replace(task, prompt=task.prompt + ...)``
       — works for the standard frozen-dataclass tasks vaultlab uses.
    3. Else return ``task`` unchanged (the next call retries with the
       same prompt; the LLM gets a second chance but no error context).
    """
    if apply_feedback is not None:
        try:
            return apply_feedback(task, feedback)
        except Exception:  # pragma: no cover — defensive
            logger.warning(
                "apply_feedback raised; reusing original task on retry"
            )
            return task

    # Try dataclass-replace if the task has a prompt field
    try:
        from dataclasses import is_dataclass, replace

        if is_dataclass(task) and hasattr(task, "prompt"):
            old_prompt = getattr(task, "prompt") or ""
            new_prompt = (
                old_prompt
                + "\n\n---\n\nRETRY FEEDBACK FROM PRIOR ATTEMPT:\n"
                + feedback
                + "\n\nPlease address the issue above and produce the "
                + "structured response again."
            )
            return replace(task, prompt=new_prompt)
    except Exception:  # pragma: no cover — defensive
        pass
    return task
