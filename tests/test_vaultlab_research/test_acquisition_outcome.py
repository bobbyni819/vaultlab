"""Tests for the AcquisitionResult.outcome derived classifier.

Per the 2026-05-02 paperclip integration design (Q4), the
``AcquisitionResult.outcome`` property classifies the existing
``source`` + ``tier_errors`` fields into a richer state machine the
user-facing CLI can consume for paywall-transparency reports.

These tests pin the classifier's behaviour so future changes to
acquisition tiers don't silently change the outcome taxonomy.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.research.acquisition import AcquisitionResult


def _result(*, source: str, pdf_path: Path | None = None,
            tier_errors: dict[str, str] | None = None,
            license: str | None = None) -> AcquisitionResult:
    return AcquisitionResult(
        doi="10.1/test",
        pdf_path=pdf_path,
        source=source,
        license=license,
        tier_errors=tier_errors or {},
    )


# ---- Successful-acquisition outcomes ------------------------------------

def test_cache_hit():
    r = _result(source="cache", pdf_path=Path("/tmp/x.pdf"))
    assert r.outcome == "cache_hit"
    assert r.is_full_text
    assert not r.needs_manual_fetch
    assert not r.is_metadata_only


def test_paperclip_full_text():
    """Paperclip success: full text + figures pre-extracted server-side."""
    r = _result(source="paperclip", pdf_path=None)  # no local PDF; that's fine
    assert r.outcome == "paperclip_full_text"
    assert r.is_full_text
    assert not r.is_metadata_only


def test_oa_pdf_unpaywall():
    r = _result(source="unpaywall", pdf_path=Path("/tmp/x.pdf"))
    assert r.outcome == "oa_pdf"
    assert r.is_full_text


def test_oa_pdf_pmc():
    r = _result(source="pmc", pdf_path=Path("/tmp/x.pdf"))
    assert r.outcome == "oa_pdf"


def test_oa_pdf_biorxiv():
    r = _result(source="biorxiv", pdf_path=Path("/tmp/x.pdf"))
    assert r.outcome == "oa_pdf"


def test_oa_pdf_medrxiv():
    r = _result(source="medrxiv", pdf_path=Path("/tmp/x.pdf"))
    assert r.outcome == "oa_pdf"


def test_springer_with_pdf_is_oa():
    """Springer succeeded with a PDF means we got the OA full text."""
    r = _result(source="springer", pdf_path=Path("/tmp/x.pdf"))
    assert r.outcome == "oa_pdf"


def test_springer_metadata_only():
    """Springer succeeded but no PDF → abstract/metadata only (Tier-B)."""
    r = _result(source="springer", pdf_path=None)
    assert r.outcome == "gated_metadata_only"
    assert r.is_metadata_only
    assert not r.is_full_text


def test_elsevier_gated_pdf_via_key():
    r = _result(source="elsevier", pdf_path=Path("/tmp/x.pdf"))
    assert r.outcome == "gated_pdf_via_key"
    assert r.is_full_text


# ---- Failure-mode outcomes ----------------------------------------------

def test_failed_paywalled_via_403_signal():
    """tier_errors with '403' surfaces as paywalled."""
    r = _result(
        source="failed",
        tier_errors={
            "unpaywall": "404",
            "pmc": "404",
            "elsevier": "403",
        },
    )
    assert r.outcome == "failed_paywalled"
    assert r.needs_manual_fetch


def test_failed_paywalled_via_401_signal():
    r = _result(
        source="failed",
        tier_errors={"elsevier": "401 Unauthorized"},
    )
    assert r.outcome == "failed_paywalled"
    assert r.needs_manual_fetch


def test_failed_paywalled_via_subscription_word():
    r = _result(
        source="failed",
        tier_errors={"elsevier": "subscription required"},
    )
    assert r.outcome == "failed_paywalled"


def test_failed_paywalled_when_gated_tier_attempted_without_explicit_signal():
    """Tried Elsevier (gated tier) but no clear auth-error signal still
    classifies as paywalled — best-effort heuristic for transparency."""
    r = _result(
        source="failed",
        tier_errors={"elsevier": "non-pdf content"},
    )
    assert r.outcome == "failed_paywalled"


def test_failed_not_indexed():
    """Tried only OA tiers, all 404 → not indexed anywhere."""
    r = _result(
        source="failed",
        tier_errors={
            "unpaywall": "404",
            "pmc": "no PMCID",
            "biorxiv": "404",
        },
    )
    assert r.outcome == "failed_not_indexed"
    assert not r.needs_manual_fetch


def test_failed_no_tier_errors_falls_back_to_unspecified():
    """Pure failed without tier_errors and without gated-tier attempts
    is the legacy ``failed`` state."""
    r = _result(source="failed", tier_errors={})
    assert r.outcome == "failed_not_indexed"


def test_unknown_source_falls_back_to_failed():
    r = _result(source="weird_unknown_source")
    assert r.outcome == "failed"


# ---- Property cross-validation ------------------------------------------

def test_full_text_states_are_disjoint_from_paywalled():
    """is_full_text and needs_manual_fetch must never both be True."""
    states = [
        _result(source="cache", pdf_path=Path("/tmp/x.pdf")),
        _result(source="paperclip"),
        _result(source="unpaywall", pdf_path=Path("/tmp/x.pdf")),
        _result(source="elsevier", pdf_path=Path("/tmp/x.pdf")),
        _result(source="failed", tier_errors={"elsevier": "403"}),
    ]
    for r in states:
        assert not (r.is_full_text and r.needs_manual_fetch), (
            f"Both flags true for {r.outcome}: full_text + needs_manual_fetch"
        )


def test_metadata_only_is_disjoint_from_full_text():
    states = [
        _result(source="cache", pdf_path=Path("/tmp/x.pdf")),
        _result(source="paperclip"),
        _result(source="unpaywall", pdf_path=Path("/tmp/x.pdf")),
        _result(source="springer", pdf_path=None),  # metadata-only
    ]
    for r in states:
        assert not (r.is_metadata_only and r.is_full_text)


def test_paperclip_outcome_does_not_require_pdf_path():
    """paperclip_full_text is a unique state — sections live in the
    server-side virtual filesystem, not as a local PDF."""
    r = _result(source="paperclip", pdf_path=None)
    assert r.is_full_text
    assert r.outcome == "paperclip_full_text"
    assert r.pdf_path is None


# ---- Backward compatibility ---------------------------------------------

def test_existing_callers_unchanged():
    """Adding outcome property must not break code that reads the
    legacy ``source`` field directly."""
    r = _result(source="unpaywall", pdf_path=Path("/tmp/x.pdf"),
                license="cc-by")
    # Legacy access patterns still work
    assert r.source == "unpaywall"
    assert r.license == "cc-by"
    assert r.pdf_path == Path("/tmp/x.pdf")
    # New access patterns also work
    assert r.outcome == "oa_pdf"
    assert r.is_full_text
