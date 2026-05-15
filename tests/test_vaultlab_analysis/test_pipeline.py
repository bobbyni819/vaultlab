"""Tests for vaultlab.analysis — result-analysis pipeline (SPEC-A).

Covers the four SPEC-A success criteria:

1. `run_pipeline(project_dir) -> AnalysisResult` consumes a project dir
   with tidy result tables and produces figures + methods + audit.
2. The pipeline does NOT run analyses; it rejects raw-data formats.
3. Methods text is grounded — every column gets named with its sample
   size; figures cite their source file + columns.
4. The shape of the AnalysisResult is documented and stable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from vaultlab.analysis import (
    AnalysisResult,
    compose_methods_paragraph,
    run_pipeline,
    summarize_dataframe,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tidy_csv(path: Path, n: int = 100) -> None:
    """Write a 100-row, 3-column tidy CSV.

    Columns: ``group`` (categorical 'A'/'B'/'C'), ``score`` (numeric float),
    ``count`` (numeric int).
    """
    import random

    random.seed(42)
    rows = []
    groups = ["A", "B", "C"]
    for i in range(n):
        rows.append(
            {
                "group": groups[i % 3],
                "score": round(random.gauss(10, 2), 3),
                "count": random.randint(0, 50),
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------


class TestSummarizeDataframe:
    def test_numeric_and_categorical(self, tmp_path: Path) -> None:
        df = pd.DataFrame(
            {
                "group": ["A", "B", "A", "C", "B"],
                "score": [1.0, 2.0, 3.0, 4.0, 5.0],
                "count": [10, 20, 30, 40, 50],
            }
        )
        summary = summarize_dataframe(df)

        assert set(summary.keys()) == {"group", "score", "count"}

        # Categorical column reports unique_count + top_values
        assert summary["group"]["dtype"].startswith("object") or "string" in summary["group"]["dtype"]
        assert summary["group"]["n"] == 5
        assert summary["group"]["n_missing"] == 0
        assert summary["group"]["unique_count"] == 3
        assert isinstance(summary["group"]["top_values"], list)

        # Numeric column reports mean/std/min/max
        assert summary["score"]["n"] == 5
        assert summary["score"]["mean"] == pytest.approx(3.0)
        assert summary["score"]["min"] == 1.0
        assert summary["score"]["max"] == 5.0

    def test_missing_values_counted(self) -> None:
        df = pd.DataFrame({"x": [1.0, None, 3.0, None, 5.0]})
        summary = summarize_dataframe(df)
        assert summary["x"]["n"] == 3
        assert summary["x"]["n_missing"] == 2
        assert summary["x"]["mean"] == pytest.approx(3.0)

    def test_summary_is_json_serializable(self) -> None:
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "x"]})
        summary = summarize_dataframe(df)
        # If anything is a numpy scalar this raises.
        json.dumps(summary)


# ---------------------------------------------------------------------------
# Methods paragraph
# ---------------------------------------------------------------------------


class TestComposeMethodsParagraph:
    def test_cites_each_file_and_column_with_n(self) -> None:
        stats_summary = {
            "expression.csv": {
                "group": {
                    "dtype": "object",
                    "n": 50,
                    "n_missing": 0,
                    "unique_count": 3,
                    "top_values": [{"value": "A", "count": 20}],
                },
                "score": {
                    "dtype": "float64",
                    "n": 50,
                    "n_missing": 0,
                    "mean": 10.1,
                    "std": 2.0,
                    "min": 5.0,
                    "max": 15.0,
                },
            }
        }
        text = compose_methods_paragraph(
            stats_summary,
            figure_entries=[
                {
                    "name": "fig1",
                    "kind": "bar",
                    "source": "expression.csv",
                    "x": "group",
                    "y": "score",
                    "path": "out/fig1.png",
                }
            ],
            project_meta={"project_name": "test-proj"},
        )
        # File is cited
        assert "expression.csv" in text
        # Each column is cited
        assert "`group`" in text
        assert "`score`" in text
        # Sample sizes appear
        assert "n=50" in text
        # Figure is cited with its source + columns
        assert "fig1" in text
        # Hedged voice appears (per AGENTS.md quality bar)
        assert "may indicate" in text or "consistent with" in text


# ---------------------------------------------------------------------------
# Pipeline — integration
# ---------------------------------------------------------------------------


class TestRunPipeline:
    def test_end_to_end_csv_inputs(self, tmp_path: Path) -> None:
        proj = tmp_path / "demo"
        (proj / "inputs").mkdir(parents=True)
        _make_tidy_csv(proj / "inputs" / "results.csv", n=100)

        figures_config = {
            "fig_score_hist": {
                "kind": "histogram",
                "source": "results.csv",
                "x": "score",
                "title": "Score distribution",
            },
            "fig_count_by_group": {
                "kind": "bar",
                "source": "results.csv",
                "x": "group",
                "y": "count",
            },
        }

        result = run_pipeline(proj, figures_config=figures_config)

        assert isinstance(result, AnalysisResult)
        assert result.project_dir == proj.resolve()
        assert len(result.figures) == 2
        for fig in result.figures:
            assert fig.is_file()
            assert fig.suffix == ".png"

        # Stats summary covers our 3 columns.
        assert "results.csv" in result.stats_summary
        cols = result.stats_summary["results.csv"]
        assert {"group", "score", "count"} <= set(cols.keys())
        assert cols["score"]["n"] == 100

        # Methods.md exists and references the file + columns.
        assert result.methods_md is not None
        assert result.methods_md.is_file()
        methods_text = result.methods_md.read_text(encoding="utf-8")
        assert "results.csv" in methods_text
        assert "`score`" in methods_text
        assert "n=100" in methods_text

        # Provenance sidecars exist for each figure + methods.md.
        # write_receipts emits .provenance.json + .method.md per artifact;
        # we should see at least 2 figures × 2 + methods × 2 = 6 sidecars.
        assert len(result.manifest_paths) >= 6
        # Each .provenance.json must be valid JSON with the expected shape.
        for path in result.manifest_paths:
            if path.suffix == ".json":
                payload = json.loads(path.read_text(encoding="utf-8"))
                assert payload["generated_by"] == "vaultlab.analysis.run_pipeline"
                assert payload["kind"] in {"figure", "methods_section"}

        # The append-only JSONL index is also written.
        index = result.out_dir / ".vaultlab-provenance.jsonl"
        assert index.is_file()
        index_lines = [
            json.loads(line)
            for line in index.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        # One entry per terminal artifact (>= 3 — 2 figs + methods.md).
        assert len(index_lines) >= 3

        # stats_summary.json shipped as a top-level audit hook.
        stats_path = result.out_dir / "stats_summary.json"
        assert stats_path.is_file()
        loaded = json.loads(stats_path.read_text(encoding="utf-8"))
        assert "results.csv" in loaded

    def test_loads_figures_config_from_json_file(self, tmp_path: Path) -> None:
        proj = tmp_path / "json-cfg"
        proj.mkdir()
        _make_tidy_csv(proj / "results.csv", n=50)
        (proj / "vaultlab-analysis.json").write_text(
            json.dumps(
                {
                    "figures": {
                        "score_hist": {
                            "kind": "histogram",
                            "source": "results.csv",
                            "x": "score",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

        result = run_pipeline(proj)
        assert len(result.figures) == 1
        assert result.figures[0].name == "score_hist.png"

    def test_parquet_input(self, tmp_path: Path) -> None:
        pytest.importorskip("pyarrow")
        proj = tmp_path / "pq"
        proj.mkdir()
        df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "y": [2.0, 4.0, 6.0, 8.0]})
        df.to_parquet(proj / "results.parquet")

        result = run_pipeline(
            proj,
            figures_config={
                "scatter": {
                    "kind": "scatter",
                    "source": "results.parquet",
                    "x": "x",
                    "y": "y",
                }
            },
        )
        assert "results.parquet" in result.stats_summary
        assert len(result.figures) == 1


class TestScopeDiscipline:
    """Pipeline must REJECT raw-data formats per the layer-above-analysis rule."""

    def test_rejects_fastq(self, tmp_path: Path) -> None:
        proj = tmp_path / "raw"
        (proj / "inputs").mkdir(parents=True)
        (proj / "inputs" / "sample.fastq").write_text("@read1\nACGT\n+\n!!!!\n")
        # Also drop a valid CSV so input discovery doesn't short-circuit on emptiness.
        _make_tidy_csv(proj / "inputs" / "results.csv")

        with pytest.raises(ValueError) as excinfo:
            run_pipeline(proj, figures_config={})
        msg = str(excinfo.value)
        assert "raw" in msg.lower() or "analysis code" in msg.lower()
        assert ".fastq" in msg or "sample.fastq" in msg

    def test_rejects_h5ad(self, tmp_path: Path) -> None:
        proj = tmp_path / "raw2"
        proj.mkdir()
        (proj / "matrix.h5ad").write_bytes(b"HDF5fake")
        with pytest.raises(ValueError):
            run_pipeline(proj, figures_config={})

    def test_rejects_microscopy(self, tmp_path: Path) -> None:
        proj = tmp_path / "raw3"
        proj.mkdir()
        (proj / "image.nd2").write_bytes(b"\x00\x00")
        with pytest.raises(ValueError):
            run_pipeline(proj, figures_config={})

    def test_rejects_mzml(self, tmp_path: Path) -> None:
        proj = tmp_path / "raw4"
        proj.mkdir()
        (proj / "spec.mzML").write_bytes(b"<xml />")  # extension is case-insensitive
        with pytest.raises(ValueError):
            run_pipeline(proj, figures_config={})

    def test_rejects_bam(self, tmp_path: Path) -> None:
        proj = tmp_path / "raw5"
        proj.mkdir()
        (proj / "reads.bam").write_bytes(b"BAM\x01")
        with pytest.raises(ValueError):
            run_pipeline(proj, figures_config={})

    def test_accepts_tidy_only_project(self, tmp_path: Path) -> None:
        """Sanity: a project with only tidy files does not raise."""
        proj = tmp_path / "clean"
        proj.mkdir()
        _make_tidy_csv(proj / "results.csv")
        # Should not raise.
        result = run_pipeline(proj, figures_config={})
        assert result.project_dir == proj.resolve()
        # No figures requested → no figures emitted, but methods still written.
        assert result.figures == []
        assert result.methods_md is not None
