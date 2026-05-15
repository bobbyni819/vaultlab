"""Tests for vaultlab.workflows.task_weight — SPEC-F task-weight dispatch.

Covers the public surface:

* :func:`classify` — task kind / n_inputs / requires_synthesis → Weight
* :func:`model_for_weight` — Weight → model id, honoring config overrides
* :func:`model_for_task` — sugar over classify + model_for_weight
* re-export from :mod:`vaultlab.workflows`
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vaultlab.workflows.task_weight import (
    WEIGHT_TO_DEFAULT_MODEL,
    TaskSpec,
    classify,
    model_for_task,
    model_for_weight,
)


# ---------------------------------------------------------------------------
# classify(): heavy-kind matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind",
    [
        "polish",
        "respond",
        "manuscript_draft",
        "deep_think",
        "synthesize",
        "synthesis",
    ],
)
def test_heavy_kinds_classify_heavy(kind: str) -> None:
    """Synthesis-class kinds always classify as heavy."""
    spec = TaskSpec(kind=kind, n_inputs=1)
    assert classify(spec) == "heavy"


# ---------------------------------------------------------------------------
# classify(): light-kind matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind",
    [
        "extract",
        "convert",
        "format",
        "render",
    ],
)
def test_light_kinds_classify_light(kind: str) -> None:
    """Mechanical / extraction / render kinds classify as light."""
    spec = TaskSpec(kind=kind, n_inputs=1)
    assert classify(spec) == "light"


@pytest.mark.parametrize(
    "kind",
    [
        "extract",
        "convert",
        "format",
        "render",
    ],
)
def test_light_kinds_stay_light_with_small_batches(kind: str) -> None:
    """A small batch of light tasks (n_inputs <= 5) stays light."""
    spec = TaskSpec(kind=kind, n_inputs=3)
    assert classify(spec) == "light"


# ---------------------------------------------------------------------------
# classify(): medium-kind matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind",
    [
        "summarize",
        "single_paper_read",
        "abstract_only",
    ],
)
def test_medium_kinds_classify_medium_with_single_input(kind: str) -> None:
    """Single-paper summarize-class kinds classify as medium."""
    spec = TaskSpec(kind=kind, n_inputs=1)
    assert classify(spec) == "medium"


# ---------------------------------------------------------------------------
# classify(): batch upgrade rule
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["summarize", "single_paper_read", "unknown_kind"])
def test_batch_over_five_upgrades_to_heavy(kind: str) -> None:
    """A batch of >5 inputs upgrades any non-light task to heavy."""
    spec = TaskSpec(kind=kind, n_inputs=6)
    assert classify(spec) == "heavy"


def test_batch_exactly_five_does_not_upgrade() -> None:
    """The threshold is strict ``> 5``: 5 inputs stays medium."""
    spec = TaskSpec(kind="summarize", n_inputs=5)
    assert classify(spec) == "medium"


# ---------------------------------------------------------------------------
# classify(): requires_synthesis override
# ---------------------------------------------------------------------------


def test_requires_synthesis_forces_heavy() -> None:
    """``requires_synthesis=True`` upgrades any task to heavy."""
    spec = TaskSpec(kind="summarize", n_inputs=1, requires_synthesis=True)
    assert classify(spec) == "heavy"


def test_requires_synthesis_overrides_light_kind() -> None:
    """Even a light kind upgrades to heavy when synthesis is required."""
    spec = TaskSpec(kind="extract", n_inputs=1, requires_synthesis=True)
    assert classify(spec) == "heavy"


# ---------------------------------------------------------------------------
# classify(): unknown kinds
# ---------------------------------------------------------------------------


def test_unknown_kind_defaults_to_medium() -> None:
    """Unknown kinds fall back to the safe medium default."""
    spec = TaskSpec(kind="this_kind_is_not_registered", n_inputs=1)
    assert classify(spec) == "medium"


def test_unknown_kind_with_batch_goes_heavy() -> None:
    """Unknown kinds still upgrade on big batches."""
    spec = TaskSpec(kind="this_kind_is_not_registered", n_inputs=10)
    assert classify(spec) == "heavy"


# ---------------------------------------------------------------------------
# model_for_weight(): defaults
# ---------------------------------------------------------------------------


def test_default_mapping_uses_claude_model_ids(tmp_path: Path) -> None:
    """Without a config file, the defaults from CLAUDE.md are used."""
    missing = tmp_path / "does_not_exist.json"
    assert model_for_weight("light", missing) == "claude-haiku-4-5"
    assert model_for_weight("medium", missing) == "claude-sonnet-4-6"
    assert model_for_weight("heavy", missing) == "claude-opus-4-7"


def test_default_constant_matches_resolved_defaults(tmp_path: Path) -> None:
    """The exported constant mirrors the resolved defaults."""
    missing = tmp_path / "does_not_exist.json"
    for weight, expected in WEIGHT_TO_DEFAULT_MODEL.items():
        assert model_for_weight(weight, missing) == expected


# ---------------------------------------------------------------------------
# model_for_weight(): config overrides
# ---------------------------------------------------------------------------


def test_config_override_replaces_defaults(tmp_path: Path) -> None:
    """A config file can replace any subset of the weight mappings."""
    cfg = tmp_path / "dispatch.json"
    cfg.write_text(
        json.dumps(
            {
                "light": "custom-light",
                "medium": "custom-medium",
                "heavy": "custom-heavy",
            }
        ),
        encoding="utf-8",
    )
    assert model_for_weight("light", cfg) == "custom-light"
    assert model_for_weight("medium", cfg) == "custom-medium"
    assert model_for_weight("heavy", cfg) == "custom-heavy"


def test_config_partial_override_keeps_defaults_for_missing_keys(tmp_path: Path) -> None:
    """Only listed keys are overridden; the rest fall back to defaults."""
    cfg = tmp_path / "dispatch.json"
    cfg.write_text(json.dumps({"heavy": "custom-heavy"}), encoding="utf-8")
    assert model_for_weight("light", cfg) == "claude-haiku-4-5"
    assert model_for_weight("medium", cfg) == "claude-sonnet-4-6"
    assert model_for_weight("heavy", cfg) == "custom-heavy"


def test_config_ignores_unknown_keys(tmp_path: Path) -> None:
    """Unknown keys are silently ignored."""
    cfg = tmp_path / "dispatch.json"
    cfg.write_text(
        json.dumps({"super_heavy": "made-up", "medium": "custom-medium"}),
        encoding="utf-8",
    )
    assert model_for_weight("medium", cfg) == "custom-medium"
    assert model_for_weight("heavy", cfg) == "claude-opus-4-7"


def test_malformed_config_falls_back_to_defaults(tmp_path: Path) -> None:
    """A corrupted config file does not crash — defaults are returned."""
    cfg = tmp_path / "dispatch.json"
    cfg.write_text("{ this is not json", encoding="utf-8")
    assert model_for_weight("light", cfg) == "claude-haiku-4-5"
    assert model_for_weight("medium", cfg) == "claude-sonnet-4-6"
    assert model_for_weight("heavy", cfg) == "claude-opus-4-7"


def test_config_with_non_object_root_falls_back(tmp_path: Path) -> None:
    """A JSON array (non-object) root is ignored gracefully."""
    cfg = tmp_path / "dispatch.json"
    cfg.write_text(json.dumps(["light", "medium"]), encoding="utf-8")
    assert model_for_weight("medium", cfg) == "claude-sonnet-4-6"


def test_env_var_overrides_default_config_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``VAULTLAB_DISPATCH_CONFIG`` selects the config path when none is passed."""
    cfg = tmp_path / "from_env.json"
    cfg.write_text(json.dumps({"medium": "env-medium"}), encoding="utf-8")
    monkeypatch.setenv("VAULTLAB_DISPATCH_CONFIG", str(cfg))
    # Pass explicit None → fall back through env var
    assert model_for_weight("medium", None) == "env-medium"


