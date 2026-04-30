"""Tests for vaultlab.config.ProjectConfig.

Lifted from ``bobby-tools/tests/test_bobby_ailab/test_config.py``.
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from vaultlab.config import ProjectConfig, load_project_config


def _write_project(dir_: str, data: dict) -> str:
    path = os.path.join(dir_, ".bobby-project.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path


def test_load_project_config_minimal_fields() -> None:
    with tempfile.TemporaryDirectory() as d:
        _write_project(d, {"name": "test", "kb_path": "/tmp/kb"})
        cfg = load_project_config(d)
    assert cfg.name == "test"
    assert cfg.kb_path == "/tmp/kb"
    assert cfg.domain == ""
    assert cfg.significance_thresholds.correlation_rho == pytest.approx(0.2)


def test_load_project_config_full_fields() -> None:
    data = {
        "name": "metabolism",
        "kb_path": "G:/My Drive/Knowledge/metabolism",
        "domain": "spatial metabolomics",
        "domain_context": "MALDI + CODEX intestine",
        "data_dirs": ["/data/csvs"],
        "figure_dirs": ["/figs"],
        "output_dirs": {"private": "/kb/Output", "shared": "/repo/results"},
        "significance_thresholds": {
            "correlation_rho": 0.3,
            "fdr_alpha": 0.01,
        },
        "target_journal": "Nature Metabolism",
        "hypotheses": ["LPI is enriched in epithelium"],
    }
    with tempfile.TemporaryDirectory() as d:
        _write_project(d, data)
        cfg = load_project_config(d)
    assert cfg.domain == "spatial metabolomics"
    assert cfg.data_dirs == ["/data/csvs"]
    assert cfg.output_dirs["shared"] == "/repo/results"
    assert cfg.significance_thresholds.correlation_rho == pytest.approx(0.3)
    assert cfg.significance_thresholds.cramers_v_meaningful == pytest.approx(0.3)  # default
    assert cfg.hypotheses == ["LPI is enriched in epithelium"]


def test_load_project_config_missing_raises() -> None:
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(FileNotFoundError):
            load_project_config(d)


def test_context_summary_includes_key_fields() -> None:
    cfg = ProjectConfig(
        name="test",
        kb_path="/tmp",
        domain="metabolomics",
        domain_context="intestine",
        target_journal="Cell",
        hypotheses=["H1", "H2"],
    )
    summary = cfg.context_summary()
    assert "PROJECT: test" in summary
    assert "metabolomics" in summary
    assert "intestine" in summary
    assert "Cell" in summary
    assert "H1" in summary and "H2" in summary
    assert "rho>=" in summary


def test_context_summary_skips_empty_fields() -> None:
    cfg = ProjectConfig(name="test", kb_path="/tmp")
    summary = cfg.context_summary()
    assert "PROJECT: test" in summary
    assert "Domain:" not in summary
    assert "Target journal:" not in summary
    assert "Hypotheses:" not in summary
