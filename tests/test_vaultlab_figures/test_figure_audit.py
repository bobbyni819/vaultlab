"""Offline tests for the /figure-audit engine (no network / API key).

Verdicts are injected via ``verdict_fn`` (the Claude-Code-as-LLM seam), which also exercises
the same ``validate_verdict`` enforcement the SDK path uses.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vaultlab.figures.verify_semantic import (
    SchemaViolation,
    audit_figure_claims,
    render_report_md,
    write_audit_report,
)


def _verdicts(mapping):
    """Return a verdict_fn that looks up a canned verdict by claim text."""
    def fn(claim, figure_path):  # noqa: ARG001
        return mapping[claim]
    return fn


def test_audit_counts_flags_and_overall():
    pairs = [
        ("a/Fig1.png", "faithful claim"),
        ("a/Fig2.png", "invented p-value"),
        ("a/Fig3.png", "overreaching claim"),
    ]
    vf = _verdicts({
        "faithful claim": {"verdict": "SUPPORTED", "evidence_anchors": ["bar ~5"], "confidence": 0.9},
        "invented p-value": {"verdict": "FABRICATED", "evidence_anchors": ["no p-value shown"], "confidence": 0.95},
        "overreaching claim": {"verdict": "PARTIAL", "evidence_anchors": ["true for 1 of 3 bars"], "confidence": 0.7},
    })
    report = audit_figure_claims(pairs, project="proj", verdict_fn=vf)

    assert report.n_claims == 3
    assert report.n_flagged == 2  # FABRICATED + PARTIAL flagged; SUPPORTED clean
    assert report.overall == "flags_found"
    assert report.verdict_counts == {"SUPPORTED": 1, "PARTIAL": 1, "UNSUPPORTED": 0, "FABRICATED": 1}
    assert report.model == "claude-code-as-llm"
    # PARTIAL must count as flagged (binary collapse matches the benchmark)
    partial = next(a for a in report.audits if a.verdict == "PARTIAL")
    assert partial.flagged is True
    supported = next(a for a in report.audits if a.verdict == "SUPPORTED")
    assert supported.flagged is False


def test_audit_all_clean():
    pairs = [("Fig.png", "ok")]
    vf = _verdicts({"ok": {"verdict": "SUPPORTED", "evidence_anchors": ["x"], "confidence": 0.8}})
    report = audit_figure_claims(pairs, verdict_fn=vf)
    assert report.overall == "clean"
    assert report.n_flagged == 0


def test_audit_empty_pairs_raises():
    with pytest.raises(ValueError):
        audit_figure_claims([], verdict_fn=_verdicts({}))


def test_audit_surfaces_invalid_injected_verdict():
    pairs = [("Fig.png", "c")]
    vf = _verdicts({"c": {"verdict": "MAYBE", "evidence_anchors": ["x"], "confidence": 0.5}})
    with pytest.raises(SchemaViolation):
        audit_figure_claims(pairs, verdict_fn=vf)


def test_write_audit_report_emits_json_md_provenance(tmp_path: Path):
    pairs = [("Fig4A_bar.png", "B220+ is highest")]
    vf = _verdicts({"B220+ is highest": {"verdict": "SUPPORTED", "evidence_anchors": ["B220+ bar ~57"], "confidence": 0.9}})
    report = audit_figure_claims(pairs, project="elife-stress", verdict_fn=vf)

    paths = write_audit_report(report, tmp_path, slug="Fig4A_bar", date_str="2026-06-09")
    assert paths["json"].exists() and paths["md"].exists()
    assert paths["json"].name == "figure-audit-Fig4A_bar-2026-06-09.json"
    # provenance receipt written next to the md
    assert (tmp_path / "figure-audit-Fig4A_bar-2026-06-09.md.provenance.json").exists()

    loaded = json.loads(paths["json"].read_text())
    assert loaded["overall"] == "clean"
    assert loaded["audits"][0]["verdict"] == "SUPPORTED"

    md = paths["md"].read_text()
    assert "Figure-claim audit" in md
    assert "B220+ bar ~57" in md  # evidence anchor surfaced


def test_render_report_md_flags_first():
    pairs = [("F1.png", "clean one"), ("F2.png", "bad one")]
    vf = _verdicts({
        "clean one": {"verdict": "SUPPORTED", "evidence_anchors": ["ok"], "confidence": 0.9},
        "bad one": {"verdict": "UNSUPPORTED", "evidence_anchors": ["wrong panel"], "confidence": 0.9},
    })
    md = render_report_md(audit_figure_claims(pairs, verdict_fn=vf))
    # flagged section header must appear before the clean one (the bare verdict words
    # also occur in the header counts line, so match the per-claim section markers)
    assert md.index("⚠️ UNSUPPORTED") < md.index("✅ SUPPORTED")
