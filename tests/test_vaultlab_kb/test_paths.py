"""Tests for vaultlab.kb.paths — canonical KB path routing.

These tests are pure path-shape assertions against a temporary kb_root.
None of the path-builder functions create directories on disk, so the
KB layout is exercised only via ``ensure_parent`` and a few manual writes.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from vaultlab.kb import paths


# ---------------------------------------------------------------------------
# Slugifiers
# ---------------------------------------------------------------------------


class TestSlugifyDoi:
    def test_replaces_slash_with_underscore(self) -> None:
        assert paths.slugify_doi("10.1126/science.1225829") == "10.1126_science.1225829"

    def test_handles_complex_doi(self) -> None:
        assert (
            paths.slugify_doi("10.1038/s41586-023-05915-x")
            == "10.1038_s41586-023-05915-x"
        )

    def test_strips_doi_url_prefix(self) -> None:
        assert (
            paths.slugify_doi("https://doi.org/10.1126/science.1225829")
            == "10.1126_science.1225829"
        )

    def test_strips_doi_colon_prefix(self) -> None:
        assert (
            paths.slugify_doi("doi:10.1126/science.1225829")
            == "10.1126_science.1225829"
        )

    def test_replaces_colon_with_underscore(self) -> None:
        # DOI with colon (rare but valid)
        result = paths.slugify_doi("10.1234/foo:bar")
        assert ":" not in result
        assert result == "10.1234_foo_bar"

    def test_replaces_other_illegal_chars(self) -> None:
        result = paths.slugify_doi("10.1234/a*b?c<d>e|f")
        # Each illegal char run becomes a single underscore.
        assert "*" not in result
        assert "?" not in result
        assert "<" not in result
        assert ">" not in result
        assert "|" not in result

    def test_strips_whitespace(self) -> None:
        assert paths.slugify_doi("  10.1126/science.1225829  ") == "10.1126_science.1225829"

    def test_empty_doi_raises(self) -> None:
        with pytest.raises(ValueError):
            paths.slugify_doi("")

    def test_slugify_doi_idempotent_with_lowercase(self) -> None:
        """Regression for L4 audit bug #4: slugify_doi must lowercase its
        output so summary paths and PDF cache paths agree on slug form
        even when a mixed-case DOI sneaks in from a search engine.
        """
        # Mixed-case and all-lowercase DOIs must produce the same slug.
        assert (
            paths.slugify_doi("10.1126/Science.xyz")
            == paths.slugify_doi("10.1126/science.xyz")
            == "10.1126_science.xyz"
        )
        # Output is always lowercase regardless of input casing.
        assert paths.slugify_doi("10.1038/S41586-023-XYZ") == "10.1038_s41586-023-xyz"
        # Idempotent: applying twice yields the same slug.
        once = paths.slugify_doi("10.1234/Foo:Bar")
        twice = paths.slugify_doi(once)
        assert once == twice == "10.1234_foo_bar"


class TestSlugifyTopic:
    def test_basic_lowercase_kebab(self) -> None:
        assert paths.slugify_topic("CRISPR base editing") == "crispr-base-editing"

    def test_collapses_whitespace(self) -> None:
        assert paths.slugify_topic("  galectin-4  sulfatide  ") == "galectin-4-sulfatide"

    def test_strips_accented_characters(self) -> None:
        assert paths.slugify_topic("Café résumé") == "cafe-resume"

    def test_drops_non_ascii(self) -> None:
        # Greek letters / emoji should be stripped, not transliterated.
        result = paths.slugify_topic("β-catenin signaling")
        assert "β" not in result
        assert "catenin" in result
        assert "signaling" in result

    def test_punctuation_becomes_single_hyphen(self) -> None:
        assert paths.slugify_topic("foo, bar; baz") == "foo-bar-baz"

    def test_trims_leading_trailing_hyphens(self) -> None:
        assert paths.slugify_topic("---hello---") == "hello"

    def test_empty_topic_raises(self) -> None:
        with pytest.raises(ValueError):
            paths.slugify_topic("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError):
            paths.slugify_topic("   ")


# ---------------------------------------------------------------------------
# Sources/
# ---------------------------------------------------------------------------


class TestSourcesPaths:
    def test_pdf_path(self, tmp_path: Path) -> None:
        p = paths.pdf_path(tmp_path, "10.1126/science.1225829")
        assert p == tmp_path / "Sources" / "Papers" / "10.1126_science.1225829.pdf"

    def test_fulltext_md_path(self, tmp_path: Path) -> None:
        p = paths.fulltext_md_path(tmp_path, "10.1126/science.1225829")
        assert p == tmp_path / "Sources" / "Papers" / "10.1126_science.1225829.md"

    def test_article_stub_path(self, tmp_path: Path) -> None:
        p = paths.article_stub_path(tmp_path, "10.1126/science.1225829")
        assert p == tmp_path / "Sources" / "Articles" / "10.1126_science.1225829.md"

    def test_search_log_path_with_explicit_date(self, tmp_path: Path) -> None:
        p = paths.search_log_path(tmp_path, "CRISPR base editing", date_str="2026-04-29")
        assert p == (
            tmp_path
            / "Sources"
            / "Notes"
            / "lit-search-crispr-base-editing-2026-04-29.md"
        )

    def test_search_log_path_defaults_to_today(self, tmp_path: Path) -> None:
        p = paths.search_log_path(tmp_path, "topic")
        today = date.today().strftime("%Y-%m-%d")
        assert p.name == f"lit-search-topic-{today}.md"

    def test_search_log_path_lives_under_sources_notes(self, tmp_path: Path) -> None:
        p = paths.search_log_path(tmp_path, "topic")
        assert p.parent == tmp_path / "Sources" / "Notes"


# ---------------------------------------------------------------------------
# Wiki/
# ---------------------------------------------------------------------------


class TestWikiPaths:
    def test_summary_path(self, tmp_path: Path) -> None:
        p = paths.summary_path(tmp_path, "10.1126/science.1225829")
        assert p == tmp_path / "Wiki" / "Summaries" / "10.1126_science.1225829.md"

    def test_concept_path_default_kind_is_lineage(self, tmp_path: Path) -> None:
        p = paths.concept_path(tmp_path, "CRISPR base editing", date_str="2026-04-29")
        assert p == (
            tmp_path
            / "Wiki"
            / "Concepts"
            / "crispr-base-editing-lineage-2026-04-29.md"
        )

    def test_concept_path_with_custom_kind(self, tmp_path: Path) -> None:
        p = paths.concept_path(
            tmp_path, "CRISPR base editing", kind="methodology", date_str="2026-04-29"
        )
        assert p.name == "crispr-base-editing-methodology-2026-04-29.md"

    def test_concept_path_default_date_is_today(self, tmp_path: Path) -> None:
        p = paths.concept_path(tmp_path, "CRISPR base editing")
        today = date.today().strftime("%Y-%m-%d")
        assert p.name.endswith(f"-{today}.md")

    def test_concept_path_empty_kind_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            paths.concept_path(tmp_path, "topic", kind="")

    def test_project_state_path(self, tmp_path: Path) -> None:
        p = paths.project_state_path(tmp_path, "Codex CN test")
        assert p == tmp_path / "Wiki" / "Projects" / "codex-cn-test" / "START_HERE.md"

    def test_project_decisions_path(self, tmp_path: Path) -> None:
        p = paths.project_decisions_path(tmp_path, "Codex CN test")
        assert (
            p == tmp_path / "Wiki" / "Projects" / "codex-cn-test" / "decisions-log.md"
        )


# ---------------------------------------------------------------------------
# Output/
# ---------------------------------------------------------------------------


class TestOutputPaths:
    def test_project_dir(self, tmp_path: Path) -> None:
        p = paths.project_dir(tmp_path, "Codex CN test")
        assert p == tmp_path / "Output" / "codex-cn-test"

    def test_deck_path_appends_pptx_suffix(self, tmp_path: Path) -> None:
        p = paths.deck_path(tmp_path, "codex-cn-test", "journal-club")
        assert p == tmp_path / "Output" / "codex-cn-test" / "journal-club.pptx"

    def test_deck_path_keeps_existing_suffix(self, tmp_path: Path) -> None:
        p = paths.deck_path(tmp_path, "codex-cn-test", "journal-club.pptx")
        assert p.name == "journal-club.pptx"

    def test_deck_path_empty_name_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            paths.deck_path(tmp_path, "p", "")

    def test_deck_plan_path(self, tmp_path: Path) -> None:
        p = paths.deck_plan_path(tmp_path, "codex-cn-test")
        assert p == tmp_path / "Output" / "codex-cn-test" / "deck_plan.md"

    def test_figure_path_default_png(self, tmp_path: Path) -> None:
        p = paths.figure_path(tmp_path, "codex-cn-test", "fig-1")
        assert p == tmp_path / "Output" / "codex-cn-test" / "figures" / "fig-1.png"

    def test_figure_path_custom_suffix(self, tmp_path: Path) -> None:
        p = paths.figure_path(tmp_path, "codex-cn-test", "fig-1", suffix=".annotated.png")
        assert p.name == "fig-1.annotated.png"

    def test_figure_path_suffix_without_leading_dot(self, tmp_path: Path) -> None:
        p = paths.figure_path(tmp_path, "codex-cn-test", "fig-1", suffix="svg")
        assert p.name == "fig-1.svg"

    def test_figure_path_empty_id_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            paths.figure_path(tmp_path, "p", "")

    def test_evidence_path_appends_suffix(self, tmp_path: Path) -> None:
        p = paths.evidence_path(tmp_path, "codex-cn-test", "manuscript-v2")
        assert p == (
            tmp_path
            / "Output"
            / "codex-cn-test"
            / "citations"
            / "manuscript-v2.evidence.json"
        )

    def test_evidence_path_keeps_existing_suffix(self, tmp_path: Path) -> None:
        p = paths.evidence_path(tmp_path, "codex-cn-test", "manuscript-v2.evidence.json")
        assert p.name == "manuscript-v2.evidence.json"

    def test_evidence_path_empty_slug_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            paths.evidence_path(tmp_path, "p", "")

    def test_run_dir_with_explicit_id(self, tmp_path: Path) -> None:
        p = paths.run_dir(tmp_path, "codex-cn-test", run_id="2026-04-29T10-15-00")
        assert p == (
            tmp_path
            / "Output"
            / "codex-cn-test"
            / "runs"
            / "2026-04-29T10-15-00"
        )

    def test_run_dir_auto_generates_id(self, tmp_path: Path) -> None:
        p = paths.run_dir(tmp_path, "codex-cn-test")
        # Auto-generated IDs contain no path separators or colons.
        run_id = p.name
        assert ":" not in run_id
        assert "/" not in run_id
        assert "\\" not in run_id
        assert "T" in run_id  # ISO 8601-like separator
        assert p.parent == tmp_path / "Output" / "codex-cn-test" / "runs"

    def test_turn_path(self, tmp_path: Path) -> None:
        run = paths.run_dir(tmp_path, "codex-cn-test", run_id="2026-04-29T10-15-00")
        p = paths.turn_path(run, 0, "literature_surveyor")
        assert p == run / "turn-0-literature_surveyor.md"

    def test_turn_path_negative_raises(self, tmp_path: Path) -> None:
        run = paths.run_dir(tmp_path, "p", run_id="r1")
        with pytest.raises(ValueError):
            paths.turn_path(run, -1, "role")

    def test_turn_path_empty_role_raises(self, tmp_path: Path) -> None:
        run = paths.run_dir(tmp_path, "p", run_id="r1")
        with pytest.raises(ValueError):
            paths.turn_path(run, 0, "")

    def test_transcript_path(self, tmp_path: Path) -> None:
        run = paths.run_dir(tmp_path, "codex-cn-test", run_id="2026-04-29T10-15-00")
        p = paths.transcript_path(run)
        assert p == run / "transcript.md"


# ---------------------------------------------------------------------------
# ensure_parent
# ---------------------------------------------------------------------------


class TestEnsureParent:
    def test_creates_missing_parents(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b" / "c" / "file.md"
        assert not target.parent.exists()
        result = paths.ensure_parent(target)
        assert result == target
        assert target.parent.is_dir()

    def test_returns_same_path(self, tmp_path: Path) -> None:
        target = tmp_path / "file.md"
        assert paths.ensure_parent(target) == target

    def test_idempotent(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b" / "file.md"
        paths.ensure_parent(target)
        # Second call should not raise.
        paths.ensure_parent(target)
        assert target.parent.is_dir()

    def test_supports_writing_file_after(self, tmp_path: Path) -> None:
        target = tmp_path / "deep" / "nested" / "file.md"
        paths.ensure_parent(target).write_text("hello")
        assert target.read_text() == "hello"


# ---------------------------------------------------------------------------
# Path-builders DO NOT mkdir on their own
# ---------------------------------------------------------------------------


class TestNoSideEffects:
    """Path-builders must be pure — no directory creation."""

    def test_summary_path_does_not_create_dir(self, tmp_path: Path) -> None:
        paths.summary_path(tmp_path, "10.1/x")
        assert not (tmp_path / "Wiki").exists()

    def test_run_dir_does_not_create_dir(self, tmp_path: Path) -> None:
        paths.run_dir(tmp_path, "p", run_id="r1")
        assert not (tmp_path / "Output").exists()

    def test_deck_path_does_not_create_dir(self, tmp_path: Path) -> None:
        paths.deck_path(tmp_path, "p", "deck")
        assert not (tmp_path / "Output").exists()


# ---------------------------------------------------------------------------
# Returns Path, not str
# ---------------------------------------------------------------------------


class TestReturnTypes:
    def test_all_helpers_return_path_objects(self, tmp_path: Path) -> None:
        run = paths.run_dir(tmp_path, "p", run_id="r1")
        assert isinstance(paths.pdf_path(tmp_path, "10.1/x"), Path)
        assert isinstance(paths.fulltext_md_path(tmp_path, "10.1/x"), Path)
        assert isinstance(paths.article_stub_path(tmp_path, "10.1/x"), Path)
        assert isinstance(paths.search_log_path(tmp_path, "q"), Path)
        assert isinstance(paths.summary_path(tmp_path, "10.1/x"), Path)
        assert isinstance(paths.concept_path(tmp_path, "t"), Path)
        assert isinstance(paths.project_state_path(tmp_path, "p"), Path)
        assert isinstance(paths.project_decisions_path(tmp_path, "p"), Path)
        assert isinstance(paths.project_dir(tmp_path, "p"), Path)
        assert isinstance(paths.deck_path(tmp_path, "p", "d"), Path)
        assert isinstance(paths.deck_plan_path(tmp_path, "p"), Path)
        assert isinstance(paths.figure_path(tmp_path, "p", "f"), Path)
        assert isinstance(paths.evidence_path(tmp_path, "p", "f"), Path)
        assert isinstance(run, Path)
        assert isinstance(paths.turn_path(run, 0, "role"), Path)
        assert isinstance(paths.transcript_path(run), Path)
