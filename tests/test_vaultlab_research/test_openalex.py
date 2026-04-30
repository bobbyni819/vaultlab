"""Unit tests for vaultlab.research.sources.openalex.

These don't hit the live OpenAlex API — they exercise the parsing logic
on canned response payloads. Author backfill integration is covered in
``test_corpus.py::test_backfill_chain_*``.
"""

from __future__ import annotations

from unittest.mock import patch

from vaultlab.research.sources.openalex import (
    OpenAlexClient,
    _normalize_author_name,
    _reconstruct_abstract,
)


# ---------------------------------------------------------------------------
# Author parsing
# ---------------------------------------------------------------------------


def test_parse_authorships_normalizes_to_last_first_initial():
    client = OpenAlexClient()
    authorships = [
        {"author": {"display_name": "Mikhail Binnewies"}},
        {"author": {"display_name": "Edward W. Roberts"}},
        {"author": {"display_name": "Kelly Kersten"}},
    ]
    out = client._parse_authorships(authorships)
    assert out == ["Binnewies M", "Roberts E", "Kersten K"]


def test_parse_authorships_skips_empty_display_name():
    client = OpenAlexClient()
    authorships = [
        {"author": {"display_name": ""}},
        {"author": {"display_name": "Jane Smith"}},
        {"author": None},
        {},
    ]
    out = client._parse_authorships(authorships)
    assert out == ["Smith J"]


def test_normalize_author_name_handles_single_token():
    """Consortia / acronyms come through as a single token; pass through."""
    assert _normalize_author_name("ENCODE") == "ENCODE"


def test_normalize_author_name_drops_middle_tokens():
    """We only care about Last + first-initial; middle initials dropped."""
    assert _normalize_author_name("John Q Public") == "Public J"


def test_normalize_author_name_handles_empty_string():
    assert _normalize_author_name("") == ""
    assert _normalize_author_name("   ") == ""


# ---------------------------------------------------------------------------
# Abstract reconstruction
# ---------------------------------------------------------------------------


def test_reconstruct_abstract_inverts_index():
    """OpenAlex returns abstracts as ``{word: [pos]}``; reverse the map."""
    inverted = {
        "We": [0],
        "show": [1],
        "that": [2],
        "T": [3, 5],
        "cells": [4],
        "infiltrate": [6],
    }
    out = _reconstruct_abstract(inverted)
    assert out == "We show that T cells T infiltrate"


def test_reconstruct_abstract_empty_returns_empty():
    assert _reconstruct_abstract(None) == ""
    assert _reconstruct_abstract({}) == ""


def test_reconstruct_abstract_skips_non_int_positions():
    """Defensive: bad positions shouldn't crash."""
    out = _reconstruct_abstract({"foo": ["not-an-int"], "bar": [0]})
    assert out == "bar"


# ---------------------------------------------------------------------------
# resolve_doi end-to-end (mocked HTTP)
# ---------------------------------------------------------------------------


def test_resolve_doi_returns_paper_with_authors():
    client = OpenAlexClient()
    fake = {
        "doi": "https://doi.org/10.1038/test",
        "title": "A test paper",
        "publication_year": 2022,
        "host_venue": {"display_name": "Test Journal"},
        "authorships": [
            {"author": {"display_name": "First Author"}},
            {"author": {"display_name": "Second Author"}},
        ],
        "cited_by_count": 42,
    }
    with patch.object(OpenAlexClient, "_get", return_value=fake):
        paper = client.resolve_doi("10.1038/test")

    assert paper is not None
    assert paper.doi == "10.1038/test"
    assert paper.title == "A test paper"
    assert paper.year == 2022
    assert paper.journal == "Test Journal"
    assert paper.citation_count == 42
    assert paper.authors == ["Author F", "Author S"]
    assert paper.source_api == "openalex"


def test_resolve_doi_returns_none_on_404():
    client = OpenAlexClient()
    with patch.object(OpenAlexClient, "_get", return_value=None):
        assert client.resolve_doi("10.9999/missing") is None


def test_resolve_doi_returns_none_on_empty_input():
    client = OpenAlexClient()
    assert client.resolve_doi("") is None
    assert client.resolve_doi("   ") is None


def test_get_authors_by_doi_returns_just_the_list():
    client = OpenAlexClient()
    fake = {
        "doi": "https://doi.org/10.1/x",
        "title": "X",
        "authorships": [
            {"author": {"display_name": "Solo Author"}},
        ],
    }
    with patch.object(OpenAlexClient, "_get", return_value=fake):
        authors = client.get_authors_by_doi("10.1/x")
    assert authors == ["Author S"]


def test_get_authors_by_doi_returns_none_when_paper_has_no_authors():
    """If OpenAlex knows the work but the authorships list is empty, we
    shouldn't return an empty list (the caller would think backfill
    succeeded). Return None so the next chain entry takes over."""
    client = OpenAlexClient()
    fake = {
        "doi": "https://doi.org/10.1/x",
        "title": "X",
        "authorships": [],
    }
    with patch.object(OpenAlexClient, "_get", return_value=fake):
        authors = client.get_authors_by_doi("10.1/x")
    assert authors is None