# ---------------------------------------------------------------------------
# model_for_task(): sugar
# ---------------------------------------------------------------------------


def test_model_for_task_classifies_then_resolves(tmp_path: Path) -> None:
    """``model_for_task`` chains classify + model_for_weight."""
    cfg = tmp_path / "dispatch.json"
    cfg.write_text(json.dumps({"heavy": "custom-heavy"}), encoding="utf-8")
    spec = TaskSpec(kind="polish", n_inputs=1)
    assert model_for_task(spec, cfg) == "custom-heavy"


def test_model_for_task_uses_defaults_when_no_config(tmp_path: Path) -> None:
    """Without an override, ``model_for_task`` returns the default model."""
    missing = tmp_path / "no.json"
    spec = TaskSpec(kind="summarize", n_inputs=1)
    assert model_for_task(spec, missing) == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# Public re-exports from vaultlab.workflows
# ---------------------------------------------------------------------------


def test_public_reexports_from_workflows() -> None:
    """Symbols are importable from the top-level ``vaultlab.workflows``."""
    from vaultlab import workflows as wf

    assert wf.classify is classify
    assert wf.model_for_weight is model_for_weight
    assert wf.model_for_task is model_for_task
    assert wf.TaskSpec is TaskSpec
    assert wf.WEIGHT_TO_DEFAULT_MODEL == WEIGHT_TO_DEFAULT_MODEL


# ---------------------------------------------------------------------------
# Example config: examples/configs/dispatch.json matches defaults
# ---------------------------------------------------------------------------


def test_examples_dispatch_json_matches_defaults() -> None:
    """The starter config in examples/configs/ must stay in sync with defaults."""
    repo_root = Path(__file__).resolve().parents[2]
    example = repo_root / "examples" / "configs" / "dispatch.json"
    assert example.exists(), f"missing example config: {example}"
    data = json.loads(example.read_text(encoding="utf-8"))
    for weight, expected in WEIGHT_TO_DEFAULT_MODEL.items():
        assert data[weight] == expected
