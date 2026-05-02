"""Tests for paperclip as Tier-0 in the acquisition waterfall.

Per the 2026-05-02 paperclip integration design (Q3 + Q4): when a
:class:`PaperclipClient` is passed to ``acquire_pdf``, we check
paperclip's corpus first. On hit, return ``source="paperclip"`` and
``pdf_path=None`` (the consumer reads pre-extracted sections from the
paperclip virtual filesystem). On miss, record
``not_in_paperclip_corpus`` and fall through to the existing waterfall.
On any client error (auth, binary, timeout): Q5 graceful degrade —
skip silently and continue.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vaultlab.research.acquisition import AcquisitionResult, acquire_pdf
from vaultlab.research.paper import Paper
from vaultlab.research.sources.paperclip import PaperclipUnavailable


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    """Empty cache dir for each test."""
    return tmp_path / "papers"


def test_paperclip_hit_returns_paperclip_source(cache_dir: Path):
    """When paperclip has the paper, acquire_pdf short-circuits."""
    pc = MagicMock()
    pc.lookup_doi.return_value = Paper(
        doi="10.1/x",
        title="Found in paperclip",
        year=2024,
        source_api="paperclip",
    )
    with patch("vaultlab.research.acquisition._PoliteSession") as mock_sess:
        result = acquire_pdf(
            doi="10.1/x",
            cache_dir=cache_dir,
            paperclip_client=pc,
        )

    # Hit short-circuits BEFORE any HTTP call (mock_sess never used)
    assert result.source == "paperclip"
    assert result.outcome == "paperclip_full_text"
    assert result.pdf_path is None  # paperclip serves text, not PDF
    assert result.is_full_text
    assert "paperclip" in result.tried
    assert pc.lookup_doi.called


def test_paperclip_miss_falls_through_to_waterfall(cache_dir: Path):
    """When paperclip misses, the existing tiers still run."""
    pc = MagicMock()
    pc.lookup_doi.return_value = None  # not in corpus

    # Mock all the HTTP tiers as failing too — the goal is to verify
    # control flow falls through, not that any specific later tier wins.
    with patch("vaultlab.research.acquisition._try_unpaywall", return_value=None), \
         patch("vaultlab.research.acquisition._try_pmc", return_value=None), \
         patch("vaultlab.research.acquisition._try_biorxiv", return_value=None), \
         patch("vaultlab.research.acquisition._try_springer", return_value=None), \
         patch("vaultlab.research.acquisition._try_elsevier", return_value=None):
        result = acquire_pdf(
            doi="10.1/y",
            cache_dir=cache_dir,
            paperclip_client=pc,
            apis={},  # no springer/elsevier keys → those tiers no-op
        )

    # paperclip was tried first
    assert result.tried[0] == "paperclip"
    # But other tiers ran after the miss
    assert "unpaywall" in result.tried
    # paperclip recorded in tier_errors with the miss reason
    assert "not_in_paperclip_corpus" in result.tier_errors.get("paperclip", "")
    # End state: no full-text anywhere
    assert result.source == "failed"


def test_paperclip_lookup_error_does_not_break_waterfall(cache_dir: Path):
    """PaperclipUnavailable from lookup_doi is absorbed; other tiers run."""
    pc = MagicMock()
    pc.lookup_doi.side_effect = PaperclipUnavailable("not authenticated")

    with patch("vaultlab.research.acquisition._try_unpaywall", return_value=None), \
         patch("vaultlab.research.acquisition._try_pmc", return_value=None), \
         patch("vaultlab.research.acquisition._try_biorxiv", return_value=None), \
         patch("vaultlab.research.acquisition._try_springer", return_value=None), \
         patch("vaultlab.research.acquisition._try_elsevier", return_value=None):
        result = acquire_pdf(
            doi="10.1/z",
            cache_dir=cache_dir,
            paperclip_client=pc,
            apis={},
        )

    # paperclip was tried but failed gracefully
    assert "paperclip" in result.tried
    assert "lookup error" in result.tier_errors["paperclip"]
    # Other tiers ran
    assert "unpaywall" in result.tried


def test_paperclip_client_none_skips_tier_silently(cache_dir: Path):
    """When paperclip_client is None, the tier doesn't appear in tried/errors."""
    with patch("vaultlab.research.acquisition._try_unpaywall", return_value=None), \
         patch("vaultlab.research.acquisition._try_pmc", return_value=None), \
         patch("vaultlab.research.acquisition._try_biorxiv", return_value=None), \
         patch("vaultlab.research.acquisition._try_springer", return_value=None), \
         patch("vaultlab.research.acquisition._try_elsevier", return_value=None):
        result = acquire_pdf(
            doi="10.1/n",
            cache_dir=cache_dir,
            paperclip_client=None,  # skip silently
            apis={},
        )

    # paperclip not tried
    assert "paperclip" not in result.tried
    assert "paperclip" not in result.tier_errors


