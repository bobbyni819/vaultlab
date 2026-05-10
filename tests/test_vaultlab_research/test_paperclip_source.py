"""Tests for vaultlab.research.sources.paperclip — parser and client API."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vaultlab.research.sources.paperclip import (
    PaperclipClient,
    PaperclipUnavailable,
    _parse_authors_line,
    _parse_search_output,
)

# ---------- Real paperclip search-output fixtures -------------------------

# Fixture #1: 3-result block from a real demo run on
# "spatial proteomics CODEX multiscale tissue computational"
SEARCH_OUTPUT_3 = """\
Found 15 papers  [s_06817faa]

  1. An ultrasensitive spatial tissue proteomics workflow exceeding 100 proteomes per day
     Melissa Klingeberg, Christoph Krisp, Sonja Fritzsche, Simon Schallenberg, Daniel Hornburg, Fabian Co...
     bio_3ac44def6d63 · bioRxiv · 2025-06-02
     https://doi.org/10.1101/2025.06.02.657389
     "A workflow for spatial tissue proteomics was developed and optimized."

  2. Highly multiplexed spatial profiling with CODEX: bioinformatic analysis and application in human disease
     Wilson Kuswanto, Garry Nolan, Guolan Lu
     PMC9684921 · PMC · 2022-11-21
     https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9684921/
     "CODEX technology was used for highly multiplexed spatial profiling of cells within tissues."

  3. AI-powered virtual tissues from spatial proteomics for clinical diagnostics
     Johann Wenckstern, Eeshaan Jain, Yexiang Cheng, Benedikt von Querfurth, Kiril Vasilev, Matteo Parise...
     arx_2501.06039 · arXiv · 2025-01-10
     "This study developed a foundation model called VirTues."
"""

# Fixture #2: result with no DOI URL line and no abstract (minimum block)
SEARCH_OUTPUT_MINIMAL = """\
Found 1 papers  [s_minimal]

  1. Some paper without optional fields
     One Author, Two Author
     PMC1234567 · PMC · 2023-05-01
"""

# Fixture #3: result with non-doi URL (PMC URL) instead of DOI
SEARCH_OUTPUT_PMC_URL = """\
Found 1 papers  [s_pmc]

  1. PMC paper with non-DOI URL
     Author Author
     PMC9876543 · PMC · 2024-01-01
     https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9876543/
     "Abstract text here."
