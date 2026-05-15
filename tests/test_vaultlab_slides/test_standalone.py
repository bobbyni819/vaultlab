"""Standalone integration test for vaultlab.slides.

Implements north-star Criterion #3 ("plug-in companion"): the primary
entrypoint of ``vaultlab.slides`` must be invocable from a fresh
``tmp_path`` fixture with no prior vaultlab state.

We exercise ``build_from_plan`` on a minimal two-slide deck plan and
verify a real ``.pptx`` is written. No KB, no template assets required
beyond what ships in the package.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_build_from_plan_runs_standalone_from_fresh_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``build_from_plan`` produces a ``.pptx`` file from a minimal dict
    plan in tmp_path with no prior vaultlab state."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))

    from vaultlab.slides import build_from_plan

    out_path = tmp_path / "decks" / "standalone.pptx"

    plan = {
        "title": "Standalone deck",
        "author": "vaultlab integration test",
        "subtitle": "Demonstrates plug-in companion criterion",
        "theme": "light",
        # plain template avoids requiring the lab-branded master deck
        "template": "plain",
        "slides": [
            {
                "type": "title",
                "title": "Standalone deck",
                "subtitle": "Plug-in companion",
                "author": "vaultlab",
            },
            {
                "type": "text",
                "title": "Why this matters",
                "bullets": [
                    "New users should not need a KB to render a deck.",
                    "Audit-grade defaults must be self-contained.",
                ],
            },
        ],
    }

    result = build_from_plan(plan, out_path, write_marp=False)

    assert isinstance(result, dict)
    assert "pptx" in result
    assert Path(result["pptx"]).exists()
    # A real .pptx is a non-trivial zip archive — guard against accidentally
    # writing an empty file.
    assert Path(result["pptx"]).stat().st_size > 1_000
