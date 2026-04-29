"""Tests for vaultlab.figures.report — figure-in-markdown report generator."""

from __future__ import annotations

from pathlib import Path

import pytest


def _make_fake_png(path: Path) -> None:
    """Write a 1-byte 'figure' file (we don't care about image validity)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)


class TestRenderReport:
    def test_writes_markdown_with_frontmatter(self, tmp_path: Path) -> None:
        from vaultlab.figures.report import FigureEntry, render_report

        _make_fake_png(tmp_path / "a.png")
        out = render_report(
            entries=[FigureEntry(figure="a.png", caption="cap A")],
            output_path=tmp_path / "report.md",
            title="Test report",
            working_dir=tmp_path,
        )

        assert out.report_path.exists()
        text = out.report_path.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        assert "title: Test report" in text
        assert "type: figure-report" in text
        assert "n_figures: 1" in text
        assert "# Test report" in text
        assert "*cap A*" in text  # caption italicized

    def test_copy_figures_into_subdir(self, tmp_path: Path) -> None:
        from vaultlab.figures.report import FigureEntry, render_report

        src = tmp_path / "src"
        src.mkdir()
        _make_fake_png(src / "fig.png")

        out = render_report(
            entries=[FigureEntry(figure=str(src / "fig.png"), caption="x")],
            output_path=tmp_path / "out" / "r.md",
            title="r",
            copy_figures=True,
        )

        assert out.figures_dir == tmp_path / "out" / "figures"
        assert (tmp_path / "out" / "figures" / "fig.png").exists()
        # Markdown references the copied figure relative to the report
        text = out.report_path.read_text()
        assert "figures/fig.png" in text

    def test_no_copy_uses_path_as_given(self, tmp_path: Path) -> None:
        from vaultlab.figures.report import FigureEntry, render_report

        _make_fake_png(tmp_path / "a.png")
        out = render_report(
            entries=[FigureEntry(figure="a.png", caption="x")],
            output_path=tmp_path / "r.md",
            title="r",
            working_dir=tmp_path,
            copy_figures=False,
        )

        assert out.figures_dir is None
        text = out.report_path.read_text()
        # Embedded path is the (relative) original
        assert "a.png" in text

    def test_results_and_notes_sections(self, tmp_path: Path) -> None:
        from vaultlab.figures.report import FigureEntry, render_report

        _make_fake_png(tmp_path / "a.png")
        out = render_report(
            entries=[
                FigureEntry(
                    figure="a.png",
                    caption="cap",
                    results="Three populations resolve at resolution=0.5.",
                    notes="Confirm with TCR-seq overlap.",
                )
            ],
            output_path=tmp_path / "r.md",
            title="r",
            working_dir=tmp_path,
        )
        text = out.report_path.read_text()
        assert "### Results" in text
        assert "Three populations resolve" in text
        assert "### Notes" in text
        assert "Confirm with TCR-seq" in text

    def test_section_title_humanizes_figure_stem(self, tmp_path: Path) -> None:
        from vaultlab.figures.report import FigureEntry, render_report

        _make_fake_png(tmp_path / "cluster_umap_v3.png")
        out = render_report(
            entries=[FigureEntry(figure="cluster_umap_v3.png", caption="cap")],
            output_path=tmp_path / "r.md",
            title="r",
            working_dir=tmp_path,
        )
        text = out.report_path.read_text()
        # Auto-derived from stem: title-cased words
        assert "Cluster Umap V3" in text

    def test_explicit_title_overrides_stem(self, tmp_path: Path) -> None:
        from vaultlab.figures.report import FigureEntry, render_report

        _make_fake_png(tmp_path / "x.png")
        out = render_report(
            entries=[FigureEntry(figure="x.png", caption="cap", title="Custom Heading")],
            output_path=tmp_path / "r.md",
            title="r",
            working_dir=tmp_path,
        )
        text = out.report_path.read_text()
        assert "Custom Heading" in text

    def test_multi_entry_report_has_dividers(self, tmp_path: Path) -> None:
        from vaultlab.figures.report import FigureEntry, render_report

        for i in range(3):
            _make_fake_png(tmp_path / f"f{i}.png")
        out = render_report(
            entries=[FigureEntry(figure=f"f{i}.png", caption=f"c{i}") for i in range(3)],
            output_path=tmp_path / "r.md",
            title="multi",
            working_dir=tmp_path,
        )
        text = out.report_path.read_text()
        # Three sections, each with a leading ---
        assert text.count("\n---\n") >= 3
        assert "n_figures: 3" in text

    def test_missing_figure_does_not_crash(self, tmp_path: Path) -> None:
        from vaultlab.figures.report import FigureEntry, render_report

        out = render_report(
            entries=[FigureEntry(figure="not-here.png", caption="x")],
            output_path=tmp_path / "r.md",
            title="r",
            working_dir=tmp_path,
            copy_figures=True,
        )
        # Path is embedded as-given so user can fix manually
        text = out.report_path.read_text()
        assert "not-here.png" in text

    def test_open_command_returned(self, tmp_path: Path) -> None:
        from vaultlab.figures.report import FigureEntry, render_report

        _make_fake_png(tmp_path / "a.png")
        out = render_report(
            entries=[FigureEntry(figure="a.png", caption="x")],
            output_path=tmp_path / "review-report.md",
            title="r",
            working_dir=tmp_path,
        )
        assert out.open_command == "bobby-kb open review-report"

    def test_empty_entries_raises(self, tmp_path: Path) -> None:
        from vaultlab.figures.report import render_report

        with pytest.raises(ValueError, match="at least one"):
            render_report(
                entries=[],
                output_path=tmp_path / "r.md",
                title="r",
            )

    def test_filename_collision_dedupes(self, tmp_path: Path) -> None:
        from vaultlab.figures.report import FigureEntry, render_report

        # Two figures from different folders, same filename
        a = tmp_path / "a" / "fig.png"
        b = tmp_path / "b" / "fig.png"
        _make_fake_png(a)
        _make_fake_png(b)

        out = render_report(
            entries=[
                FigureEntry(figure=str(a), caption="A"),
                FigureEntry(figure=str(b), caption="B"),
            ],
            output_path=tmp_path / "r.md",
            title="dup",
        )
        figures = sorted(p.name for p in out.figures_dir.iterdir())  # type: ignore[union-attr]
        assert "fig.png" in figures
        assert "fig-1.png" in figures  # dedup'd second copy
