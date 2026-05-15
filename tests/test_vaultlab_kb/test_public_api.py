"""Public-API surface tests for vaultlab.kb (SPEC-D — sub-goal 2.3).

The north-star plan calls out the short ergonomic names
(``vaultlab.kb.setup`` / ``vaultlab.kb.lint`` / ``LintIssue``) as the
public primitive surface. The canonical names (``scaffold_kb`` /
``lint_kb`` / ``LintFinding``) carry the full SPEC-D semantics. These
tests enforce that BOTH names exist and resolve to the same object so
neither contract drifts.
"""

from __future__ import annotations

from pathlib import Path


def test_kb_namespace_exports_canonical_setup_surface() -> None:
    """SPEC-D names are exported from vaultlab.kb at the package level."""
    import vaultlab.kb as kb

    # Canonical names
    assert hasattr(kb, "scaffold_kb")
    assert hasattr(kb, "lint_kb")
    assert hasattr(kb, "LintReport")
    assert hasattr(kb, "LintFinding")
    assert hasattr(kb, "ScaffoldError")


def test_kb_namespace_exports_short_aliases() -> None:
    """Short aliases (setup / lint / LintIssue) are exported and usable."""
    import vaultlab.kb as kb

    assert hasattr(kb, "setup")
    assert hasattr(kb, "lint")
    assert hasattr(kb, "LintIssue")


def test_aliases_point_to_canonical_objects() -> None:
    """``setup is scaffold_kb`` etc. — single source of truth, no drift."""
    import vaultlab.kb as kb

    assert kb.setup is kb.scaffold_kb
    assert kb.lint is kb.lint_kb
    assert kb.LintIssue is kb.LintFinding


def test_setup_alias_scaffolds_kb(tmp_path: Path) -> None:
    """Calling ``vaultlab.kb.setup`` scaffolds an identical tree to scaffold_kb."""
    from vaultlab.kb import setup

    proj_dir = setup(tmp_path, "alias-project")
    assert proj_dir.is_dir()
    # Canonical folders + files present
    assert (proj_dir / "Sources" / "Articles").is_dir()
    assert (proj_dir / "Wiki" / "Concepts").is_dir()
    assert (proj_dir / "Output" / "Plans").is_dir()
    assert (proj_dir / "START_HERE.md").is_file()
    assert (proj_dir / "_Index.md").is_file()


def test_lint_alias_returns_lintreport(tmp_path: Path) -> None:
    """Calling ``vaultlab.kb.lint`` returns a LintReport on a fresh scaffold."""
    from vaultlab.kb import LintReport, lint, setup

    setup(tmp_path, "alias-project")
    report = lint(tmp_path, "alias-project")
    assert isinstance(report, LintReport)
    assert report.shippable
    assert report.summary == {"fail": 0, "warn": 0, "info": 0}


def test_lintissue_alias_matches_lintfinding(tmp_path: Path) -> None:
    """``LintIssue`` aliases ``LintFinding`` — findings are instances of both."""
    from vaultlab.kb import LintFinding, LintIssue, lint, setup

    proj_dir = setup(tmp_path, "alias-project")
    (proj_dir / "START_HERE.md").unlink()
    report = lint(tmp_path, "alias-project")
    assert len(report.findings) >= 1
    for finding in report.findings:
        assert isinstance(finding, LintFinding)
        assert isinstance(finding, LintIssue)  # same class
