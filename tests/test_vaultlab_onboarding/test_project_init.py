"""Tests for vaultlab.onboarding.project_init — folder scan + orchestrator."""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.onboarding.config import PROJECT_CONFIG_FILENAME, load_config
from vaultlab.onboarding.intake import IntakeForm, render_intake_template
from vaultlab.onboarding.project_init import (
    FolderInventory,
    ProjectInit,
    init_project_from_intake,
    scan_project_folder,
)

# ---------------------------------------------------------------------------
# scan_project_folder
# ---------------------------------------------------------------------------


class TestScanProjectFolder:
    def test_empty_folder(self, tmp_path: Path) -> None:
        inv = scan_project_folder(tmp_path)
        assert isinstance(inv, FolderInventory)
        assert inv.total_files == 0
        assert inv.counts == {}
        assert inv.has_readme is False
        assert inv.has_claude_md is False

    def test_classifies_python_files(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("# hi", encoding="utf-8")
        (tmp_path / "utils.py").write_text("# hi", encoding="utf-8")
        inv = scan_project_folder(tmp_path)
        assert inv.counts.get("python") == 2

    def test_classifies_mixed_types(self, tmp_path: Path) -> None:
        (tmp_path / "analysis.py").write_text("", encoding="utf-8")
        (tmp_path / "exploration.ipynb").write_text("{}", encoding="utf-8")
        (tmp_path / "data.h5ad").write_bytes(b"")
        (tmp_path / "paper.pdf").write_bytes(b"")
        (tmp_path / "draft.docx").write_bytes(b"")
        inv = scan_project_folder(tmp_path)
        assert inv.counts.get("python") == 1
        assert inv.counts.get("notebook") == 1
        assert inv.counts.get("data_anndata") == 1
        assert inv.counts.get("paper") == 1
        assert inv.counts.get("manuscript") == 1
        assert inv.total_files == 5

    def test_skips_dot_dirs(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("ref", encoding="utf-8")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "main.cpython-313.pyc").write_bytes(b"")
        (tmp_path / "real.py").write_text("", encoding="utf-8")
        inv = scan_project_folder(tmp_path)
        assert inv.counts.get("python") == 1  # only real.py, not the .pyc

    def test_detects_readme(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# Hi", encoding="utf-8")
        inv = scan_project_folder(tmp_path)
        assert inv.has_readme is True

    def test_detects_claude_md(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("# Hi", encoding="utf-8")
        inv = scan_project_folder(tmp_path)
        assert inv.has_claude_md is True

    def test_detects_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        inv = scan_project_folder(tmp_path)
        assert inv.has_pyproject is True

    def test_recursive_walk(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.py").write_text("", encoding="utf-8")
        (tmp_path / "src" / "subpkg").mkdir()
        (tmp_path / "src" / "subpkg" / "b.py").write_text("", encoding="utf-8")
        inv = scan_project_folder(tmp_path)
        assert inv.counts.get("python") == 2

    def test_samples_capped_at_five(self, tmp_path: Path) -> None:
        for i in range(20):
            (tmp_path / f"f{i}.py").write_text("", encoding="utf-8")
        inv = scan_project_folder(tmp_path)
        assert len(inv.samples["python"]) == 5

    def test_missing_folder_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            scan_project_folder(tmp_path / "nope")

    def test_file_path_raises_not_a_dir(self, tmp_path: Path) -> None:
        f = tmp_path / "x.txt"
        f.write_text("", encoding="utf-8")
        with pytest.raises(NotADirectoryError):
            scan_project_folder(f)


# ---------------------------------------------------------------------------
# init_project_from_intake — full orchestrator
# ---------------------------------------------------------------------------


class TestInitProjectFromIntake:
    def _setup(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        """Create a project folder + KB + filled intake. Returns (project, kb, intake)."""
        project_path = tmp_path / "my_project"
        project_path.mkdir()
        kb_root = tmp_path / "kb"
        kb_root.mkdir()

        # Add some content to the project folder
        (project_path / "README.md").write_text("# my project", encoding="utf-8")
        (project_path / "analysis.py").write_text("", encoding="utf-8")
        (project_path / "data").mkdir()
        (project_path / "data" / "raw.csv").write_text("a,b\n1,2", encoding="utf-8")

        # Build a filled intake
        form = IntakeForm(
            topic="Spatial transcriptomics in PDAC",
            goals=["understand_literature"],
            audiences=["self"],
            have=["wet_lab_data"],
            exclusions={"exclude_preprints": True},
            style=["hedged"],
            pi_preferences="John likes author-year",
            deadlines=["weekly"],
            free_form="Side project for thesis aim 3",
        )
        intake_p = project_path / "project_intake.md"
        intake_p.write_text(form.to_markdown(), encoding="utf-8")

        return project_path, kb_root, intake_p

    def test_returns_project_init_view(self, tmp_path: Path) -> None:
        project_path, kb_root, intake_p = self._setup(tmp_path)
        result = init_project_from_intake(intake_p, kb_root, project_path)
        assert isinstance(result, ProjectInit)

    def test_slug_derived_from_topic(self, tmp_path: Path) -> None:
        project_path, kb_root, intake_p = self._setup(tmp_path)
        result = init_project_from_intake(intake_p, kb_root, project_path)
        assert result.slug == "spatial-transcriptomics-in-pdac"

    def test_explicit_slug_override(self, tmp_path: Path) -> None:
        project_path, kb_root, intake_p = self._setup(tmp_path)
        result = init_project_from_intake(intake_p, kb_root, project_path, slug="custom-slug")
        assert result.slug == "custom-slug"

    def test_writes_start_here(self, tmp_path: Path) -> None:
        project_path, kb_root, intake_p = self._setup(tmp_path)
        result = init_project_from_intake(intake_p, kb_root, project_path)
        assert result.start_here_path is not None
        assert result.start_here_path.exists()
        body = result.start_here_path.read_text(encoding="utf-8")
        assert "# START_HERE — spatial-transcriptomics-in-pdac" in body
        assert "Spatial transcriptomics in PDAC" in body

    def test_writes_intake_kb_copy(self, tmp_path: Path) -> None:
        project_path, kb_root, intake_p = self._setup(tmp_path)
        result = init_project_from_intake(intake_p, kb_root, project_path)
        assert result.intake_kb_copy_path is not None
        assert result.intake_kb_copy_path.exists()
        assert result.intake_kb_copy_path.name == "intake.md"

    def test_writes_decisions_log(self, tmp_path: Path) -> None:
        project_path, kb_root, intake_p = self._setup(tmp_path)
        result = init_project_from_intake(intake_p, kb_root, project_path)
        assert result.decisions_log_path is not None
        assert result.decisions_log_path.exists()
        body = result.decisions_log_path.read_text(encoding="utf-8")
        assert "Project onboarded" in body
        assert "Spatial transcriptomics in PDAC" in body

    def test_writes_project_config(self, tmp_path: Path) -> None:
        project_path, kb_root, intake_p = self._setup(tmp_path)
        result = init_project_from_intake(intake_p, kb_root, project_path)
        assert result.project_config_path is not None
        assert result.project_config_path.exists()
        assert result.project_config_path.name == PROJECT_CONFIG_FILENAME

    def test_config_round_trips(self, tmp_path: Path) -> None:
        project_path, kb_root, intake_p = self._setup(tmp_path)
        result = init_project_from_intake(intake_p, kb_root, project_path)
        loaded = load_config(project_path)
        assert loaded is not None
        assert loaded.slug == result.slug
        assert loaded.topic == "Spatial transcriptomics in PDAC"
        assert "understand_literature" in loaded.goal
        assert "self" in loaded.audience

    def test_files_written_returns_four_paths(self, tmp_path: Path) -> None:
        project_path, kb_root, intake_p = self._setup(tmp_path)
        result = init_project_from_intake(intake_p, kb_root, project_path)
        assert len(result.files_written()) == 4

    def test_inventory_attached(self, tmp_path: Path) -> None:
        project_path, kb_root, intake_p = self._setup(tmp_path)
        result = init_project_from_intake(intake_p, kb_root, project_path)
        assert result.inventory.has_readme is True
        assert result.inventory.counts.get("python") == 1
        assert result.inventory.counts.get("data_tabular") == 1

    def test_follow_up_questions_present(self, tmp_path: Path) -> None:
        project_path, kb_root, intake_p = self._setup(tmp_path)
        result = init_project_from_intake(intake_p, kb_root, project_path)
        assert 1 <= len(result.follow_up_questions) <= 5

    def test_empty_template_blocks_init(self, tmp_path: Path) -> None:
        """An unfilled template should fail validation before writing."""
        from vaultlab.onboarding.intake import IntakeValidationError

        project_path = tmp_path / "p"
        project_path.mkdir()
        kb_root = tmp_path / "kb"
        kb_root.mkdir()
        intake_p = project_path / "project_intake.md"
        intake_p.write_text(render_intake_template(), encoding="utf-8")
        with pytest.raises(IntakeValidationError):
            init_project_from_intake(intake_p, kb_root, project_path)

    def test_data_dirs_collected(self, tmp_path: Path) -> None:
        project_path, kb_root, intake_p = self._setup(tmp_path)
        result = init_project_from_intake(intake_p, kb_root, project_path)
        # data/raw.csv → data dir should be collected
        assert any("data" in d.lower() for d in result.config.data_dirs)


class TestFollowUpHeuristics:
    """The composer should ask gap-targeted questions, not generic ones."""

    def _make(
        self,
        *,
        topic: str = "X",
        goals: list[str] | None = None,
        audiences: list[str] | None = None,
        have: list[str] | None = None,
        exclusions: dict | None = None,
        pi_preferences: str = "",
        free_form: str = "",
    ) -> tuple[Path, Path, Path]:
        return goals, audiences, have, exclusions, pi_preferences, free_form  # type: ignore[return-value]

    def test_asks_about_pi_when_pi_audience_no_prefs(self, tmp_path: Path) -> None:
        project_path = tmp_path / "p"
        project_path.mkdir()
        kb = tmp_path / "kb"
        kb.mkdir()
        form = IntakeForm(
            topic="X",
            goals=["understand_literature"],
            audiences=["pi"],
        )
        intake_p = project_path / "project_intake.md"
        intake_p.write_text(form.to_markdown(), encoding="utf-8")
        result = init_project_from_intake(intake_p, kb, project_path)
        assert any("PI" in q for q in result.follow_up_questions)

    def test_asks_for_data_path_when_wet_lab_ticked_but_no_data_files(self, tmp_path: Path) -> None:
        project_path = tmp_path / "p"
        project_path.mkdir()
        kb = tmp_path / "kb"
        kb.mkdir()
        form = IntakeForm(
            topic="X",
            goals=["understand_literature"],
            audiences=["self"],
            have=["wet_lab_data"],
        )
        intake_p = project_path / "project_intake.md"
        intake_p.write_text(form.to_markdown(), encoding="utf-8")
        result = init_project_from_intake(intake_p, kb, project_path)
        assert any("Wet-lab" in q or "data" in q.lower() for q in result.follow_up_questions)
