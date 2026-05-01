"""Regression tests for the author-name → wikilink-label helper.

The bug: OpenAlex returns "J. Kennedy-Darling" (initial-first format)
where the naive ``authors[0].split()[0]`` picked ``"J."`` instead of
``"Kennedy-Darling"``. This produced ``[[10.x_y|J. 2020]]`` wikilinks
in the regenerated CODEX arc when those authors had been backfilled
from OpenAlex (236 papers in evening-4).

These tests pin :func:`vaultlab.kb.paths.format_author_lastname` and
its public wrapper :func:`vaultlab.kb.paths.author_year_label` so the
fix sticks.
"""

from __future__ import annotations

import pytest

from vaultlab.kb.paths import author_year_label, format_author_lastname


class TestFormatAuthorLastname:
    def test_handles_initial_first_format(self) -> None:
        """OpenAlex / CrossRef return initial-first."""
        assert format_author_lastname("J. Kennedy-Darling") == "Kennedy-Darling"
        assert format_author_lastname("S. Bhate") == "Bhate"
        assert format_author_lastname("J. Hickey") == "Hickey"

    def test_handles_last_first_format(self) -> None:
        """NCBI / S2 short form: ``Last F`` / ``Last FM``."""
        assert format_author_lastname("Goltsev Y") == "Goltsev"
        assert format_author_lastname("Smith JX") == "Smith"
        assert format_author_lastname("Hickey JW") == "Hickey"

    def test_handles_short_surname_in_last_first_format(self) -> None:
        """NCBI ``Li C`` should resolve to ``Li`` (first token is the
        surname, last token is the initial). Pre-evening-5 the heuristic
        flipped these because both tokens were short.
        """
        assert format_author_lastname("Li C") == "Li"
        assert format_author_lastname("Wu Q") == "Wu"
        assert format_author_lastname("Ng K") == "Ng"

    def test_handles_full_first_last(self) -> None:
        """Western full names, no comma, no initials in either position."""
        assert format_author_lastname("Sarah Black") == "Black"
        assert format_author_lastname("First Middle Last") == "Last"

    def test_handles_vancouver_last_comma_first(self) -> None:
        """CSL-JSON / Vancouver: surname before the comma."""
        assert format_author_lastname("Kennedy-Darling, J.") == "Kennedy-Darling"
        assert format_author_lastname("Smith, J X") == "Smith"
        assert format_author_lastname("Last, First") == "Last"

    def test_handles_unicode_hyphen(self) -> None:
        """OpenAlex sometimes emits U+2010 (HYPHEN). Normalize to ASCII."""
        # U+2010 HYPHEN
        assert format_author_lastname("Kennedy‐Darling X") == "Kennedy-Darling"
        # U+2013 EN DASH
        assert format_author_lastname("J. Kennedy–Darling") == "Kennedy-Darling"
        # ASCII hyphen passes through unchanged
        assert format_author_lastname("Kennedy-Darling X") == "Kennedy-Darling"

    def test_handles_single_token(self) -> None:
        """Corp authors / pre-extracted surnames pass through."""
        assert format_author_lastname("ConsortiumX") == "ConsortiumX"
        assert format_author_lastname("Smith") == "Smith"

    def test_handles_empty(self) -> None:
        assert format_author_lastname("") == ""
        assert format_author_lastname("   ") == ""

    def test_handles_initials_with_periods(self) -> None:
        """Multi-initial first name should still skip to the surname."""
        assert format_author_lastname("J.W. Hickey") == "Hickey"
        assert format_author_lastname("J. W. Hickey") == "Hickey"

    def test_handles_generational_suffix(self) -> None:
        """Western-order names with Jr./III/IV trailing suffix."""
        # "Smith Jr." → surname is Smith; suffix is dropped from the tail.
        # We test the initial-first path here since that's where suffixes
        # land in OpenAlex output.
        assert format_author_lastname("J. Smith Jr.") == "Smith"
        assert format_author_lastname("J. Smith III") == "Smith"


class TestAuthorYearLabel:
    def test_renders_kennedy_darling_2020(self) -> None:
        """The exact case Bobby flagged: OpenAlex first author, year present."""
        out = author_year_label(
            ["J. Kennedy-Darling", "S. Bhate", "J. Hickey"],
            2020,
        )
        assert out == "Kennedy-Darling 2020"

    def test_skips_to_first_parseable_author(self) -> None:
        """Empty first author falls through to the next entry."""
        out = author_year_label(["", "Goltsev Y"], 2018)
        assert out == "Goltsev 2018"

    def test_falls_back_to_anon_nd(self) -> None:
        assert author_year_label([], None) == "Anon n.d."
        assert author_year_label([""], None) == "Anon n.d."

    def test_year_only_falls_back_to_anon(self) -> None:
        assert author_year_label([], 2020) == "Anon 2020"

    def test_authors_only_falls_back_to_nd(self) -> None:
        assert author_year_label(["Goltsev Y"], None) == "Goltsev n.d."


class TestEndToEndCallsites:
    """Regression: every wikilink-rendering callsite picks up the fix.

    Each sub-test instantiates the relevant rendering helper with a
    PaperSummary / candidate that has OpenAlex-style authors and asserts
    the rendered label uses the surname, not the initial.
    """

    def test_lineage_author_year_label(self) -> None:
        from vaultlab.research.lineage import _author_year_label
        from vaultlab.research.summarize import PaperSummary

        s = PaperSummary(
            doi="10.1002/eji.202048891",
            authors=["J. Kennedy-Darling", "S. Bhate", "J. Hickey"],
            year=2020,
        )
        assert _author_year_label(s) == "Kennedy-Darling 2020"

    def test_lineage_project_view_label(self) -> None:
        from vaultlab.research.lineage import _project_view_label
        from vaultlab.research.summarize import PaperSummary

        s = PaperSummary(
            doi="10.1/x",
            authors=["A. Black"],
            year=2022,
        )
        assert _project_view_label(s) == "Black 2022"

    def test_deck_format_author_lastname_shim(self) -> None:
        """The deck.py shim now delegates to the central helper."""
        from vaultlab.slides.deck import _format_author_lastname

        assert _format_author_lastname("J. Kennedy-Darling") == "Kennedy-Darling"
        # Old NCBI form still works.
        assert _format_author_lastname("Goltsev Y") == "Goltsev"

    def test_deck_plan_summary_label(self) -> None:
        from vaultlab.workflows.deck_plan import _author_year_label_from_dict

        out = _author_year_label_from_dict(
            {"authors": ["J. Kennedy-Darling"], "year": 2020}
        )
        assert out == "Kennedy-Darling 2020"
