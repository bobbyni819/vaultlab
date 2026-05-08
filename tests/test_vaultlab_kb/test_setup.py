"""Tests for vaultlab.kb.setup (SPEC-D — KB scaffolding + lint)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from vaultlab.kb.setup import (
    CANONICAL_FOLDERS,
    DOMAIN_EXTENSIONS,
    LintFinding,
    LintReport,
    ScaffoldError,
    lint_kb,
    scaffold_kb,
)


def test_scaffold_creates_canonical_folders(tmp_path: Path) -> None:
    """All 11 canonical folders are created."""
    proj_dir = scaffold_kb(tmp_path, "test-project")
    assert proj_dir == tmp_path / "test-project"
    for folder in CANONICAL_FOLDERS:
        assert (proj_dir / folder).is_dir(), f"missing folder {folder}"


def test_scaffold_creates_top_level_files(tmp_path: Path) -> None:
    """START_HERE / _Index / _Catalog / _Log are created."""
    proj_dir = scaffold_kb(tmp_path, "test-project")
    for filename in ("START_HERE.md", "_Index.md", "_Catalog.md", "_Log.md"):
        assert (proj_dir / filename).is_file()


def test_scaffold_start_here_includes_maintenance_rules(tmp_path: Path) -> None:
    """START_HERE template embeds the 7 maintenance rules."""
    proj_dir = scaffold_kb(tmp_path, "test-project")
    text = (proj_dir / "START_HERE.md").read_text(encoding="utf-8")
    # Verify the canonical 7 rules are embedded
    assert "Maintenance rules" in text
    assert "1. **On every session**" in text
    assert "Newest day must make sense cold" in text
    # Today's date section
    assert "📅" in text
    # Status emoji legend
    assert "🟡" in text
    assert "🟢" in text


def test_scaffold_log_includes_setup_entry(tmp_path: Path) -> None:
    """_Log.md is initialized with a setup entry."""
    proj_dir = scaffold_kb(tmp_path, "test-project")
    log_text = (proj_dir / "_Log.md").read_text(encoding="utf-8")
    assert "setup | KB scaffolded" in log_text


def test_scaffold_slugifies_messy_name(tmp_path: Path) -> None:
    """Project name with spaces / caps gets slugified."""
    proj_dir = scaffold_kb(tmp_path, "My Cool Project")
    assert proj_dir.name == "my-cool-project"


def test_scaffold_refuses_existing_without_force(tmp_path: Path) -> None:
    """Scaffolding over existing folder raises ScaffoldError."""
    scaffold_kb(tmp_path, "test-project")
    with pytest.raises(ScaffoldError, match="already exists"):
        scaffold_kb(tmp_path, "test-project")


def test_scaffold_force_fills_missing_pieces(tmp_path: Path) -> None:
    """force=True fills in missing folders without disturbing existing files."""
    scaffold_kb(tmp_path, "test-project")
    proj_dir = tmp_path / "test-project"
    # Delete one canonical folder
    import shutil
    shutil.rmtree(proj_dir / "Wiki" / "Concepts")
    assert not (proj_dir / "Wiki" / "Concepts").exists()

    # Modify START_HERE so we can verify it's preserved
    (proj_dir / "START_HERE.md").write_text(
        "MY CUSTOM CONTENT", encoding="utf-8"
    )

    scaffold_kb(tmp_path, "test-project", force=True)
    assert (proj_dir / "Wiki" / "Concepts").is_dir()  # filled in
    # Existing file preserved
    assert (proj_dir / "START_HERE.md").read_text(encoding="utf-8") == "MY CUSTOM CONTENT"


def test_scaffold_with_domain_extension(tmp_path: Path) -> None:
    """Domain extensions add their declared folders."""
    proj_dir = scaffold_kb(
        tmp_path, "stocks", domain_extensions=["equities"]
    )
    for folder in DOMAIN_EXTENSIONS["equities"]:
        assert (proj_dir / folder).is_dir(), f"missing extension folder {folder}"


def test_scaffold_unknown_domain_extension_raises(tmp_path: Path) -> None:
    """Unknown extension key raises ScaffoldError."""
    with pytest.raises(ScaffoldError, match="Unknown domain_extension"):
        scaffold_kb(
            tmp_path, "test", domain_extensions=["nonexistent-extension"]
        )


def test_lint_clean_scaffold_reports_no_findings(tmp_path: Path) -> None:
    """A fresh scaffold lints clean."""
    scaffold_kb(tmp_path, "test-project")
    report = lint_kb(tmp_path, "test-project")
    assert isinstance(report, LintReport)
    assert report.passed
    assert report.shippable
    assert report.summary["fail"] == 0


def test_lint_detects_missing_folder(tmp_path: Path) -> None:
    """A KB missing a canonical folder gets a warn finding."""
    proj_dir = scaffold_kb(tmp_path, "test-project")
    # Delete a folder
    import shutil
    shutil.rmtree(proj_dir / "Wiki" / "Methodology")

    report = lint_kb(tmp_path, "test-project")
    assert not report.passed
    missing_folder_findings = [
        f for f in report.findings if f.kind == "missing_folder"
    ]
    assert len(missing_folder_findings) >= 1


def test_lint_detects_missing_start_here(tmp_path: Path) -> None:
    """Missing START_HERE.md is severity=fail."""
    proj_dir = scaffold_kb(tmp_path, "test-project")
    (proj_dir / "START_HERE.md").unlink()

    report = lint_kb(tmp_path, "test-project")
    fails = [f for f in report.findings if f.severity == "fail"]
    assert any("START_HERE.md" in str(f.path) for f in fails)
    assert not report.shippable


def test_lint_detects_naming_violation(tmp_path: Path) -> None:
    """Articles not matching AuthorYearTitle convention surface as info."""
    proj_dir = scaffold_kb(tmp_path, "test-project")
    # Create a misnamed article
    (proj_dir / "Sources" / "Articles" / "random_thing.md").write_text(
        "# Random\n", encoding="utf-8"
    )

    report = lint_kb(tmp_path, "test-project")
    naming_findings = [
        f for f in report.findings if f.kind == "naming_violation"
    ]
    assert len(naming_findings) >= 1
    assert all(f.severity == "info" for f in naming_findings)


def test_lint_accepts_canonical_naming(tmp_path: Path) -> None:
    """AuthorYearTitle-shape filenames pass the naming check."""
    proj_dir = scaffold_kb(tmp_path, "test-project")
    (proj_dir / "Sources" / "Articles" / "Pentimalli_2025_lipid-axis.md").write_text(
        "# Pentimalli 2025\n", encoding="utf-8"
    )

    report = lint_kb(tmp_path, "test-project")
    naming_findings = [
        f for f in report.findings if f.kind == "naming_violation"
    ]
    assert len(naming_findings) == 0


def test_lint_missing_project_folder_is_fail(tmp_path: Path) -> None:
    """Auditing a non-existent project folder is severity=fail."""
    report = lint_kb(tmp_path, "no-such-project")
    assert not report.shippable
    fails = [f for f in report.findings if f.severity == "fail"]
    assert any(f.kind == "missing_folder" for f in fails)


def test_lint_render_markdown_includes_all_severities(tmp_path: Path) -> None:
    """render_markdown produces a structured audit doc."""
    proj_dir = scaffold_kb(tmp_path, "test-project")
    (proj_dir / "Sources" / "Articles" / "bad_name.md").write_text("# x\n", encoding="utf-8")

    report = lint_kb(tmp_path, "test-project")
    rendered = report.render_markdown()
    assert "KB lint — test-project" in rendered
    assert "Summary:" in rendered
    assert "INFO" in rendered or "WARN" in rendered or "FAIL" in rendered


def test_lint_summary_counts_severities(tmp_path: Path) -> None:
    """summary attribute counts findings by severity."""
    proj_dir = scaffold_kb(tmp_path, "test-project")
    # Trigger multiple findings
    (proj_dir / "START_HERE.md").unlink()  # fail
    import shutil
    shutil.rmtree(proj_dir / "Sources" / "Notes")  # warn
    (proj_dir / "Sources" / "Articles" / "bad_name.md").write_text("# x\n", encoding="utf-8")  # info

    report = lint_kb(tmp_path, "test-project")
    summary = report.summary
    assert summary["fail"] >= 1
    assert summary["warn"] >= 1
    assert summary["info"] >= 1


def test_scaffold_idempotent_under_force(tmp_path: Path) -> None:
    """force=True called twice is a no-op (no errors, no changes)."""
    scaffold_kb(tmp_path, "test-project")
    proj_dir = tmp_path / "test-project"
    initial_files = sorted(p.name for p in proj_dir.iterdir())

    scaffold_kb(tmp_path, "test-project", force=True)
    second_files = sorted(p.name for p in proj_dir.iterdir())
    assert initial_files == second_files
