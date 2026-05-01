"""Tests for Elsevier-cluster (Scopus) search integration.

Note: ScienceDirect Search at ``/content/search/sciencedirect`` is *not*
supported with our current API key tier (returns 401 AUTHORIZATION_ERROR).
Scopus Search at ``/content/search/scopus`` IS supported and gives broader
cross-publisher coverage. We use Scopus and label the source ``"scopus"``.
"""

from __future__ import annotations

from unittest.mock import patch

from vaultlab.research.paper import Paper
from vaultlab.research.search import unified_search
from vaultlab.research.sources.elsevier import ElsevierClient


# ---------------------------------------------------------------------------
# ElsevierClient.search response parsing (Scopus shape)
# ---------------------------------------------------------------------------


def test_search_returns_empty_list_without_api_key():
    """Search short-circuits cleanly when no key configured."""
    client = ElsevierClient(api_key="")
    assert client.search("anything") == []


def test_search_parses_scopus_response_shape():
    """Verify Paper objects are populated correctly from a Scopus response."""
    fake_response = {
        "search-results": {
            "opensearch:totalResults": "1594",
            "entry": [
                {
                    "prism:doi": "10.1186/s40644-026-01006-y",
                    "dc:title": "Developing an interpretable ML model via SHAP",
                    "prism:coverDate": "2026-12-01",
                    "prism:publicationName": "Cancer Imaging",
                    "dc:creator": "Zou W.",
                    "citedby-count": "0",
                    "pubmed-id": "41691300",
                    "link": [
                        {
                            "@ref": "self",
                            "@href": "https://api.elsevier.com/content/abstract/scopus_id/...",
                        }
                    ],
                },
                {
                    "prism:doi": "10.1016/j.cell.2018.07.010",
                    "dc:title": "Deep Profiling of Mouse Splenic Architecture",
                    "prism:coverDate": "2018-08-09",
                    "prism:publicationName": "Cell",
                    "dc:creator": "Goltsev Y",
                    "citedby-count": "412",
                    "pubmed-id": "30270040",
                },
            ],
        }
    }

    client = ElsevierClient(api_key="fake-key")

    class _FakeResp:
        status_code = 200

        def json(self):
            return fake_response

        def raise_for_status(self):
            pass

    with patch.object(client._session, "get", return_value=_FakeResp()):
        papers = client.search("CODEX multiplexed imaging", max_results=10)

    assert len(papers) == 2

    # First entry — current-year paper, low cite count, has PMID
    assert papers[0].doi == "10.1186/s40644-026-01006-y"
    assert papers[0].title.startswith("Developing an interpretable")
    assert papers[0].year == 2026
    assert papers[0].journal == "Cancer Imaging"
    assert papers[0].authors == ["Zou W."]
    assert papers[0].citation_count == 0
    assert papers[0].pmid == "41691300"
    assert papers[0].source_api == "scopus"

    # Second entry — older paper with real citation count
    assert papers[1].doi == "10.1016/j.cell.2018.07.010"
    assert papers[1].journal == "Cell"
    assert papers[1].citation_count == 412


def test_search_handles_403_authentication_failure():
    """403 response yields empty list, doesn't raise."""
    client = ElsevierClient(api_key="bad-key")

    class _FakeResp:
        status_code = 403

        def json(self):
            return {}

        def raise_for_status(self):
            raise RuntimeError("403")

    with patch.object(client._session, "get", return_value=_FakeResp()):
        assert client.search("anything") == []


def test_search_handles_malformed_response():
    """Missing search-results / entry fields yields empty list."""
    client = ElsevierClient(api_key="fake-key")

    class _FakeResp:
        status_code = 200

        def json(self):
            return {"unexpected": "shape"}

        def raise_for_status(self):
            pass

    with patch.object(client._session, "get", return_value=_FakeResp()):
        assert client.search("anything") == []


def test_search_handles_non_int_citedby_count():
    """If Scopus returns a malformed citedby-count, fall back to 0."""
    client = ElsevierClient(api_key="fake-key")
    fake_response = {
        "search-results": {
            "entry": [
                {
                    "prism:doi": "10.1/X",
                    "dc:title": "T",
                    "prism:coverDate": "2024-01-01",
                    "citedby-count": "not-a-number",
                }
            ]
        }
    }

    class _FakeResp:
        status_code = 200

        def json(self):
            return fake_response

        def raise_for_status(self):
            pass

    with patch.object(client._session, "get", return_value=_FakeResp()):
        papers = client.search("any")
    assert papers[0].citation_count == 0


# ---------------------------------------------------------------------------
# unified_search with Scopus
# ---------------------------------------------------------------------------


class _FakeScopus:
    def __init__(self, papers: list[Paper]):
        self._papers = papers
        self.calls: list[str] = []

    def search(self, query: str, max_results: int = 50) -> list[Paper]:
        self.calls.append(query)
        return list(self._papers)


def test_unified_search_uses_scopus_when_in_default_sources():
    """Default sources list now includes ``scopus``."""
    fake = _FakeScopus(
        [
            Paper(
                title="Goltsev",
                year=2018,
                citation_count=412,
                doi="10.1016/j.cell.2018.07.010",
                source_api="scopus",
            )
        ]
    )
    papers = unified_search(query="CODEX", sciencedirect_client=fake)
    assert fake.calls == ["CODEX"]
    assert any(p.doi == "10.1016/j.cell.2018.07.010" for p in papers)


def test_unified_search_skips_scopus_when_client_is_none():
    """Without a client, the source is silently skipped."""
    papers = unified_search(query="CODEX", sciencedirect_client=None)
    assert papers == []


def test_unified_search_scopus_records_in_trace():
    """The trace's per_source dict reports scopus hits."""
    fake = _FakeScopus(
        [
            Paper(
                doi="10.1/A",
                year=2024,
                citation_count=10,
                source_api="scopus",
            )
        ]
    )
    _papers, trace = unified_search(
        query="any",
        sciencedirect_client=fake,
        return_trace=True,
    )
    assert "scopus" in trace.per_source
    assert trace.per_source["scopus"].hits == 1


def test_unified_search_legacy_elsevier_alias_still_works():
    """Legacy 'elsevier' alias picks up the Scopus client."""
    fake = _FakeScopus(
        [
            Paper(
                doi="10.1/A",
                year=2024,
                citation_count=1,
                source_api="scopus",
            )
        ]
    )
    papers = unified_search(
        query="any",
        sources=["elsevier"],
        sciencedirect_client=fake,
    )
    assert len(papers) == 1


def test_unified_search_legacy_sciencedirect_alias_still_works():
    """Legacy 'sciencedirect' alias picks up the Scopus client."""
    fake = _FakeScopus(
        [
            Paper(
                doi="10.1/A",
                year=2024,
                citation_count=1,
                source_api="scopus",
            )
        ]
    )
    papers = unified_search(
        query="any",
        sources=["sciencedirect"],
        sciencedirect_client=fake,
    )
    assert len(papers) == 1
