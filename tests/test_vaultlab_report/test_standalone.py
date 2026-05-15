"""Standalone integration test for vaultlab.report.

Implements north-star Criterion #3 ("plug-in companion"): the primary
entrypoint of ``vaultlab.report`` must be invocable from a fresh
``tmp_path`` fixture with no prior vaultlab state.

We exercise ``write_report`` with a tiny component-driven sections list
and verify a self-contained HTML file is produced in tmp_path. The
HTML module is pure-Python — no external assets, no LLM, no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_write_report_runs_standalone_from_fresh_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``write_report`` produces a self-contained ``.html`` file from a
    minimal component-driven sections list with no prior state."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))

    from vaultlab.report import components as c
    from vaultlab.report import write_report

    sections = [
        c.tldr_box(
            [
                "Standalone vaultlab.report invocation",
                "No KB required",
                "No external assets",
            ]
        ),
        c.card_grid(
            [
                c.severity_card("Init", body="OK", severity="good"),
                c.severity_card("Render", body="OK", severity="good"),
            ]
        ),
    ]

    out = tmp_path / "reports" / "standalone.html"
    written = write_report(
        out,
        "Standalone smoke report",
        sections,
        eyebrow="vaultlab · integration test",
        subtitle="plug-in companion check",
        theme="light",
    )

    assert written == out
    assert out.exists()

    html = out.read_text(encoding="utf-8")
    # Sanity: complete HTML doc + the rendered components.
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert "Standalone smoke report" in html
    assert "Standalone vaultlab.report invocation" in html
    # CSS + JS should be inlined (single-file invariant).
    assert "<style>" in html
    assert "<script>" in html
