"""Standalone integration test for vaultlab.workflows.

Implements north-star Criterion #3 ("plug-in companion"): the primary
entrypoints of ``vaultlab.workflows`` must be invocable from a fresh
``tmp_path`` fixture with no prior vaultlab state.

We exercise ``plan_synthesis`` — the simplest single-role workflow
builder. It returns a ``WorkflowPlan`` (a plan dataclass), not an LLM
call, so no agent execution is required.

The cfg duck-type is constructed from ``vaultlab.config.ProjectConfig``
pointing at a KB tree scaffolded inside tmp_path.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def test_plan_synthesis_runs_standalone_from_fresh_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``plan_synthesis`` returns a ``WorkflowPlan`` against a fresh KB
    scaffolded inside tmp_path with no prior vaultlab state."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))

    from vaultlab.config import ProjectConfig
    from vaultlab.workflows import WorkflowPlan, plan_synthesis

    # Minimal KB skeleton — the workflow builders peek at
    # Sources/Notes, Wiki/Concepts and Output to gather prior summaries.
    kb_dir = tmp_path / "kb"
    for sub in ("Output", "Sources/Notes", "Wiki/Concepts"):
        os.makedirs(kb_dir / sub, exist_ok=True)

    cfg = ProjectConfig(
        name="standalone-test",
        kb_path=str(kb_dir),
        domain="biology",
        domain_context="standalone smoke test",
    )

    wp = plan_synthesis(cfg, topic="standalone plug-in companion test")

    assert isinstance(wp, WorkflowPlan)
    assert wp.meeting is not None
    assert wp.meeting.topic == "standalone plug-in companion test"
    assert wp.provenance.generated_by == "synthesize"
    # Canonical path is computed relative to cfg.kb_path — should land
    # under tmp_path, demonstrating the workflow respects the caller's
    # KB without any global config.
    assert wp.canonical_output_path is not None
    assert str(kb_dir) in wp.canonical_output_path
