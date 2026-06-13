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
    state_aware_preflight,
    summarize_dataframe,
)


@pytest.fixture(autouse=True)
def _isolated_kb(tmp_path_factory, monkeypatch):
    """Point default KB routing at a throwaway dir so run_pipeline never writes
    to the developer's real KB. Tests that pass explicit kb_root/out_dir
    override this; tests that monkeypatch resolve_kb_root to raise fall back to
    <project>/out as designed."""
    kb = tmp_path_factory.mktemp("isolated_kb")
    monkeypatch.setenv("VAULTLAB_KB_ROOT", str(kb))
    yield


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

        # Categorical column reports unique_count + top_values.
        # pandas reports a string column's dtype differently across versions:
        # "object" (<=2.x default), "string" (StringDtype), "str" (pandas 3.0
        # default). Accept all so the suite is pandas-version-robust.
        group_dtype = summary["group"]["dtype"]
        assert group_dtype in ("object", "str") or "string" in group_dtype
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

    def test_two_group_bar_gets_hedged_interpretation(self, tmp_path: Path) -> None:
        pytest.importorskip("scipy")
        import csv

        proj = tmp_path / "twogroup"
        (proj / "data").mkdir(parents=True)
        csv_path = proj / "data" / "Fig4F.csv"
        # Two groups with a clear separation so the t-test is significant.
        treated = [9.0, 9.5, 10.0, 10.5, 9.8, 10.2]
        control = [2.0, 2.5, 1.8, 2.2, 1.9, 2.1]
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["arm", "abscess_area"])
            for v in treated:
                w.writerow(["treated", v])
            for v in control:
                w.writerow(["control", v])

        figures_config = {
            "Fig4F": {
                "kind": "bar",
                "source": "Fig4F.csv",
                "x": "arm",
                "y": "abscess_area",
            },
            # Non-interpreted figure: keeps the fixed fallback sidecar note.
            "Fig4F_hist": {
                "kind": "histogram",
                "source": "Fig4F.csv",
                "x": "abscess_area",
            },
        }
        result = run_pipeline(proj, figures_config=figures_config)

        assert result.methods_md is not None
        methods_text = result.methods_md.read_text(encoding="utf-8")
        # An interpretive sentence with a recomputed p-value is now present.
        assert "p=" in methods_text
        # A direction token appears (groups sort to control < treated → "a<b").
        assert "higher in" in methods_text or "lower in" in methods_text
        # Both sample sizes are cited (6 treated / 6 control).
        assert "n=6/6" in methods_text
        # Hedged voice retained; no overclaiming verbs.
        assert "appears" in methods_text
        assert "proves" not in methods_text.lower()
        assert "verification only" in methods_text

        # The bar figure's .method.md sidecar carries the finding, not boilerplate.
        bar_sidecar = result.out_dir / "Fig4F.png.method.md"
        assert bar_sidecar.is_file()
        bar_note = bar_sidecar.read_text(encoding="utf-8")
        assert "p=" in bar_note
        assert "n=6/6" in bar_note
        assert "higher in" in bar_note or "lower in" in bar_note

        # The non-interpreted histogram sidecar still renders the fallback note.
        hist_sidecar = result.out_dir / "Fig4F_hist.png.method.md"
        assert hist_sidecar.is_file()
        hist_note = hist_sidecar.read_text(encoding="utf-8")
        assert "Generated by vaultlab.analysis from a tidy result table" in hist_note
        assert "p=" not in hist_note

    def test_three_group_bar_no_fabricated_comparison(self) -> None:
        pytest.importorskip("scipy")
        import pandas as pd

        from vaultlab.analysis.pipeline import _interpret_bar_figure

        df = pd.DataFrame(
            {"grp": ["A", "A", "B", "B", "C", "C"], "val": [1, 2, 3, 4, 5, 6]}
        )
        # >2 groups, no explicit `groups` pair → no comparison.
        assert _interpret_bar_figure(df, {"kind": "bar", "x": "grp", "y": "val"}) is None

    def test_explicit_groups_numeric_dtype_string_config(self) -> None:
        pytest.importorskip("scipy")
        import pandas as pd

        from vaultlab.analysis.pipeline import _interpret_bar_figure

        # Numeric group column (dose 0/1/2) with explicit JSON-string `groups`.
        # A raw `"0" in [0, 1, 2]` membership test would mismatch and skip the
        # comparison — the str-keyed mapping must recover the real int values.
        df = pd.DataFrame(
            {
                "dose": [0, 0, 0, 1, 1, 1, 2],
                "val": [2.0, 2.5, 1.8, 9.0, 9.5, 10.0, 5.0],
            }
        )
        sentence = _interpret_bar_figure(
            df,
            {"kind": "bar", "x": "dose", "y": "val", "groups": ["0", "1"]},
        )
        assert sentence is not None
        assert "p=" in sentence
        assert "n=3/3" in sentence

    def test_methods_sidecar_stamped_template_only(self, tmp_path: Path) -> None:
        proj = tmp_path / "stamped"
        proj.mkdir()
        _make_tidy_csv(proj / "results.csv", n=30)

        result = run_pipeline(proj, figures_config={})
        assert result.methods_md is not None
        sidecar = result.out_dir / "methods.md.provenance.json"
        assert sidecar.is_file()
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["producer"] == "template-only"

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

    def test_rejects_xlsx(self, tmp_path: Path) -> None:
        proj = tmp_path / "sheet"
        proj.mkdir()
        (proj / "Fig4A.xlsx").write_bytes(b"PK\x03\x04fake-xlsx")
        with pytest.raises(ValueError) as excinfo:
            run_pipeline(proj, figures_config={})
        msg = str(excinfo.value).lower()
        assert "fig4a.xlsx" in msg
        assert "tidy" in msg or "convert" in msg

    def test_rejects_xls(self, tmp_path: Path) -> None:
        proj = tmp_path / "sheet2"
        proj.mkdir()
        (proj / "old.xls").write_bytes(b"\xd0\xcf\x11\xe0fake-xls")
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

    @pytest.mark.parametrize(
        "unsafe_name",
        ["../escape", "sub/dir/fig", ".", "..", ""],
    )
    def test_rejects_unsafe_figure_name(self, tmp_path: Path, unsafe_name: str) -> None:
        """A figure name that could escape out_dir is skipped, not written."""
        proj = tmp_path / "proj"
        proj.mkdir()
        _make_tidy_csv(proj / "results.csv")
        out = tmp_path / "out"
        cfg = {unsafe_name: {"kind": "bar", "source": "results.csv", "x": "group", "y": "score"}}
        result = run_pipeline(proj, figures_config=cfg, out_dir=out)
        # The unsafe figure is skipped — nothing emitted for it.
        assert result.figures == []
        # And nothing was written outside out_dir (traversal blocked).
        assert not (tmp_path / "escape.png").exists()
        assert not (proj.parent / "escape.png").exists()

    def test_rejects_absolute_figure_name(self, tmp_path: Path) -> None:
        """An absolute figure name must not write outside out_dir."""
        proj = tmp_path / "proj"
        proj.mkdir()
        _make_tidy_csv(proj / "results.csv")
        out = tmp_path / "out"
        target = tmp_path / "PWNED"
        cfg = {str(target): {"kind": "bar", "source": "results.csv", "x": "group", "y": "score"}}
        result = run_pipeline(proj, figures_config=cfg, out_dir=out)
        assert result.figures == []
        # The absolute-path sink must not have been written.
        assert not Path(f"{target}.png").exists()


