"""Tests for vaultlab.citations.evidence.EvidenceIndex.

Covers:
- store → lookup round-trip
- DOI + claim normalization (case/whitespace)
- Miss paths (unknown DOI, known DOI unknown claim)
- JSON on-disk persistence across separate instances
- Empty index defaults
- Dedup: same doi+claim stored twice — no duplicate entry, new source_file appended
- list_all() / stats() aggregates
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.citations.evidence import EvidenceIndex


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_index(tmp_path: Path) -> EvidenceIndex:
    return EvidenceIndex(str(tmp_path))


def _store_one(idx: EvidenceIndex, doi: str = "10.1/abc", claim: str = "Claim A") -> None:
    idx.store(
        doi=doi,
        claim=claim,
        status="supported",
        evidence_chunk="The data show X.",
        chunk_location="p3",
        confidence=0.9,
        source_file="draft.md",
    )


# ---------------------------------------------------------------------------
# 1. store → lookup round-trip
# ---------------------------------------------------------------------------

def test_store_lookup_round_trip(tmp_path: Path) -> None:
    idx = _make_index(tmp_path)
    _store_one(idx)

    result = idx.lookup("10.1/abc", "Claim A")

    assert result is not None
    assert result["status"] == "supported"
    assert result["evidence_chunk"] == "The data show X."
    assert result["confidence"] == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# 2. Normalization: case + whitespace variants of same doi+claim must hit
# ---------------------------------------------------------------------------

def test_normalization_doi_and_claim(tmp_path: Path) -> None:
    idx = _make_index(tmp_path)
    # Store with mixed case doi and padded claim
    idx.store(
        doi="10.1/AbC",
        claim="  Claim Text  ",
        status="supported",
        evidence_chunk="Evidence here.",
        chunk_location="p1",
        confidence=0.8,
        source_file="paper.md",
    )

    # Look up with lowercase doi + unpadded claim
    result = idx.lookup("10.1/abc", "claim text")
    assert result is not None, "Normalization failed: mixed-case/padded store not found by lowercase/unpadded lookup"
    assert result["status"] == "supported"


# ---------------------------------------------------------------------------
# 3. Miss paths
# ---------------------------------------------------------------------------

def test_lookup_unknown_doi_returns_none(tmp_path: Path) -> None:
    idx = _make_index(tmp_path)
    _store_one(idx, doi="10.1/known")

    assert idx.lookup("10.1/unknown", "Claim A") is None


def test_lookup_known_doi_unknown_claim_returns_none(tmp_path: Path) -> None:
    idx = _make_index(tmp_path)
    _store_one(idx, doi="10.1/known", claim="Claim A")

    assert idx.lookup("10.1/known", "Totally different claim") is None


# ---------------------------------------------------------------------------
# 4. JSON on-disk persistence across instances
# ---------------------------------------------------------------------------

def test_persistence_across_instances(tmp_path: Path) -> None:
    idx1 = _make_index(tmp_path)
    _store_one(idx1, doi="10.2/persist", claim="Persisted claim")

    # New instance reading from same kb_dir
    idx2 = _make_index(tmp_path)
    result = idx2.lookup("10.2/persist", "Persisted claim")

    assert result is not None, "New EvidenceIndex instance did not reload stored data from disk"
    assert result["confidence"] == pytest.approx(0.9)


def test_persistence_file_exists_at_expected_path(tmp_path: Path) -> None:
    idx = _make_index(tmp_path)
    _store_one(idx)

    expected = tmp_path / "Sources" / ".evidence_index.json"
    assert expected.exists(), f"Index file not found at {expected}"


# ---------------------------------------------------------------------------
# 5. Empty cache defaults
# ---------------------------------------------------------------------------

def test_empty_index_lookup_returns_none(tmp_path: Path) -> None:
    idx = _make_index(tmp_path)
    assert idx.lookup("10.1/anything", "Any claim") is None


def test_empty_index_stats(tmp_path: Path) -> None:
    idx = _make_index(tmp_path)
    assert idx.stats() == {"total_papers": 0, "total_claims": 0}


def test_empty_index_list_all(tmp_path: Path) -> None:
    idx = _make_index(tmp_path)
    assert idx.list_all() == []


# ---------------------------------------------------------------------------
# 6. Dedup: same doi+claim stored twice → no duplicate; new source_file appended
# ---------------------------------------------------------------------------

def test_dedup_no_duplicate_claim_entry(tmp_path: Path) -> None:
    idx = _make_index(tmp_path)
    _store_one(idx, doi="10.3/dedup", claim="Same claim")
    # Store again — different source_file
    idx.store(
        doi="10.3/dedup",
        claim="Same claim",
        status="supported",
        evidence_chunk="The data show X.",
        chunk_location="p3",
        confidence=0.9,
        source_file="second_draft.md",
    )

    # Reload to verify on-disk state
    idx2 = _make_index(tmp_path)
    stats = idx2.stats()
    assert stats["total_claims"] == 1, (
        f"Expected 1 claim after duplicate store, got {stats['total_claims']}"
    )


def test_dedup_source_file_appended(tmp_path: Path) -> None:
    idx = _make_index(tmp_path)
    _store_one(idx, doi="10.3/src", claim="Multi-source claim")
    idx.store(
        doi="10.3/src",
        claim="Multi-source claim",
        status="supported",
        evidence_chunk="The data show X.",
        chunk_location="p3",
        confidence=0.9,
        source_file="second.md",
    )

    result = idx.lookup("10.3/src", "Multi-source claim")
    assert result is not None
    # Hard membership (not .get(..., [])): a key-name regression in evidence.py
    # must FAIL here, not silently pass against an empty default.
    assert "source_files" in result, f"entry missing 'source_files' key: {result}"
    source_files = result["source_files"]
    assert "draft.md" in source_files, f"Original source_file missing: {source_files}"
    assert "second.md" in source_files, f"New source_file not appended: {source_files}"
    # Original claim text is preserved verbatim (store does not normalize at write).
    assert result["claim"] == "Multi-source claim"


# ---------------------------------------------------------------------------
# 7. list_all() / stats() after storing 2 claims across 1-2 DOIs
# ---------------------------------------------------------------------------

def test_stats_two_claims_one_doi(tmp_path: Path) -> None:
    idx = _make_index(tmp_path)
    _store_one(idx, doi="10.4/one", claim="Claim A")
    _store_one(idx, doi="10.4/one", claim="Claim B")

    s = idx.stats()
    assert s["total_papers"] == 1
    assert s["total_claims"] == 2


def test_stats_two_claims_two_dois(tmp_path: Path) -> None:
    idx = _make_index(tmp_path)
    _store_one(idx, doi="10.4/one", claim="Claim A")
    _store_one(idx, doi="10.4/two", claim="Claim B")

    s = idx.stats()
    assert s["total_papers"] == 2
    assert s["total_claims"] == 2


def test_list_all_structure(tmp_path: Path) -> None:
    idx = _make_index(tmp_path)
    _store_one(idx, doi="10.5/list", claim="Claim A")
    _store_one(idx, doi="10.5/list", claim="Claim B")

    entries = idx.list_all()
    assert len(entries) == 1
    entry = entries[0]
    assert entry["doi"] == "10.5/list"
    assert entry["claim_count"] == 2
    assert "latest_verified" in entry
    assert "statuses" in entry
    assert len(entry["statuses"]) == 2


def test_list_all_two_dois_sorted(tmp_path: Path) -> None:
    idx = _make_index(tmp_path)
    _store_one(idx, doi="10.5/zzz", claim="Last claim")
    _store_one(idx, doi="10.5/aaa", claim="First claim")

    entries = idx.list_all()
    assert len(entries) == 2
    # list_all sorts by doi key
    assert entries[0]["doi"] == "10.5/aaa"
    assert entries[1]["doi"] == "10.5/zzz"