"""


def test_parse_three_results():
    papers = _parse_search_output(SEARCH_OUTPUT_3)
    assert len(papers) == 3

    p1, p2, p3 = papers

    assert p1.title.startswith("An ultrasensitive spatial tissue proteomics workflow")
    assert p1.authors[0] == "Melissa Klingeberg"
    assert "Christoph Krisp" in p1.authors
    assert p1.year == 2025
    assert p1.journal == "bioRxiv"
    assert p1.doi == "10.1101/2025.06.02.657389"
    assert "spatial tissue proteomics" in p1.abstract.lower()
    assert p1.source_api == "paperclip"

    assert p2.title.startswith("Highly multiplexed spatial profiling with CODEX")
    assert p2.authors == ["Wilson Kuswanto", "Garry Nolan", "Guolan Lu"]
    assert p2.year == 2022
    assert p2.journal == "PMC"
    assert p2.doi == ""  # PMC URL is not a DOI URL
    # url field captures the PMC link even though doi is empty
    assert "ncbi.nlm.nih.gov/pmc" in p2.url

    assert p3.title.startswith("AI-powered virtual tissues from spatial proteomics")
    assert p3.year == 2025
    assert p3.journal == "arXiv"
    assert p3.doi == ""  # arxiv id not a doi
    assert "VirTues" in p3.abstract


def test_parse_minimal_block():
    """No URL, no abstract — minimum required fields still parse."""
    papers = _parse_search_output(SEARCH_OUTPUT_MINIMAL)
    assert len(papers) == 1
    p = papers[0]
    assert p.title == "Some paper without optional fields"
    assert p.authors == ["One Author", "Two Author"]
    assert p.year == 2023
    assert p.journal == "PMC"
    assert p.doi == ""
    assert p.abstract == ""
    assert p.url == ""


def test_parse_pmc_url():
    papers = _parse_search_output(SEARCH_OUTPUT_PMC_URL)
    assert len(papers) == 1
    p = papers[0]
    assert p.url.startswith("https://www.ncbi.nlm.nih.gov")
    assert p.doi == ""  # PMC URL is not a doi.org URL
    assert "Abstract text here" in p.abstract


def test_parse_authors_line_truncated():
    out = _parse_authors_line("Smith J, Doe A, Roe B...")
    assert out == ["Smith J", "Doe A", "Roe B"]


def test_parse_authors_line_no_truncation():
    out = _parse_authors_line("Smith J, Doe A")
    assert out == ["Smith J", "Doe A"]


def test_parse_authors_line_strips_periods():
    out = _parse_authors_line("Smith J., Doe A.")
    assert out == ["Smith J", "Doe A"]


def test_parse_empty_output():
    papers = _parse_search_output("")
    assert papers == []


def test_parse_no_results_header():
    """Output with header but no result blocks."""
    papers = _parse_search_output("Found 0 papers  [s_empty]\n\n")
    assert papers == []


# ---------- Client API tests (subprocess mocked) --------------------------


def test_client_unavailable_when_binary_missing():
    """Client.available is False when paperclip binary not on PATH."""
    with patch("vaultlab.research.sources.paperclip.shutil.which", return_value=None):
        client = PaperclipClient()
        assert not client.available


def test_client_authenticated_via_env_var():
    """PAPERCLIP_API_KEY env var is sufficient for is_authenticated."""
    with (
        patch(
            "vaultlab.research.sources.paperclip.shutil.which", return_value="/usr/bin/paperclip"
        ),
        patch("vaultlab.research.sources.paperclip.os.path.exists", return_value=True),
        patch.dict("os.environ", {"PAPERCLIP_API_KEY": "test-key"}),
    ):
        client = PaperclipClient()
        assert client.is_authenticated()


def test_client_unauthenticated_raises_in_search():
    """Search raises PaperclipUnavailable when explicitly not signed in.

    The optimistic-by-default ``is_authenticated`` only flips to False
    when ``paperclip config`` explicitly says "not signed in" AND no
    credentials file is found.
    """
    with (
        patch(
            "vaultlab.research.sources.paperclip.shutil.which", return_value="/usr/bin/paperclip"
        ),
        patch("vaultlab.research.sources.paperclip.os.path.exists", return_value=True),
        patch("vaultlab.research.sources.paperclip.os.path.isfile", return_value=False),
        patch.dict("os.environ", {}, clear=True),
        patch("vaultlab.research.sources.paperclip.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Auth: not signed in",
            stderr="",
        )
        client = PaperclipClient()
        with pytest.raises(PaperclipUnavailable):
            client.search("anything")


def test_client_returns_papers_on_success():
    """Search subprocess returns parsed Paper objects."""
    with (
        patch(
            "vaultlab.research.sources.paperclip.shutil.which", return_value="/usr/bin/paperclip"
        ),
        patch("vaultlab.research.sources.paperclip.os.path.exists", return_value=True),
        patch.dict("os.environ", {"PAPERCLIP_API_KEY": "k"}),
        patch.object(PaperclipClient, "_run_paperclip") as mock_run,
    ):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=SEARCH_OUTPUT_3,
            stderr="",
        )
        client = PaperclipClient()
        papers = client.search("test query", max_results=3)
        assert len(papers) == 3
        assert papers[0].source_api == "paperclip"


def test_client_returns_empty_on_search_error():
    """Non-zero exit returns empty list, doesn't raise."""
    with (
        patch(
            "vaultlab.research.sources.paperclip.shutil.which", return_value="/usr/bin/paperclip"
        ),
        patch("vaultlab.research.sources.paperclip.os.path.exists", return_value=True),
        patch.dict("os.environ", {"PAPERCLIP_API_KEY": "k"}),
        patch.object(PaperclipClient, "_run_paperclip") as mock_run,
    ):
        mock_run.return_value = MagicMock(
            returncode=2,
            stdout="",
            stderr="API error",
        )
        client = PaperclipClient()
        papers = client.search("query")
        assert papers == []