class TestRecursiveDiscovery:
    """Discovery + scope-enforcement recurse within data/ and inputs/."""

    def test_discovers_nested_csv_in_data(self, tmp_path: Path) -> None:
        proj = tmp_path / "nested"
        (proj / "data" / "panels").mkdir(parents=True)
        nested = proj / "data" / "panels" / "Fig4A.csv"
        _make_tidy_csv(nested)

        result = run_pipeline(proj, figures_config={})
        assert nested.resolve() in result.inputs

    def test_rejects_nested_raw_in_data(self, tmp_path: Path) -> None:
        proj = tmp_path / "nested_raw"
        (proj / "data" / "sub").mkdir(parents=True)
        (proj / "data" / "sub" / "x.fastq").write_text("@r\nACGT\n+\n!!!!\n")
        _make_tidy_csv(proj / "data" / "results.csv")

        with pytest.raises(ValueError):
            run_pipeline(proj, figures_config={})

    def test_sibling_raw_dir_not_flagged(self, tmp_path: Path) -> None:
        """Raw data in an unscanned sibling folder must NOT false-flag."""
        proj = tmp_path / "with_backup"
        (proj / "raw_backup").mkdir(parents=True)
        (proj / "raw_backup" / "x.fastq").write_text("@r\nACGT\n+\n!!!!\n")
        _make_tidy_csv(proj / "results.csv")

        # Should not raise; the sibling raw dir is outside data/ and inputs/.
        result = run_pipeline(proj, figures_config={})
        assert (proj / "raw_backup" / "x.fastq").resolve() not in result.inputs


