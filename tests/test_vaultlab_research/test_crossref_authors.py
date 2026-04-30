"""Unit tests for CrossRef author parsing and per-DOI lookup.

These cover the gap-fix where consortium / group / literal authors were
silently dropped, leading to ``authors: []`` in summary frontmatter.
"""

from __future__ import annotations

from unittest.mock import patch

from vaultlab.research.sources.crossref import CrossRefClient


# ---------------------------------------------------------------------------
# Author parsing — covers the literal/name fallthrough fix
# ---------------------------------------------------------------------------


def test_parse_authors_personal_author():
    client = CrossRefClient()
    out = client._parse_authors(
        [{"family": "Smith", "given": "Jane"}, {"family": "Doe", "given": "John A"}]
    )
    assert out == ["Smith J", "Doe J"]


def test_parse_authors_handles_consortium_name_field():
    """CrossRef's consortium/group authors come in as ``{"name": "..."}``
    instead of ``{"family": ..., "given": ...}``. Without the fix, these
    were silently dropped — empty author list."""
    client = CrossRefClient()
    out = client._parse_authors(
        [
            {"name": "ENCODE Project Consortium"},
            {"family": "Smith", "given": "Jane"},
        ]
    )
    assert out == ["ENCODE Project Consortium", "Smith J"]


def test_parse_authors_handles_literal_field():
    """Older / imported CrossRef records use ``{"literal": "..."}`` for
    pre-personal-name authorship. Without the fix, these were dropped."""
    client = CrossRefClient()
    out = client._parse_authors([{"literal": "Working Group on Foo"}])
    assert out == ["Working Group on Foo"]


def test_parse_authors_skips_empty_dicts():
    client = CrossRefClient()
    out = client._parse_authors([{}, {"family": "Smith", "given": "Jane"}, {}])
    assert out == ["Smith J"]


def test_parse_authors_handles_non_dict_entries():
    """Defensive: malformed entries shouldn't crash."""
    client = CrossRefClient()
    out = client._parse_authors(
        ["bogus string", None, {"family": "Smith", "given": "Jane"}]
    )
    assert out == ["Smith J"]


def test_parse_authors_family_only_or_given_only():
    client = CrossRefClient()
    out = client._parse_authors(
        [{"family": "Smith"}, {"given": "Jane"}]
    )
    assert out == ["Smith", "Jane"]


# ---------------------------------------------------------------------------
# get_authors_by_doi — used by the backfill chain
# ---------------------------------------------------------------------------


def test_get_authors_by_doi_returns_list_when_resolve_succeeds():
    client = CrossRefClient()
    fake_message = {
        "DOI": "10.1/test",
        "title": ["A test"],
        "author": [
            {"family": "Smith", "given": "Jane"},
            {"family": "Doe", "given": "John"},
        ],
        "issued": {"date-parts": [[2020]]},
    }
    with patch.object(CrossRefClient, "_get", return_value=fake_message):
        authors = client.get_authors_by_doi("10.1/test")
    assert authors == ["Smith J", "Doe J"]


def test_get_authors_by_doi_returns_none_on_404():
    client = CrossRefClient()
    with patch.object(CrossRefClient, "_get", return_value=None):
        assert client.get_authors_by_doi("10.9/missing") is None


def test_get_authors_by_doi_returns_none_when_authors_empty():
    """Differentiates 'CrossRef has the paper with no authors' from 'has
    authors' — chain should fall through if authors list is empty."""
    client = CrossRefClient()
    fake_message = {
        "DOI": "10.1/test",
        "title": ["No authors"],
        "author": [],
    }
    with patch.object(CrossRefClient, "_get", return_value=fake_message):
        assert client.get_authors_by_doi("10.1/test") is None
