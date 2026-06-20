"""Tests for deriving DAS source-data prose from coverage manifests."""

from __future__ import annotations

from pathlib import Path

from vaultlab.figures.publication.coverage import CoverageManifest
from vaultlab.manuscript.data_availability import (
    data_sources_from_coverage,
    merge_into_das,
)


def _write_manifest(
    coverage_dir: Path,
    name: str,
    *,
    figure_id: str,
    source_data: list[str],
    source_data_sha256: dict[str, str] | None = None,
) -> None:
    CoverageManifest(
        figure_id=figure_id,
        script_path=f"scripts/{figure_id}.py",
        source_data=source_data,
        source_data_sha256=source_data_sha256,
    ).to_json(coverage_dir / f"{name}.coverage.json")


def test_data_sources_from_coverage_dedupes_shared_sources(tmp_path: Path) -> None:
    coverage_dir = tmp_path / "coverage"
    shared_hash = "a" * 64
    unique_hash = "b" * 64
    _write_manifest(
        coverage_dir,
        "fig1",
        figure_id="Figure 1",
        source_data=["data/source-counts.csv", "data/fig1-only.csv"],
        source_data_sha256={
            "data/source-counts.csv": shared_hash,
            "data/fig1-only.csv": unique_hash,
        },
    )
    _write_manifest(
        coverage_dir,
        "fig2",
        figure_id="Figure 2",
        source_data=["data/source-counts.csv"],
        source_data_sha256={"data/source-counts.csv": shared_hash},
    )
    _write_manifest(
        coverage_dir,
        "fig3",
        figure_id="Figure 3",
        source_data=["GSE123456"],
    )

    sources = data_sources_from_coverage(coverage_dir)

    assert sources.n_manifests == 3
    assert sources.n_figures == 3
    assert [source.source_file for source in sources.sources] == [
        "GSE123456",
        "data/fig1-only.csv",
        "data/source-counts.csv",
    ]
    shared = sources.sources[2]
    assert shared.figure_ids == ["Figure 1", "Figure 2"]
    assert shared.sha256 == shared_hash
    markdown = sources.to_markdown()
    assert "| source_file | figures | sha256[:8] |" in markdown
    assert "| data/source-counts.csv | Figure 1, Figure 2 | aaaaaaaa |" in markdown


def test_to_das_draft_mentions_figures_files_and_local_deposit_todo(tmp_path: Path) -> None:
    coverage_dir = tmp_path / "coverage"
    _write_manifest(
        coverage_dir,
        "fig1",
        figure_id="Figure 1",
        source_data=["data/source-counts.csv"],
    )
    _write_manifest(
        coverage_dir,
        "fig2",
        figure_id="Figure 2",
        source_data=["GSE123456"],
    )

    draft = data_sources_from_coverage(coverage_dir).to_das_draft()

    assert (
        "The source data underlying Figure(s) Figure 1 are provided in `data/source-counts.csv`."
        in draft
    )
    assert "The source data underlying Figure(s) Figure 2 are provided in `GSE123456`." in draft
    assert "accession-based deposit" in draft


def test_merge_into_das_appends_coverage_lines_without_duplicates(tmp_path: Path) -> None:
    coverage_dir = tmp_path / "coverage"
    _write_manifest(
        coverage_dir,
        "fig1",
        figure_id="Figure 1",
        source_data=["data/source-counts.csv"],
    )
    sources = data_sources_from_coverage(coverage_dir)
    existing = "RNA-seq data are deposited at GEO under accession GSE123456."

    merged_once = merge_into_das(existing, sources)
    merged_twice = merge_into_das(merged_once, sources)

    expected_line = (
        "The source data underlying Figure(s) Figure 1 are provided in `data/source-counts.csv`."
    )
    assert expected_line in merged_once
    assert merged_twice.count(expected_line) == 1


def test_to_das_draft_flags_conflicting_hashes(tmp_path: Path) -> None:
    coverage_dir = tmp_path / "coverage"
    first_hash = "c" * 64
    second_hash = "d" * 64
    _write_manifest(
        coverage_dir,
        "fig1",
        figure_id="Figure 1",
        source_data=["data/source-counts.csv"],
        source_data_sha256={"data/source-counts.csv": first_hash},
    )
    _write_manifest(
        coverage_dir,
        "fig2",
        figure_id="Figure 2",
        source_data=["data/source-counts.csv"],
        source_data_sha256={"data/source-counts.csv": second_hash},
    )

    sources = data_sources_from_coverage(coverage_dir)

    assert sources.sources[0].sha256 == first_hash
    assert sources.to_dict()["sha256_conflicts"] == {
        "data/source-counts.csv": [first_hash, second_hash]
    }
    draft = sources.to_das_draft()
    assert "conflicting SHA-256 values" in draft
    assert first_hash in draft
    assert second_hash in draft


def test_data_sources_from_coverage_missing_dir_returns_empty(tmp_path: Path) -> None:
    sources = data_sources_from_coverage(tmp_path / "does-not-exist")

    assert sources.n_manifests == 0
    assert sources.n_figures == 0
    assert sources.sources == []
    assert sources.to_markdown() == "| source_file | figures | sha256[:8] |\n|---|---|---|"
    assert sources.to_das_draft() == ""


def test_data_sources_from_coverage_skips_bad_sidecar(tmp_path: Path) -> None:
    coverage_dir = tmp_path / "coverage"
    coverage_dir.mkdir()
    (coverage_dir / "bad.coverage.json").write_text("{not json", encoding="utf-8")
    _write_manifest(
        coverage_dir,
        "fig1",
        figure_id="Figure 1",
        source_data=["data/source-counts.csv"],
    )

    sources = data_sources_from_coverage(coverage_dir)

    assert sources.n_manifests == 1
    assert sources.n_figures == 1
    assert [source.source_file for source in sources.sources] == ["data/source-counts.csv"]
