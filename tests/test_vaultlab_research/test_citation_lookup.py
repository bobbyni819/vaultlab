"""Unit tests for vaultlab.research.citation_lookup.

All HTTP traffic is mocked. The captured response payloads below are
miniaturized but structurally faithful to what CrossRef and Semantic
Scholar actually return (verified against live API on 2026-04-29).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from vaultlab.research.citation_lookup import (
    USER_AGENT,
    RateLimitError,
    Reference,
    _parse_crossref_reference,
    _parse_s2_paper_as_reference,
    get_citations_via_s2,
    get_influential_count_via_s2,
    get_references_via_crossref,
)

# ---------------------------------------------------------------------------
# Reference parsing
# ---------------------------------------------------------------------------


class TestParseCrossrefReference:
    def test_full_reference(self):
        raw = {
            "key": "ref1",
            "DOI": "10.1126/SCIENCE.1225829",
            "article-title": "Programmable nucleases",
            "year": "2012",
            "author": "Jinek",
        }
        ref = _parse_crossref_reference(raw)
        assert ref.doi == "10.1126/science.1225829"
        assert ref.title == "Programmable nucleases"
        assert ref.year == 2012
        assert ref.authors == ["Jinek"]

    def test_missing_doi_yields_empty_string(self):
        raw = {"year": "2010", "author": "Doe"}
        ref = _parse_crossref_reference(raw)
        assert ref.doi == ""
        assert ref.year == 2010

    def test_falls_back_to_volume_title(self):
        raw = {"DOI": "10.1/x", "volume-title": "Vol Title", "year": "2000"}
        ref = _parse_crossref_reference(raw)
        assert ref.title == "Vol Title"

    def test_year_garbage_becomes_zero(self):
        raw = {"DOI": "10.1/x", "year": "n/d"}
        ref = _parse_crossref_reference(raw)
        assert ref.year == 0

    def test_missing_author(self):
        raw = {"DOI": "10.1/x", "year": "2020"}
        ref = _parse_crossref_reference(raw)
        assert ref.authors == []


class TestParseS2Reference:
    def test_full_paper(self):
        raw = {
            "title": "Foo",
            "year": 2020,
            "venue": "Nature",
            "externalIds": {"DOI": "10.1/A"},
            "authors": [{"name": "Smith J"}, {"name": "Doe A"}],
        }
        ref = _parse_s2_paper_as_reference(raw)
        assert ref.doi == "10.1/a"
        assert ref.title == "Foo"
        assert ref.year == 2020
        assert ref.authors == ["Smith J", "Doe A"]

    def test_missing_external_ids(self):
        raw = {"title": "Foo", "year": 2020}
        ref = _parse_s2_paper_as_reference(raw)
        assert ref.doi == ""


# ---------------------------------------------------------------------------
# get_references_via_crossref — mocks
# ---------------------------------------------------------------------------


def _mock_response(status_code: int, json_body=None, headers=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.json.return_value = json_body if json_body is not None else {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(f"{status_code}")
    else:
        resp.raise_for_status.return_value = None
    return resp


CROSSREF_OK_BODY = {
    "status": "ok",
    "message": {
        "DOI": "10.1126/science.1225829",
        "title": ["A Programmable Dual-RNA-Guided DNA Endonuclease"],
        "reference": [
            {
                "key": "r1",
                "DOI": "10.1038/nature09886",
                "article-title": "RNA-guided immunity",
                "year": "2011",
                "author": "Wiedenheft",
            },
            {
                "key": "r2",
                "DOI": "10.1126/science.1138140",
                "article-title": "CRISPR provides acquired resistance",
                "year": "2007",
                "author": "Barrangou",
            },
            # A reference with no DOI (should still parse, doi == "")
            {"key": "r3", "article-title": "No-DOI ref", "year": "1998"},
        ],
    },
}


class TestGetReferencesViaCrossref:
    def test_blank_doi_returns_none(self):
        assert get_references_via_crossref("") is None
        assert get_references_via_crossref("   ") is None

    def test_happy_path(self):
        with patch(
            "vaultlab.research.citation_lookup.requests.get",
            return_value=_mock_response(200, CROSSREF_OK_BODY),
        ) as mock_get:
            refs = get_references_via_crossref("10.1126/science.1225829")
        assert refs is not None
        assert len(refs) == 3
        assert refs[0].doi == "10.1038/nature09886"
        assert refs[0].year == 2011
        assert refs[2].doi == ""  # no-DOI ref preserved

        # Polite User-Agent
        _, kwargs = mock_get.call_args
        assert kwargs["headers"]["User-Agent"] == USER_AGENT
        assert "10.1126/science.1225829" in mock_get.call_args[0][0]

    def test_404_returns_none(self):
        with patch(
            "vaultlab.research.citation_lookup.requests.get",
            return_value=_mock_response(404),
        ):
            refs = get_references_via_crossref("10.invalid/doi")
        assert refs is None

    def test_429_raises_rate_limit(self):
        with patch(
            "vaultlab.research.citation_lookup.requests.get",
            return_value=_mock_response(429, headers={"Retry-After": "5"}),
        ):
            with pytest.raises(RateLimitError) as excinfo:
                get_references_via_crossref("10.1/x")
        assert excinfo.value.source == "crossref"
        assert excinfo.value.retry_after == 5.0

    def test_no_reference_array_returns_none(self):
        body = {"status": "ok", "message": {"DOI": "10.1/x"}}
        with patch(
            "vaultlab.research.citation_lookup.requests.get",
            return_value=_mock_response(200, body),
        ):
            refs = get_references_via_crossref("10.1/x")
        assert refs is None

    def test_network_error_returns_none(self):
        with patch(
            "vaultlab.research.citation_lookup.requests.get",
            side_effect=requests.ConnectionError("boom"),
        ):
            refs = get_references_via_crossref("10.1/x")
        assert refs is None


# ---------------------------------------------------------------------------
# get_citations_via_s2
# ---------------------------------------------------------------------------


S2_CITATIONS_BODY = {
    "data": [
        {
            "citingPaper": {
                "title": "Citer A",
                "year": 2023,
                "externalIds": {"DOI": "10.1/A"},
                "authors": [{"name": "Alpha B"}],
            }
        },
        {
            "citingPaper": {
                "title": "Citer B",
                "year": 2024,
                "externalIds": {"DOI": "10.2/B"},
                "authors": [],
            }
        },
        {"citingPaper": {}},  # malformed entry — must be skipped
    ]
}


class TestGetCitationsViaS2:
    def test_blank_doi(self):
        assert get_citations_via_s2("") == []

    def test_happy_path(self):
        with patch(
            "vaultlab.research.citation_lookup.requests.get",
            return_value=_mock_response(200, S2_CITATIONS_BODY),
        ) as mock_get:
            refs = get_citations_via_s2("10.1126/science.1225829", api_key="secret")
        assert len(refs) == 2
        assert refs[0].doi == "10.1/a"
        assert refs[0].year == 2023
        assert refs[1].title == "Citer B"

        _, kwargs = mock_get.call_args
        assert kwargs["headers"]["x-api-key"] == "secret"
        assert kwargs["headers"]["User-Agent"] == USER_AGENT

    def test_404_returns_empty(self):
        with patch(
            "vaultlab.research.citation_lookup.requests.get",
            return_value=_mock_response(404),
        ):
            refs = get_citations_via_s2("10.1/x")
        assert refs == []

    def test_429_raises(self):
        with patch(
            "vaultlab.research.citation_lookup.requests.get",
            return_value=_mock_response(429),
        ):
            with pytest.raises(RateLimitError) as exc:
                get_citations_via_s2("10.1/x")
        assert exc.value.source == "semantic_scholar"


# ---------------------------------------------------------------------------
# get_influential_count_via_s2
# ---------------------------------------------------------------------------


class TestGetInfluentialCountViaS2:
    def test_returns_tuple(self):
        body = {"citationCount": 13_037, "influentialCitationCount": 1_847}
        with patch(
            "vaultlab.research.citation_lookup.requests.get",
            return_value=_mock_response(200, body),
        ):
            result = get_influential_count_via_s2("10.1126/science.1225829")
        assert result == (13_037, 1_847)

    def test_404_returns_none(self):
        with patch(
            "vaultlab.research.citation_lookup.requests.get",
            return_value=_mock_response(404),
        ):
            assert get_influential_count_via_s2("10.invalid/x") is None

    def test_blank_doi(self):
        assert get_influential_count_via_s2("") is None

    def test_missing_fields_default_to_zero(self):
        with patch(
            "vaultlab.research.citation_lookup.requests.get",
            return_value=_mock_response(200, {}),
        ):
            assert get_influential_count_via_s2("10.1/x") == (0, 0)


# ---------------------------------------------------------------------------
# Reference dataclass smoke test
# ---------------------------------------------------------------------------


def test_reference_to_dict_round_trip():
    ref = Reference(doi="10.1/x", title="T", year=2020, authors=["A"])
    d = ref.to_dict()
    assert d == {"doi": "10.1/x", "title": "T", "year": 2020, "authors": ["A"]}
