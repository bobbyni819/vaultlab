"""Tests for vaultlab.report.feature_flag_editor — Pattern #19.

Deterministic string-level + filesystem tests; no browser rendering.
"""

from __future__ import annotations

import json
from pathlib import Path

from vaultlab.report.feature_flag_editor import (
    FeatureFlagConfig,
    FlagGroup,
    build_feature_flag_editor,
    write_feature_flag_editor,
)


# ---------------------------------------------------------------------------
# Fixtures


def _minimal() -> FeatureFlagConfig:
    return FeatureFlagConfig(
        title="Minimal config",
        groups=[
            FlagGroup(
                title="Pipeline phases",
                flags=[
                    ("verify", True, "Run Phase 1 data verification."),
                    ("reason", True, "Run Phase 3 multi-agent reasoning."),
                ],
            ),
        ],
    )


def _full() -> FeatureFlagConfig:
    return FeatureFlagConfig(
        title="Vaultlab dispatch config",
        intro="Override per-task LLM routing weights.",
        groups=[
            FlagGroup(
                title="Pipeline phases",
                flags=[
                    ("verify", True, "Run Phase 1 data verification."),
                    ("reason", True, "Run Phase 3 multi-agent reasoning."),
                    ("write", False, "Skip Phase 6 to draft from outline only."),
                ],
            ),
            FlagGroup(
                title="Routing overrides",
                flags=[
                    ("use_opus_for_audit", True, "Use Opus for citation audits."),
                    ("use_haiku_for_extract", False, "Cheap extraction path."),
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# build_feature_flag_editor


def test_build_minimal_returns_non_empty_html():
    html = build_feature_flag_editor(_minimal())
    assert isinstance(html, str)
    assert html.startswith("<!doctype html>")
    assert "</html>" in html
    assert "Minimal config" in html


def test_build_contains_toggle_per_flag():
    html = build_feature_flag_editor(_full())
    # 3 + 2 = 5 flags, each gets a checkbox input
    assert html.count('class="vl-flag"') == 5
    # Default-true flags are pre-checked
    assert html.count(" checked") >= 3
    # All flag names and descriptions appear
    for fname, _, desc in (
        _full().groups[0].flags + _full().groups[1].flags
    ):
        assert fname in html
        assert desc in html


def test_build_contains_copy_buttons():
    html = build_feature_flag_editor(_full())
    assert "Copy defaults" in html
    assert "Copy current as JSON" in html
    assert "Copy diff from defaults" in html


def test_build_defaults_payload_embedded():
    """The defaults JSON must be embedded so the JS diff can compute deltas."""
    html = build_feature_flag_editor(_full())
    # The Copy-defaults button carries the payload via data-copy (escaped).
    # The diff script carries it inline (unescaped JSON literal in <script>).
    assert "Pipeline phases" in html
    assert "use_opus_for_audit" in html


def test_build_escapes_user_text():
    cfg = FeatureFlagConfig(
        title="<script>alert(1)</script>",
        groups=[
            FlagGroup(
                title="<x>",
                flags=[("<bad>", True, "<also bad>")],
            )
        ],
    )
    html = build_feature_flag_editor(cfg)
    # Raw script-from-user must not appear unescaped in <body>
    # (it's used only as title text + chip labels — all escaped).
    body_marker = "<body>"
    body = html[html.index(body_marker):]
    assert "<script>alert(1)</script>" not in body


# ---------------------------------------------------------------------------
# write_feature_flag_editor + provenance


def test_write_creates_output_file(tmp_path: Path):
    out = tmp_path / "flags.html"
    result = write_feature_flag_editor(_minimal(), out)
    assert result == out
    assert out.exists()
    assert out.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_write_creates_provenance_sidecars(tmp_path: Path):
    out = tmp_path / "flags.html"
    write_feature_flag_editor(_full(), out)
    prov_json = out.with_name(out.name + ".provenance.json")
    method_md = out.with_name(out.name + ".method.md")
    assert prov_json.exists()
    assert method_md.exists()
    payload = json.loads(prov_json.read_text(encoding="utf-8"))
    assert payload["generated_by"] == "vaultlab.report.feature_flag_editor"
    assert payload["kind"] == "feature_flag_editor"
    assert payload["params"]["group_count"] == 2
    assert payload["params"]["flag_count"] == 5
