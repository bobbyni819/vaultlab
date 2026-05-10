"""Tests for manual-fetch fallback for paywalled papers.

When the PDF acquisition waterfall fails on a paper Bobby has
institutional browser access to (Springer-Nature, Wiley non-OA), the
system surfaces a copy-paste-ready manual-fetch instruction block
instead of silently marking the paper Tier-C-forever.
"""

from __future__ import annotations

from pathlib import Path

from vaultlab.research.acquisition import (
    AcquisitionResult,
    render_manual_fetch_instructions,
)
from vaultlab.research.paper import Paper


def _failed(
    doi: str,
    *,
    cache_path: Path,
    tried: tuple[str, ...] = ("unpaywall", "pmc", "biorxiv", "springer", "elsevier"),
    errors: dict[str, str] | None = None,
) -> AcquisitionResult:
    return AcquisitionResult(
        doi=doi,
        pdf_path=None,
        source="failed",
        license=None,
        error=f"no source had pdf (tried {', '.join(tried)})",
        tried=tried,
        tier_errors=errors or {"springer": "OA only at meta tier or 403"},
        wall_time_ms=2000,
        publisher_url=f"https://doi.org/{doi}",
        cache_target_path=cache_path,
    )


def _ok(doi: str) -> AcquisitionResult:
    return AcquisitionResult(
        doi=doi,
        pdf_path=Path(f"/tmp/{doi.replace('/', '_')}.pdf"),
        source="unpaywall",
        license="cc-by",
    )


def test_manual_fetch_fields_populated_on_failure(tmp_path: Path):
    """publisher_url + cache_target_path are populated on failed acquisitions."""
    cache_path = tmp_path / "10.1038_nmeth.2869.pdf"
    r = _failed("10.1038/nmeth.2869", cache_path=cache_path)
    assert r.publisher_url == "https://doi.org/10.1038/nmeth.2869"
    assert r.cache_target_path == cache_path


def test_manual_fetch_fields_none_on_success():
    """Successful acquisitions don't carry manual-fetch metadata."""
    r = _ok("10.1016/j.cell.2018.07.010")
    assert r.publisher_url is None
    assert r.cache_target_path is None


def test_render_manual_fetch_returns_empty_when_all_succeeded():
    """No failed acquisitions → empty markdown."""
    results = {
        "10.1/A": _ok("10.1/A"),
        "10.1/B": _ok("10.1/B"),
    }
    out = render_manual_fetch_instructions(results)
    assert out == ""


def test_render_manual_fetch_includes_publisher_url_and_cache_path(
    tmp_path: Path,
):
    """The rendered markdown includes publisher URL + drop path per failed paper."""
    cache_path = tmp_path / "10.1038_nmeth.2869.pdf"
    results = {
        "10.1038/nmeth.2869": _failed("10.1038/nmeth.2869", cache_path=cache_path),
        "10.1/ok": _ok("10.1/ok"),
    }
    out = render_manual_fetch_instructions(results)

    assert "https://doi.org/10.1038/nmeth.2869" in out
    assert str(cache_path) in out
    # The successful paper is NOT in the report
    assert "10.1/ok" not in out
    # Heading is present
    assert "# Papers needing manual download" in out


def test_render_manual_fetch_uses_corpus_paper_metadata(tmp_path: Path):
    """When given corpus_papers, includes title + journal in the report."""
    cache_path = tmp_path / "10.1038_nmeth.2869.pdf"
    paper = Paper(
        title="Highly Multiplexed Imaging by Mass Cytometry",
        year=2014,
        journal="Nature Methods",
        doi="10.1038/nmeth.2869",
    )
    results = {
        "10.1038/nmeth.2869": _failed("10.1038/nmeth.2869", cache_path=cache_path),
    }
    corpus_papers = {"10.1038/nmeth.2869": paper}

    out = render_manual_fetch_instructions(results, corpus_papers=corpus_papers)

    assert "Highly Multiplexed Imaging by Mass Cytometry" in out
    assert "Nature Methods" in out


def test_render_manual_fetch_lists_tier_errors(tmp_path: Path):
    """The 'why each tier failed' summary appears in the markdown."""
    cache_path = tmp_path / "10.1038_nmeth.2869.pdf"
    errors = {
        "unpaywall": "no OA location with url_for_pdf",
        "pmc": "no PMCID for DOI",
        "springer": "OA only at meta tier or 403",
    }
    results = {
        "10.1038/nmeth.2869": _failed("10.1038/nmeth.2869", cache_path=cache_path, errors=errors),
    }
    out = render_manual_fetch_instructions(results)

    assert "unpaywall=no OA location" in out
    assert "pmc=no PMCID for DOI" in out
    assert "springer=OA only at meta tier" in out


def test_render_manual_fetch_includes_how_to_fetch_section(tmp_path: Path):
    """The closing 'How to fetch' section gives the user concrete steps."""
    cache_path = tmp_path / "10.1/X.pdf"
    results = {"10.1/X": _failed("10.1/X", cache_path=cache_path)}
    out = render_manual_fetch_instructions(results)
    assert "## How to fetch" in out
    assert "Duke VPN" in out
    assert "Re-run `/lit-arc`" in out
