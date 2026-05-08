"""Tests for vaultlab.kb.dossier (SPEC-N).

Covers compilation against fake KB layouts, freshness gating, archiving
of prior dossiers, and per-section source extraction.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from vaultlab.kb.dossier import (
    Dossier,
    DossierSection,
    DossierStateUnreadable,
    compile_dossier,
    dossier_age_hours,
    dossier_archive_dir,
    dossier_path,
    load_dossier,
)


@pytest.fixture
def fake_kb(tmp_path: Path) -> Path:
    """Build a minimal fake KB layout."""
    kb = tmp_path / "kb"
    proj = kb / "Wiki" / "Projects" / "test-project"
    proj.mkdir(parents=True)

    (proj / "START_HERE.md").write_text(
        "# START HERE — test-project\n\n"
        "## 2026-05-08 (Friday)\n\n"
        "### Open items\n"
        "- 🔴 Replicate the SM enrichment finding in second cohort\n"
        "- 🟡 Audit the Pentimalli journal-club deck\n\n"
        "### Done today\n"
        "- ✅ Built SPEC-B\n",
        encoding="utf-8",
    )
    (proj / "decisions-log.md").write_text(
        "# Decisions\n\n"
        "## [2026-05-01] decision | Use Spearman over Pearson\n"
        "Per round-8 discussion, Spearman handles non-linear better.\n\n"
        "## [2026-05-03] decision | FDR via BH per Pentimalli\n",
        encoding="utf-8",
    )
    (proj / "intake.md").write_text(
        "## Topic\n\nLipidomics in IBD\n\n"
        "## Goal\n\nIdentify lipid-class axes in muscularis layer\n",
        encoding="utf-8",
    )

    # A few Tier-A summaries
    summaries = kb / "Wiki" / "Summaries"
    summaries.mkdir(parents=True)
    (summaries / "10.1016_j.cels.2025.101261.md").write_text(
        "# Pentimalli 2025\n\nLipid-class axis correlates with cell-type density.\n",
        encoding="utf-8",
    )
    (summaries / "10.1126_science.aar7042.md").write_text(
        "# Schurch 2020\n\nSpatial neighborhood templates in colorectal CRC.\n",
        encoding="utf-8",
    )

    # A concept doc
    concepts = kb / "Wiki" / "Concepts"
    concepts.mkdir(parents=True)
    (concepts / "phospholipid-sphingolipid-axis.md").write_text(
        "# Phospholipid-Sphingolipid Axis\n\n"
        "Long-chain SMs accumulate in muscularis layer in n=4 donors.\n",
        encoding="utf-8",
    )

    # An output report
    reports = kb / "Output" / "test-project" / "Reports"
    reports.mkdir(parents=True)
    (reports / "expert-reviewer-audit-pentimalli-2026-05-08.md").write_text(
        '# Audit\n\n```json\n{"expert_questions": ["Have you replicated?", '
        '"What is the FDR power at n=4?"]}\n```\n',
        encoding="utf-8",
    )
    (reports / "methods-critic-audit-2026-05-07.md").write_text(
        "# Methods Critic Audit\n\nSee report.\n", encoding="utf-8"
    )

    # A grill doc
    notes = kb / "Sources" / "Notes"
    notes.mkdir(parents=True)
    (notes / "grill-frontier-2026-05-08.md").write_text(
        "Open question: is the SM enrichment driven by donor-3?\n",
        encoding="utf-8",
    )

    # A sibling project (for cross-project section)
    sib = kb / "Wiki" / "Projects" / "spatial-tx"
    sib.mkdir(parents=True)
    (sib / "START_HERE.md").write_text("# Spatial TX project\n", encoding="utf-8")

    return kb


def test_compile_dossier_creates_file(fake_kb: Path) -> None:
    """compile_dossier writes the canonical file to disk."""
    dossier = compile_dossier(fake_kb, "test-project")
    assert isinstance(dossier, Dossier)
    target = dossier_path(fake_kb, "test-project")
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    # Frontmatter + heading
    assert "title: Project Dossier — test-project" in text
    assert "# Project Dossier — test-project" in text


def test_compile_dossier_has_nine_sections(fake_kb: Path) -> None:
    """All 9 canonical sections are produced."""
    dossier = compile_dossier(fake_kb, "test-project")
    assert len(dossier.sections) == 9
    expected_slugs = [
        "origin",
        "current_state",
        "methodology_commitments",
        "established_findings",
        "frontier",
        "literature",
        "cross_project",
        "anticipated_questions",
        "recent_tail",
    ]
    actual_slugs = [s.slug for s in dossier.sections]
    assert actual_slugs == expected_slugs


def test_compile_dossier_origin_pulls_intake(fake_kb: Path) -> None:
    """Section 1 (origin) reads intake.md."""
    dossier = compile_dossier(fake_kb, "test-project")
    origin = dossier.sections[0]
    assert origin.slug == "origin"
    assert "muscularis" in origin.body or "Lipidomics" in origin.body


def test_compile_dossier_methodology_pulls_decisions(fake_kb: Path) -> None:
    """Section 3 (methodology) reads decisions-log.md."""
    dossier = compile_dossier(fake_kb, "test-project")
    methods = dossier.sections[2]
    assert methods.slug == "methodology_commitments"
    assert "Spearman" in methods.body
    assert "Pentimalli" in methods.body


def test_compile_dossier_literature_pulls_summaries(fake_kb: Path) -> None:
    """Section 6 (literature) lists Tier-A summaries."""
    dossier = compile_dossier(fake_kb, "test-project")
    lit = dossier.sections[5]
    assert lit.slug == "literature"
    # Wikilinks to the two summary files
    assert "10.1016_j.cels.2025.101261" in lit.body
    assert "10.1126_science.aar7042" in lit.body


def test_compile_dossier_anticipated_pulls_expert_questions(
    fake_kb: Path,
) -> None:
    """Section 8 (anticipated questions) extracts from expert-reviewer audit JSON."""
    dossier = compile_dossier(fake_kb, "test-project")
    anticipated = dossier.sections[7]
    assert anticipated.slug == "anticipated_questions"
    # Should pick up the JSON-embedded questions
    assert "replicated" in anticipated.body.lower()
    assert "FDR" in anticipated.body or "n=4" in anticipated.body


def test_compile_dossier_cross_project_lists_siblings(fake_kb: Path) -> None:
    """Section 7 (cross-project) finds sibling projects."""
    dossier = compile_dossier(fake_kb, "test-project")
    cross = dossier.sections[6]
    assert cross.slug == "cross_project"
    assert "spatial-tx" in cross.body


def test_compile_dossier_missing_project_raises(tmp_path: Path) -> None:
    """Project folder missing → DossierStateUnreadable."""
    kb = tmp_path / "empty-kb"
    (kb / "Wiki" / "Projects").mkdir(parents=True)
    with pytest.raises(DossierStateUnreadable, match="Project folder missing"):
        compile_dossier(kb, "no-such-project")


def test_freshness_skip_when_recent(fake_kb: Path) -> None:
    """If dossier is fresh (<24h), don't recompile by default."""
    dossier1 = compile_dossier(fake_kb, "test-project")
    target = dossier_path(fake_kb, "test-project")
    first_mtime = target.stat().st_mtime

    # Re-compile without force; should skip
    dossier2 = compile_dossier(fake_kb, "test-project")
    second_mtime = target.stat().st_mtime

    # File mtime didn't change = no rewrite
    assert second_mtime == first_mtime
    # Returns a Dossier (loaded from disk, with single "raw" section)
    assert dossier2.sections[0].slug == "raw"