class TestOutputRouting:
    """A3/#15: default output routes to <kb>/Output/<project>/runs/<date>/."""

    def test_default_routes_to_kb(self, tmp_path: Path) -> None:
        kb = tmp_path / "kb"
        kb.mkdir()
        proj = tmp_path / "myproj"
        proj.mkdir()
        _make_tidy_csv(proj / "results.csv", n=20)

        result = run_pipeline(proj, figures_config={}, kb_root=kb)
        parts = result.out_dir.parts
        # Lands under the KB's Output/<slug>/runs/<date>/ tree.
        assert str(kb.resolve()) in str(result.out_dir)
        assert "Output" in parts
        assert "runs" in parts
        assert result.methods_md is not None and result.methods_md.is_file()

    def test_explicit_out_dir_wins(self, tmp_path: Path) -> None:
        kb = tmp_path / "kb"
        kb.mkdir()
        proj = tmp_path / "myproj2"
        proj.mkdir()
        _make_tidy_csv(proj / "results.csv", n=20)
        explicit = tmp_path / "custom_out"

        result = run_pipeline(
            proj, figures_config={}, kb_root=kb, out_dir=explicit
        )
        assert result.out_dir == explicit.resolve()

    def test_falls_back_to_project_out_when_no_kb(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import vaultlab.context as ctx

        def _raise(*_a, **_k):
            raise ctx.KbRootNotConfigured("no KB")

        monkeypatch.setattr(ctx, "resolve_kb_root", _raise)

        proj = tmp_path / "myproj3"
        proj.mkdir()
        _make_tidy_csv(proj / "results.csv", n=20)

        result = run_pipeline(proj, figures_config={})
        assert result.out_dir == (proj / "out").resolve()


class TestFigureVerification:
    """B017: a figure whose sidecar write failed must be flagged, not asserted."""

    def test_failed_sidecar_marks_figure_unverified(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        proj = tmp_path / "fail"
        proj.mkdir()
        _make_tidy_csv(proj / "results.csv", n=30)

        import vaultlab.analysis.pipeline as pipe

        def _boom(*_a, **_k):
            raise RuntimeError("disk full")

        # Force provenance writing to fail for this run.
        monkeypatch.setattr(pipe, "write_receipts", _boom)

        cfg = {"f1": {"kind": "bar", "source": "results.csv", "x": "group", "y": "score"}}
        result = run_pipeline(proj, figures_config=cfg)

        # The figure still rendered, but methods.md flags the missing sidecar.
        assert (result.out_dir / "f1.png").is_file()
        assert result.methods_md is not None
        methods_text = result.methods_md.read_text(encoding="utf-8")
        assert "[sidecar: missing]" in methods_text


class TestAuditGate:
    """Opt-in rigor_auditor gate (B6). Default off; fail loud without a runner."""

    def _stub_runner(self):
        def _runner(meeting, roles):
            return [{"output": json.dumps({"passed": True, "issues": []})}]

        return _runner

    def test_audit_attaches_verdict(self, tmp_path: Path) -> None:
        proj = tmp_path / "aud"
        proj.mkdir()
        _make_tidy_csv(proj / "results.csv", n=30)

        result = run_pipeline(
            proj, figures_config={}, audit=True, audit_runner=self._stub_runner()
        )
        assert result.audit_result is not None
        assert result.audit_result["passed"] is True
        # Empty issues proves the stub runner's output flowed through; every
        # silent-skip fallback returns a non-empty single-issue list instead.
        assert result.audit_result["issues"] == []

    def test_audit_true_without_runner_raises(self, tmp_path: Path) -> None:
        proj = tmp_path / "aud2"
        proj.mkdir()
        _make_tidy_csv(proj / "results.csv", n=30)

        with pytest.raises(ValueError, match="audit_runner"):
            run_pipeline(proj, figures_config={}, audit=True)

    def test_default_no_audit(self, tmp_path: Path) -> None:
        proj = tmp_path / "aud3"
        proj.mkdir()
        _make_tidy_csv(proj / "results.csv", n=30)

        result = run_pipeline(proj, figures_config={})
        assert result.audit_result is None


class TestStateAwarePreflight:
    """CLAUDE.md commitment #6 — pipeline reads prior state before producing."""

    def _bar_project(self, root: Path) -> tuple[Path, dict]:
        proj = root / "proj"
        proj.mkdir()
        _make_tidy_csv(proj / "results.csv", n=40)
        cfg = {"fig1": {"kind": "bar", "source": "results.csv", "x": "group", "y": "score"}}
        return proj, cfg

    def test_extend_does_not_overwrite_existing_figure(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        kb = tmp_path / "kb"
        kb.mkdir()
        proj, cfg = self._bar_project(tmp_path)

        # First (fresh) run renders the figure.
        r1 = run_pipeline(proj, figures_config=cfg, kb_root=kb)
        fig = r1.out_dir / "fig1.png"
        assert fig.is_file()
        # Capture the kept figure's sidecars so we can prove they are NOT
        # rewritten on the extend run (a rewrite would re-timestamp provenance
        # newer than the PNG it describes).
        prov = r1.out_dir / "fig1.png.provenance.json"
        method = r1.out_dir / "fig1.png.method.md"
        assert prov.is_file() and method.is_file()
        prov_before, method_before = prov.read_bytes(), method.read_bytes()
        # Replace the PNG with a sentinel so an overwrite is detectable.
        fig.write_bytes(b"SENTINEL-NOT-A-PNG")

        # Second run in extend mode must keep the existing output untouched.
        with caplog.at_level(logging.INFO, logger="vaultlab.analysis.pipeline"):
            r2 = run_pipeline(proj, figures_config=cfg, kb_root=kb, mode="extend")
        assert r2.mode == "extend"
        assert fig.read_bytes() == b"SENTINEL-NOT-A-PNG"  # not re-rendered
        assert "found 1 prior figures; extending" in caplog.text
        # The kept figure is still registered (skipped render ≠ dropped output).
        assert any("fig1" in str(p) for p in r2.figures)
        assert r2.methods_md is not None and "fig1" in r2.methods_md.read_text()
        # Kept-figure sidecars are reused verbatim, not rewritten, and the
        # figure stays verified (no fail-loud marker in methods.md).
        assert prov.read_bytes() == prov_before
        assert method.read_bytes() == method_before
        assert "[sidecar: missing]" not in r2.methods_md.read_text()

    def test_preflight_counts_prior_figures_in_kb_output(self, tmp_path: Path) -> None:
        kb = tmp_path / "kb"
        out = tmp_path / "out"
        out.mkdir()
        kb_out = kb / "myproj" / "Output"
        kb_out.mkdir(parents=True)
        (kb_out / "Fig4A.png").write_bytes(b"x")
        (kb_out / "Fig4B.png").write_bytes(b"x")

        pre = state_aware_preflight("myproj", out, kb_root=kb, mode="extend")
        assert pre.prior_figure_names == {"Fig4A", "Fig4B"}
        assert pre.message == "found 2 prior figures; extending"

    def test_unconfigured_kb_noops(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import vaultlab.context as ctx

        def _raise(*_a, **_k):
            raise ctx.KbRootNotConfigured("no KB")

        monkeypatch.setattr(ctx, "resolve_kb_root", _raise)

        proj, cfg = self._bar_project(tmp_path)
        # Default mode, no kb_root → preflight must no-op, run completes.
        result = run_pipeline(proj, figures_config=cfg)
        assert result.methods_md is not None
        assert result.methods_md.is_file()
        assert (result.out_dir / "fig1.png").is_file()


class TestContextPreservation:
    """run_pipeline must keep the project's START_HERE current (commitment #7)."""

    _START_HERE = (
        "---\nproject: myproj\nversion: 1\n---\n"
        "# START_HERE — myproj\n\n"
        "## Recent activity\n\n"
        "## Files to read first if resuming\n\n"
        "## Open questions\n"
    )

    def test_run_pipeline_updates_start_here_when_onboarded(self, tmp_path: Path) -> None:
        from vaultlab.kb.paths import project_state_path

        kb = tmp_path / "kb"
        sh = project_state_path(kb, "myproj")
        sh.parent.mkdir(parents=True, exist_ok=True)
        sh.write_text(self._START_HERE, encoding="utf-8")

        proj = tmp_path / "proj"
        proj.mkdir()
        _make_tidy_csv(proj / "results.csv")

        run_pipeline(proj, figures_config={}, project_name="myproj", kb_root=kb)

        body = sh.read_text(encoding="utf-8")
        assert "Ran analysis pipeline" in body  # activity recorded under Recent activity

    def test_run_pipeline_noop_start_here_when_not_onboarded(self, tmp_path: Path) -> None:
        # No START_HERE on disk -> update_start_here returns None; pipeline still succeeds.
        from vaultlab.kb.paths import project_state_path

        kb = tmp_path / "kb"
        kb.mkdir()
        proj = tmp_path / "proj"
        proj.mkdir()
        _make_tidy_csv(proj / "results.csv")

        result = run_pipeline(proj, figures_config={}, project_name="ghost", kb_root=kb)
        assert isinstance(result, AnalysisResult)  # no crash, no START_HERE written
        assert not project_state_path(kb, "ghost").exists()