def test_paperclip_hit_outcome_is_paperclip_full_text(cache_dir: Path):
    """End-to-end: paperclip hit yields the right classified outcome."""
    pc = MagicMock()
    pc.lookup_doi.return_value = Paper(
        doi="10.1/x",
        title="X",
        year=2024,
        source_api="paperclip",
    )
    result = acquire_pdf(
        doi="10.1/x",
        cache_dir=cache_dir,
        paperclip_client=pc,
    )
    assert result.outcome == "paperclip_full_text"
    assert result.is_full_text
    assert not result.is_metadata_only
    assert not result.needs_manual_fetch


def test_cache_hit_takes_priority_over_paperclip(tmp_path: Path):
    """If a PDF is already cached on disk, return cache_hit before
    even asking paperclip — preserves existing fast-path behaviour."""
    cache_dir = tmp_path / "papers"
    cache_dir.mkdir()
    # Create a "valid PDF" cache hit
    cached = cache_dir / "10.1_a.pdf"
    cached.write_bytes(b"%PDF-1.4\n" + b"x" * 2000)

    # Patch doi_slug + cache_path_for to point to our fake cached file
    with patch("vaultlab.research.acquisition.cache_path_for",
               return_value=cached):
        pc = MagicMock()
        pc.lookup_doi = MagicMock()  # would be called if cache miss
        result = acquire_pdf(
            doi="10.1/a",
            cache_dir=cache_dir,
            paperclip_client=pc,
        )

    assert result.source == "cache"
    assert result.outcome == "cache_hit"
    # paperclip never queried because cache short-circuited first
    assert not pc.lookup_doi.called


def test_paperclip_miss_tier_errors_does_not_classify_as_paywalled(
    cache_dir: Path,
):
    """Adding 'not_in_paperclip_corpus' to tier_errors must NOT cause
    the result to be misclassified as failed_paywalled."""
    pc = MagicMock()
    pc.lookup_doi.return_value = None

    # Make all HTTP tiers fail with 404 — should classify as
    # failed_not_indexed, NOT failed_paywalled, because none of the
    # tier errors are auth-related.
    def make_404(name):
        def _f(*args, **kwargs):
            return None
        return _f

    with patch("vaultlab.research.acquisition._try_unpaywall", return_value=None), \
         patch("vaultlab.research.acquisition._try_pmc", return_value=None), \
         patch("vaultlab.research.acquisition._try_biorxiv", return_value=None), \
         patch("vaultlab.research.acquisition._try_springer", return_value=None), \
         patch("vaultlab.research.acquisition._try_elsevier", return_value=None):
        result = acquire_pdf(
            doi="10.1/notfound",
            cache_dir=cache_dir,
            paperclip_client=pc,
            apis={},  # no elsevier/springer key — those tiers won't be tried
        )

    # paperclip miss in tier_errors
    assert "paperclip" in result.tier_errors
    # But final classification is not paywalled
    assert result.outcome != "failed_paywalled"
    assert not result.needs_manual_fetch


def test_paperclip_tier_runs_before_unpaywall(cache_dir: Path):
    """Paperclip is Tier 0 — must be tried BEFORE Unpaywall."""
    pc = MagicMock()
    pc.lookup_doi.return_value = None

    with patch("vaultlab.research.acquisition._try_unpaywall", return_value=None), \
         patch("vaultlab.research.acquisition._try_pmc", return_value=None), \
         patch("vaultlab.research.acquisition._try_biorxiv", return_value=None), \
         patch("vaultlab.research.acquisition._try_springer", return_value=None), \
         patch("vaultlab.research.acquisition._try_elsevier", return_value=None):
        result = acquire_pdf(
            doi="10.1/order",
            cache_dir=cache_dir,
            paperclip_client=pc,
            apis={},
        )

    # tried list ordering: paperclip first
    pc_idx = result.tried.index("paperclip")
    upw_idx = result.tried.index("unpaywall")
    assert pc_idx < upw_idx
