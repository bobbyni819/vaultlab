"""Tests for the retry-with-feedback helper (#111).

Pattern lifted from AI-Scientist's perform_experiments.py:52-60. The
critical contract: when the callback fails, the wrapper composes a
new task with truncated error feedback and retries — bounded — so the
LLM gets one (or more) chances to self-correct.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from vaultlab.research.retry import (
    RetryAttempt,
    RetryResult,
    retry_with_feedback,
    truncate_feedback,
)


# ---------------------------------------------------------------------------
# truncate_feedback
# ---------------------------------------------------------------------------


def test_truncate_short_text_unchanged():
    assert truncate_feedback("hello") == "hello"


def test_truncate_keeps_tail_not_head():
    """The tail of the error is more relevant than the head — keep last N chars."""
    text = "A" * 1000 + "RELEVANT_ENDING"
    out = truncate_feedback(text, max_chars=20)
    # Truncation marker prepended; relevant tail kept
    assert out.startswith("[...truncated...]")
    assert "RELEVANT_ENDING" in out
    # Head is dropped
    assert "A" * 1000 not in out


def test_truncate_default_chars():
    text = "x" * 5000
    out = truncate_feedback(text)
    # Default is 1500 chars + truncation prefix
    assert len(out) < len(text)
    assert "[...truncated...]" in out


# ---------------------------------------------------------------------------
# Synthetic task with a prompt field for the dataclass-replace path
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FakeTask:
    prompt: str
    other_data: str = ""


# ---------------------------------------------------------------------------
# Successful first attempt
# ---------------------------------------------------------------------------


def test_succeeds_on_first_attempt_when_callback_returns_valid_dict():
    def cb(task):
        return {"ok": True}

    result = retry_with_feedback(cb, _FakeTask(prompt="initial"))
    assert result.succeeded
    assert result.response == {"ok": True}
    assert len(result.attempts) == 1
    assert result.attempts[0].succeeded


# ---------------------------------------------------------------------------
# Exception → retry with feedback
# ---------------------------------------------------------------------------


def test_exception_triggers_retry_with_feedback():
    """Callback raises on attempt 1, succeeds on attempt 2 with the feedback."""
    seen_prompts: list[str] = []

    def cb(task: _FakeTask):
        seen_prompts.append(task.prompt)
        if len(seen_prompts) == 1:
            raise RuntimeError("connection died")
        return {"recovered": True}

    result = retry_with_feedback(
        cb, _FakeTask(prompt="initial"), max_retries=1
    )
    assert result.succeeded
    assert len(seen_prompts) == 2
    # Second attempt's prompt includes the error context
    assert "RETRY FEEDBACK" in seen_prompts[1]
    assert "connection died" in seen_prompts[1]
    # Original prompt body still in there
    assert "initial" in seen_prompts[1]
    # Two attempts recorded; first failed, second succeeded
    assert len(result.attempts) == 2
    assert result.attempts[0].failure_mode == "exception"
    assert result.attempts[1].succeeded


def test_exhausts_retries_returns_unsuccessful_result():
    def cb(task):
        raise RuntimeError("persistent failure")

    result = retry_with_feedback(
        cb, _FakeTask(prompt="t"), max_retries=2
    )
    assert not result.succeeded
    assert result.response is None
    # 1 initial + 2 retries = 3 attempts, all failed
    assert len(result.attempts) == 3
    assert all(a.failure_mode == "exception" for a in result.attempts)


# ---------------------------------------------------------------------------
# Empty / None response → retry with feedback
# ---------------------------------------------------------------------------


def test_none_response_treated_as_failure():
    seen: list[str] = []

    def cb(task):
        seen.append(task.prompt)
        return None if len(seen) == 1 else {"ok": True}

    result = retry_with_feedback(
        cb, _FakeTask(prompt="t"), max_retries=1
    )
    assert result.succeeded
    assert result.attempts[0].failure_mode == "empty"


def test_empty_dict_treated_as_failure():
    seen: list[str] = []

    def cb(task):
        seen.append(task.prompt)
        return {} if len(seen) == 1 else {"ok": True}

    result = retry_with_feedback(
        cb, _FakeTask(prompt="t"), max_retries=1
    )
    assert result.succeeded
    assert result.attempts[0].failure_mode == "empty"


def test_non_dict_response_treated_as_failure():
    """Lists, strings, ints — anything not a dict is a failure."""

    def cb(task):
        return ["not", "a", "dict"]

    result = retry_with_feedback(
        cb, _FakeTask(prompt="t"), max_retries=0
    )
    assert not result.succeeded
    assert result.attempts[0].failure_mode == "empty"


# ---------------------------------------------------------------------------
# Validation feedback
# ---------------------------------------------------------------------------


def test_validator_failure_triggers_retry():
    seen: list[str] = []

    def cb(task: _FakeTask):
        seen.append(task.prompt)
        # Both attempts return technically-valid dicts; validator decides
        return {"value": 1 if len(seen) == 1 else 100}

    def validator(response):
        # First attempt: value too small; second: ok
        if response["value"] < 50:
            return "value must be >= 50"
        return ""

    result = retry_with_feedback(
        cb,
        _FakeTask(prompt="t"),
        max_retries=1,
        validate=validator,
    )
    assert result.succeeded
    assert result.attempts[0].failure_mode == "validation"
    # Feedback included the validator's error message
    assert "value must be >= 50" in seen[1]


def test_validator_returning_empty_string_is_success():
    """Validator returns "" for valid responses → first attempt succeeds."""

    def cb(task):
        return {"value": 42}

    def validator(response):
        return ""  # all good

    result = retry_with_feedback(
        cb, _FakeTask(prompt="t"), validate=validator
    )
    assert result.succeeded
    assert len(result.attempts) == 1


# ---------------------------------------------------------------------------
# Custom apply_feedback
# ---------------------------------------------------------------------------


def test_custom_apply_feedback_takes_precedence_over_default():
    """When ``apply_feedback`` is given, it controls how feedback flows in."""
    seen_tasks: list[_FakeTask] = []
    custom_calls: list[tuple] = []

    def cb(task: _FakeTask):
        seen_tasks.append(task)
        if len(seen_tasks) == 1:
            return {}
        return {"ok": True}

    def custom_apply(task, feedback):
        custom_calls.append((task, feedback))
        # Return a brand-new task that signals we got the feedback
        return _FakeTask(prompt="REWRITTEN", other_data=feedback[:50])

    result = retry_with_feedback(
        cb,
        _FakeTask(prompt="initial"),
        max_retries=1,
        apply_feedback=custom_apply,
    )
    assert result.succeeded
    # Custom apply was called once
    assert len(custom_calls) == 1
    # Second attempt saw the rewritten task
    assert seen_tasks[1].prompt == "REWRITTEN"


# ---------------------------------------------------------------------------
# max_retries bounds
# ---------------------------------------------------------------------------


def test_max_retries_zero_means_no_retry():
    """max_retries=0 → at most 1 attempt total (the initial call)."""
    call_count = [0]

    def cb(task):
        call_count[0] += 1
        return {}  # always fails

    result = retry_with_feedback(
        cb, _FakeTask(prompt="t"), max_retries=0
    )
    assert call_count[0] == 1
    assert not result.succeeded
    assert len(result.attempts) == 1


def test_negative_max_retries_treated_as_zero():
    call_count = [0]

    def cb(task):
        call_count[0] += 1
        return {}

    result = retry_with_feedback(
        cb, _FakeTask(prompt="t"), max_retries=-5
    )
    assert call_count[0] == 1


# ---------------------------------------------------------------------------
# Feedback truncation
# ---------------------------------------------------------------------------


def test_long_exception_message_truncated_to_max_feedback_chars():
    """An exception with a 5000-char message gets truncated to max_feedback_chars."""

    def cb(task):
        raise RuntimeError("X" * 5000)

    result = retry_with_feedback(
        cb,
        _FakeTask(prompt="t"),
        max_retries=1,
        max_feedback_chars=200,
    )
    # Look at the recorded feedback in the failed attempt
    err_text = result.attempts[0].error_text
    # Total length should be roughly 200 + truncation marker, not 5000
    assert len(err_text) < 500


# ---------------------------------------------------------------------------
# Non-dataclass task — should not crash when default apply_feedback can't reach prompt
# ---------------------------------------------------------------------------


def test_non_dataclass_task_retries_without_feedback_application():
    """If task isn't a dataclass with a prompt field, retry passes the
    original task unchanged on subsequent attempts (no error)."""
    call_count = [0]

    class _PlainTask:
        # Not a dataclass; no prompt
        pass

    def cb(task):
        call_count[0] += 1
        if call_count[0] == 1:
            return {}
        return {"ok": True}

    plain = _PlainTask()
    result = retry_with_feedback(
        cb, plain, max_retries=1
    )
    # Retry happened (count went up)
    assert call_count[0] == 2
    # Final attempt succeeded even though feedback couldn't be woven in
    assert result.succeeded