def test_client_search_passes_source_filter():
    """sources= kwarg becomes -s SOURCE flags on the CLI."""
    with (
        patch(
            "vaultlab.research.sources.paperclip.shutil.which", return_value="/usr/bin/paperclip"
        ),
        patch("vaultlab.research.sources.paperclip.os.path.exists", return_value=True),
        patch.dict("os.environ", {"PAPERCLIP_API_KEY": "k"}),
        patch.object(PaperclipClient, "_run_paperclip") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        client = PaperclipClient()
        client.search("query", sources=["pmc", "biorxiv"])
        called_args = mock_run.call_args[0][0]
        assert "-s" in called_args
        # Both sources should be passed
        s_indices = [i for i, a in enumerate(called_args) if a == "-s"]
        assert len(s_indices) == 2
        assert called_args[s_indices[0] + 1] == "pmc"
        assert called_args[s_indices[1] + 1] == "biorxiv"


def test_lookup_doi_returns_paper_on_hit():
    """lookup_doi parses paperclip's lookup output (same format as search)."""
    output = """\
  1. Hickey et al. spatial mapping primer
     John W. Hickey, Elizabeth K. Neumann, Garry P. Nolan
     arx_2107.07953 · arXiv · 2021-07-16
     "This paper reviews multiplexed antibody-based imaging."
"""
    with (
        patch(
            "vaultlab.research.sources.paperclip.shutil.which", return_value="/usr/bin/paperclip"
        ),
        patch("vaultlab.research.sources.paperclip.os.path.exists", return_value=True),
        patch.object(PaperclipClient, "_run_paperclip") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout=output, stderr="")
        client = PaperclipClient()
        paper = client.lookup_doi("10.48550/arXiv.2107.07953")
        assert paper is not None
        assert paper.year == 2021
        # CLI was called with `lookup doi <doi>`
        called_args = mock_run.call_args[0][0]
        assert "lookup" in called_args
        assert "doi" in called_args


def test_lookup_doi_returns_none_on_miss():
    """When paperclip exits non-zero, lookup_doi returns None silently."""
    with (
        patch(
            "vaultlab.research.sources.paperclip.shutil.which", return_value="/usr/bin/paperclip"
        ),
        patch("vaultlab.research.sources.paperclip.os.path.exists", return_value=True),
        patch.object(PaperclipClient, "_run_paperclip") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not found")
        client = PaperclipClient()
        assert client.lookup_doi("10.1/missing") is None


def test_lookup_doi_returns_none_on_empty_input():
    with (
        patch(
            "vaultlab.research.sources.paperclip.shutil.which", return_value="/usr/bin/paperclip"
        ),
        patch("vaultlab.research.sources.paperclip.os.path.exists", return_value=True),
    ):
        client = PaperclipClient()
        assert client.lookup_doi("") is None
        assert client.lookup_doi(None) is None


def test_client_search_passes_since_flag():
    """since= kwarg becomes --since flag."""
    with (
        patch(
            "vaultlab.research.sources.paperclip.shutil.which", return_value="/usr/bin/paperclip"
        ),
        patch("vaultlab.research.sources.paperclip.os.path.exists", return_value=True),
        patch.dict("os.environ", {"PAPERCLIP_API_KEY": "k"}),
        patch.object(PaperclipClient, "_run_paperclip") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        client = PaperclipClient()
        client.search("query", since="30d")
        called_args = mock_run.call_args[0][0]
        assert "--since" in called_args
        assert called_args[called_args.index("--since") + 1] == "30d"
