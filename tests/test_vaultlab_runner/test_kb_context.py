"""Tests for vaultlab.runner.kb_context.compose_preamble.

Pins the context-preservation fix (2026-06-10): the preamble must read the project's
state from the SAME canonical location onboarding + update_start_here write it
(``<kb>/Wiki/Projects/<slug>/``), not the flat ``<kb>/<slug>/`` it read before — which
made a correctly-onboarded project raise KbStateUnreadable on every sub-agent spawn,
silently defeating CLAUDE.md commitment #7.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.kb.paths import project_dir, project_state_path
from vaultlab.runner.kb_context import (
    KbContextBundle,
    KbStateUnreadable,
    compose_preamble,
    prepend_preamble,
)

SLUG = "cancer-spatial"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _onboard_canonical(kb: Path) -> None:
    """Lay out a project the way onboarding actually writes it."""
    _write(project_state_path(kb, SLUG), "# START_HERE\n\nDaily brief: spatial CODEX tonsil run.\n")
    _write(
        project_state_path(kb, SLUG).parent / "decisions-log.md",
        "# Decisions\n\n## 2099-01-01 — method\nWe use spearman after round 8.\n",
    )
    _write(project_dir(kb, SLUG) / "arc.md", "# Arc\n\nThe lineage arc body.\n")


def test_preamble_reads_canonical_state(tmp_path: Path):
    _onboard_canonical(tmp_path)
    text = compose_preamble(SLUG, kb_root=tmp_path)
    assert f"Project context preamble — {SLUG}" in text
    assert "Daily brief: spatial CODEX tonsil run." in text  # START_HERE found at canonical path
    assert "spearman after round 8" in text  # decisions-log found
    assert "arc.md" in text  # Output/<slug>/ found


def test_preamble_bundle_fields(tmp_path: Path):
    _onboard_canonical(tmp_path)
    bundle = compose_preamble(SLUG, kb_root=tmp_path, return_bundle=True)
    assert isinstance(bundle, KbContextBundle)
    assert "Daily brief" in bundle.start_here_text
    assert "spearman" in bundle.decisions_text
    assert any(name == "arc.md" for name, _ in bundle.recent_outputs)
    assert bundle.token_estimate > 0


def test_preamble_raises_when_unonboarded(tmp_path: Path):
    with pytest.raises(KbStateUnreadable) as exc:
        compose_preamble(SLUG, kb_root=tmp_path)
    # The error must point at the canonical onboarding location, not the flat folder.
    assert "Wiki" in str(exc.value) and "Projects" in str(exc.value)


def test_preamble_legacy_flat_layout_fallback(tmp_path: Path):
    # A legacy project that kept START_HERE at <kb>/<slug>/ still resolves.
    _write(tmp_path / SLUG / "START_HERE.md", "# START_HERE\n\nLegacy flat layout brief.\n")
    text = compose_preamble(SLUG, kb_root=tmp_path)
    assert "Legacy flat layout brief." in text


# ---------------------------------------------------------------------------
# prepend_preamble — the orchestrator hook (commitment #7)
# ---------------------------------------------------------------------------


def test_prepend_none_slug_is_passthrough(tmp_path: Path):
    # Not project-scoped -> no behaviour change for the caller.
    assert prepend_preamble("ORIGINAL CTX", None, kb_root=tmp_path) == "ORIGINAL CTX"
    assert prepend_preamble("ORIGINAL CTX", "", kb_root=tmp_path) == "ORIGINAL CTX"


def test_prepend_onboarded_prepends_above_rule(tmp_path: Path):
    _onboard_canonical(tmp_path)
    out = prepend_preamble("ORIGINAL CTX BODY", SLUG, kb_root=tmp_path)
    assert "Daily brief: spatial CODEX tonsil run." in out  # the preamble landed
    assert "ORIGINAL CTX BODY" in out  # the caller's context is preserved
    assert "\n\n---\n\n" in out  # separated by a rule
    assert out.index("Daily brief") < out.index("ORIGINAL CTX BODY")  # preamble first


def test_prepend_unonboarded_logs_and_passes_through(tmp_path: Path, caplog):
    # Project not onboarded -> log a warning and proceed WITHOUT the preamble
    # (a meeting must not die because context couldn't be assembled).
    import logging

    with caplog.at_level(logging.WARNING):
        out = prepend_preamble("ORIGINAL CTX", SLUG, kb_root=tmp_path)
    assert out == "ORIGINAL CTX"
    assert any("preamble unavailable" in r.message.lower() or "without it" in r.message.lower()
               for r in caplog.records)


def test_prepend_empty_context_returns_bare_preamble(tmp_path: Path):
    _onboard_canonical(tmp_path)
    out = prepend_preamble("", SLUG, kb_root=tmp_path)
    assert "Daily brief: spatial CODEX tonsil run." in out
    assert not out.startswith("\n\n---")  # no dangling separator when context is empty