def test_freshness_force_recompile(fake_kb: Path) -> None:
    """force=True overrides the freshness check."""
    compile_dossier(fake_kb, "test-project")
    target = dossier_path(fake_kb, "test-project")
    initial_size = target.stat().st_size

    # Force recompile
    dossier = compile_dossier(fake_kb, "test-project", force=True)
    # Got a real Dossier (not a "raw" one-section degenerate)
    assert len(dossier.sections) == 9
    # Archive directory now has the prior version
    archive = dossier_archive_dir(fake_kb, "test-project")
    assert archive.exists()
    archived_files = list(archive.glob("*.md"))
    assert len(archived_files) >= 1


def test_dossier_age_hours_returns_none_if_absent(tmp_path: Path) -> None:
    """dossier_age_hours returns None when no dossier exists."""
    kb = tmp_path / "kb"
    (kb / "Wiki" / "Projects" / "x").mkdir(parents=True)
    age = dossier_age_hours(kb, "x")
    assert age is None


def test_dossier_age_hours_returns_float_when_present(fake_kb: Path) -> None:
    """dossier_age_hours returns float when dossier exists."""
    compile_dossier(fake_kb, "test-project")
    age = dossier_age_hours(fake_kb, "test-project")
    assert isinstance(age, float)
    assert 0 <= age < 1.0  # just compiled, age < 1h


def test_load_dossier_returns_text(fake_kb: Path) -> None:
    """load_dossier returns the markdown text after compilation."""
    compile_dossier(fake_kb, "test-project")
    text = load_dossier(fake_kb, "test-project")
    assert "Project Dossier — test-project" in text


def test_load_dossier_returns_empty_if_absent(tmp_path: Path) -> None:
    """load_dossier returns empty string when dossier doesn't exist."""
    kb = tmp_path / "kb"
    (kb / "Wiki" / "Projects" / "x").mkdir(parents=True)
    text = load_dossier(kb, "x")
    assert text == ""


def test_render_includes_sources_footer(fake_kb: Path) -> None:
    """Rendered dossier includes a Sources footer."""
    dossier = compile_dossier(fake_kb, "test-project", force=True)
    rendered = dossier.render()
    assert "## Sources" in rendered
    assert "decisions-log.md" in rendered
    assert "START_HERE.md" in rendered


def test_dossier_path_canonical_location(tmp_path: Path) -> None:
    """dossier_path resolves to Wiki/Projects/<slug>/Project-Dossier.md."""
    kb = tmp_path / "kb"
    expected = kb / "Wiki" / "Projects" / "my-project" / "Project-Dossier.md"
    assert dossier_path(kb, "my-project") == expected


def test_dossier_handles_messy_slug(tmp_path: Path) -> None:
    """Messy project names get slugified."""
    kb = tmp_path / "kb"
    proj_with_spaces = kb / "Wiki" / "Projects" / "my-cool-project"
    proj_with_spaces.mkdir(parents=True)
    (proj_with_spaces / "START_HERE.md").write_text("# x\n", encoding="utf-8")

    dossier = compile_dossier(kb, "My Cool Project")
    target = dossier_path(kb, "My Cool Project")
    assert target.exists()
    assert "my-cool-project" in str(target)
