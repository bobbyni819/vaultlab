"""Standalone integration test for vaultlab.manuscript.

Implements north-star Criterion #3 ("plug-in companion"): the primary
entrypoint of ``vaultlab.manuscript`` must be invocable from a fresh
``tmp_path`` fixture with no prior vaultlab state.

We exercise ``write_polish_report`` on a short markdown string. The
polish checkers are pure-Python (no LLM needed); the only filesystem
side effects are the report + its provenance sidecars under tmp_path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_write_polish_report_runs_standalone_from_fresh_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``write_polish_report`` writes a polish report + provenance
    receipts from a string input in tmp_path with no prior state."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))

    from vaultlab.manuscript.polish import write_polish_report

    # Text with one US spelling and a sentence > 30 words to trigger both
    # checkers, exercising the non-empty path of the report builder.
    text = (
        "We measured color contrast and analyzed the fiber distribution. "
        "This intentionally long sentence contains more than thirty words "
        "to deliberately trigger the polish checker that flags overly long "
        "sentences exceeding the documented threshold for clear academic "
        "prose, ensuring the report aggregator has at least one entry."
    )

    out = tmp_path / "polish-report.md"
    written = write_polish_report(out, text, source_path="draft.md", max_words=30)

    assert written == out
    assert out.exists()

    body = out.read_text(encoding="utf-8")
    assert "Polish report" in body
    # At least one of the checkers should have fired with the seeded text.
    assert "Long sentences" in body or "spelling" in body.lower()

    # Red Line #2: provenance receipt must be written alongside the artifact.
    prov_path = out.with_name(out.name + ".provenance.json")
    method_path = out.with_name(out.name + ".method.md")
    assert prov_path.exists(), "polish report missing .provenance.json sidecar"
    assert method_path.exists(), "polish report missing .method.md sidecar"

    record = json.loads(prov_path.read_text(encoding="utf-8"))
    assert record["generated_by"].endswith("write_polish_report")
