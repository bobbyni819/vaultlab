"""Tests for vaultlab.research.abstract_recall.get_abstract_for_doi.

Coverage:
* (a) Paper found with non-empty abstract  -> returns abstract string.
* (b) Paper found but abstract is empty    -> returns None.
* (c) get_paper returns None               -> returns None.
* (d) Empty DOI string                     -> returns None, get_paper never called.

Because ``abstract_recall`` imports ``get_paper`` lazily inside the function body
(to avoid circular imports at package initialisation), ``patch`` cannot find it as a
pre-existing attribute of the abstract_recall module.  We therefore patch it at its
real home — ``vaultlab.research.get_paper`` — which is the object the lazy
``from vaultlab.research import get_paper`` binds at call time.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from vaultlab.research.abstract_recall import get_abstract_for_doi
from vaultlab.research.paper import Paper

# The lazy import inside abstract_recall resolves to vaultlab.research.get_paper,
# so that is the target we patch.
_PATCH_TARGET = "vaultlab.research.get_paper"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _paper_with_abstract(abstract: str) -> Paper:
    return Paper(
        title="A Test Paper",
        doi="10.1/test",
        abstract=abstract,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetAbstractForDoi:
    """Unit tests for get_abstract_for_doi."""

    def test_returns_abstract_when_paper_found(self):
        """(a) Paper found with non-empty abstract -> abstract string returned."""
        expected = "Spatial transcriptomics reveals cell-type-specific organization."
        paper = _paper_with_abstract(expected)

        with patch(_PATCH_TARGET, return_value=paper) as mock_get_paper:
            result = get_abstract_for_doi("10.1038/s41586-023-05915-x")

        assert result == expected
        mock_get_paper.assert_called_once_with("10.1038/s41586-023-05915-x")

    def test_returns_none_when_abstract_empty(self):
        """(b) Paper found but abstract field is empty string -> None."""
        paper = _paper_with_abstract("")

        with patch(_PATCH_TARGET, return_value=paper) as mock_get_paper:
            result = get_abstract_for_doi("10.1/abstract-empty")

        assert result is None
        mock_get_paper.assert_called_once_with("10.1/abstract-empty")

    def test_returns_none_when_get_paper_returns_none(self):
        """(c) get_paper returns None (paper not found) -> None."""
        with patch(_PATCH_TARGET, return_value=None) as mock_get_paper:
            result = get_abstract_for_doi("10.1/not-in-any-db")

        assert result is None
        mock_get_paper.assert_called_once_with("10.1/not-in-any-db")

    def test_empty_doi_returns_none_without_calling_get_paper(self):
        """(d) Empty DOI -> None immediately, get_paper never called."""
        with patch(_PATCH_TARGET) as mock_get_paper:
            result = get_abstract_for_doi("")

        assert result is None
        mock_get_paper.assert_not_called()
