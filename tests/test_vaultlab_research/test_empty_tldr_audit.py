"""Tests for vaultlab.research.empty_tldr_audit."""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.research.empty_tldr_audit import (
    MIN_TLDR_CHARS,
    AuditResult,
    AuditSummary,
    TLDRStatus,
    audit_summaries,
    classify_summary,
    recoverable_paths,
)


def _write_summary(
    path: Path,
    *,
    tier: str = "A",
    doi: str = "10.1/test",
    tldr: str | None = "This is a substantive TL;DR for testing." * 2,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    parts = [
        "---",
        f'doi: "{doi}"',
        f"tier: {tier}",
        "title: Test paper",
        "---",
        "",
    ]
    if tldr is not None:
        parts.extend(["## TL;DR", "", tldr, ""])
    parts.append("## Why it matters")
    parts.append("- ...")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# classify_summary
# ---------------------------------------------------------------------------


def test_classify_substantive_tldr_as_ok(tmp_path: Path):
    p = _write_summary(tmp_path / "ok.md")
    result = classify_summary(p)
    assert result.status == TLDRStatus.OK
    assert result.tier == "A"
    assert result.tldr_length > MIN_TLDR_CHARS


def test_classify_missing_tldr_heading_as_empty(tmp_path: Path):
    p = _write_summary(tmp_path / "no-heading.md", tldr=None)
    result = classify_summary(p)
    assert result.status == TLDRStatus.EMPTY_TLDR
    assert "no '## TL;DR' heading" in result.reason


def test_classify_placeholder_tldr_as_empty(tmp_path: Path):
    p = _write_summary(tmp_path / "placeholder.md", tldr="_(empty)_")
    result = classify_summary(p)
    assert result.status == TLDRStatus.EMPTY_TLDR
    assert "placeholder" in result.reason.lower()


def test_classify_tier_c_stub_text_as_empty(tmp_path: Path):
    p = _write_summary(
        tmp_path / "stub.md",
        tldr="_No full-text PDF available; this is a Tier C stub built from corpus metrics only._",
    )
    result = classify_summary(p)
    assert result.status == TLDRStatus.EMPTY_TLDR


def test_classify_short_tldr_as_empty(tmp_path: Path):
    p = _write_summary(tmp_path / "short.md", tldr="Too short.")
    result = classify_summary(p)
    assert result.status == TLDRStatus.EMPTY_TLDR
    assert "shorter than" in result.reason


def test_classify_just_at_threshold_as_ok(tmp_path: Path):
    """Exactly MIN_TLDR_CHARS should be OK (boundary)."""
    text = "x" * MIN_TLDR_CHARS
    p = _write_summary(tmp_path / "edge.md", tldr=text)
    result = classify_summary(p)
    assert result.status == TLDRStatus.OK


def test_classify_missing_file_as_unreadable(tmp_path: Path):
    result = classify_summary(tmp_path / "nonexistent.md")
    assert result.status == TLDRStatus.UNREADABLE


def test_classify_no_frontmatter_as_unreadable(tmp_path: Path):
    p = tmp_path / "no-fm.md"
    p.write_text("just a body\n", encoding="utf-8")
    result = classify_summary(p)
    assert result.status == TLDRStatus.UNREADABLE


def test_classify_broken_yaml_as_unreadable(tmp_path: Path):
    p = tmp_path / "broken.md"
    p.write_text("---\nbroken: [unclosed\n---\nbody\n", encoding="utf-8")
    result = classify_summary(p)
    assert result.status == TLDRStatus.UNREADABLE


# ---------------------------------------------------------------------------
# audit_summaries (aggregation)
# ---------------------------------------------------------------------------


def test_audit_buckets_results_by_status_and_tier(tmp_path: Path):
    paths = [
        _write_summary(tmp_path / "ok-a.md", tier="A"),
        _write_summary(tmp_path / "empty-a.md", tier="A", tldr="_(empty)_"),
        _write_summary(tmp_path / "empty-b.md", tier="B", tldr="_(empty)_"),
        _write_summary(tmp_path / "empty-c.md", tier="C", tldr="_(empty)_"),
    ]
    summary = audit_summaries(paths)

    assert summary.total == 4
    assert len(summary.ok) == 2  # ok-a + tier-C empty (expected, not flagged)
    assert len(summary.empty_tldr_tier_a) == 1
    assert len(summary.empty_tldr_tier_b) == 1
    assert summary.empty_tldr_tier_a[0].path.name == "empty-a.md"
    assert summary.empty_tldr_tier_b[0].path.name == "empty-b.md"


def test_audit_handles_unreadable_files(tmp_path: Path):
    # One ok, one missing
    paths = [
        _write_summary(tmp_path / "ok.md"),
        tmp_path / "missing.md",
    ]
    summary = audit_summaries(paths)
    assert len(summary.ok) == 1
    assert len(summary.unreadable) == 1


def test_audit_empty_iterable():
    summary = audit_summaries([])
    assert summary.total == 0
    assert summary.ok == []


# ---------------------------------------------------------------------------
# recoverable_paths
# ---------------------------------------------------------------------------


def test_recoverable_when_pdf_cached(tmp_path: Path):
    pdf_dir = tmp_path / "Sources" / "Papers"
    pdf_dir.mkdir(parents=True)
    # Cache a PDF for "10.1/recoverable"
    from vaultlab.kb.paths import slugify_doi
    (pdf_dir / f"{slugify_doi('10.1/recoverable')}.pdf").write_bytes(b"PDF data")

    audit_results = [
        AuditResult(
            path=tmp_path / "x.md", doi="10.1/recoverable",
            tier="A", status=TLDRStatus.EMPTY_TLDR,
            tldr_length=0, reason="empty",
        ),
    ]

    recoverable, unrecoverable = recoverable_paths(
        audit_results=audit_results, pdf_cache_dir=pdf_dir,
    )

    assert len(recoverable) == 1
    assert len(unrecoverable) == 0
    assert recoverable[0].doi == "10.1/recoverable"


def test_unrecoverable_when_no_pdf_cached(tmp_path: Path):
    pdf_dir = tmp_path / "Sources" / "Papers"
    pdf_dir.mkdir(parents=True)

    audit_results = [
        AuditResult(
            path=tmp_path / "x.md", doi="10.1/no-pdf",
            tier="A", status=TLDRStatus.EMPTY_TLDR,
            tldr_length=0, reason="empty",
        ),
    ]

    recoverable, unrecoverable = recoverable_paths(
        audit_results=audit_results, pdf_cache_dir=pdf_dir,
    )

    assert len(recoverable) == 0
    assert len(unrecoverable) == 1


def test_unrecoverable_when_doi_missing(tmp_path: Path):
    pdf_dir = tmp_path / "Sources" / "Papers"
    pdf_dir.mkdir(parents=True)

    audit_results = [
        AuditResult(
            path=tmp_path / "x.md", doi="",  # no DOI extracted
            tier="A", status=TLDRStatus.EMPTY_TLDR,
            tldr_length=0, reason="empty",
        ),
    ]

    recoverable, unrecoverable = recoverable_paths(
        audit_results=audit_results, pdf_cache_dir=pdf_dir,
    )

    assert len(recoverable) == 0
    assert len(unrecoverable) == 1


def test_unrecoverable_when_pdf_zero_bytes(tmp_path: Path):
    """A 0-byte PDF file is treated as not-actually-cached."""
    pdf_dir = tmp_path / "Sources" / "Papers"
    pdf_dir.mkdir(parents=True)
    from vaultlab.kb.paths import slugify_doi
    (pdf_dir / f"{slugify_doi('10.1/zero')}.pdf").write_bytes(b"")  # zero bytes

    audit_results = [
        AuditResult(
            path=tmp_path / "x.md", doi="10.1/zero",
            tier="A", status=TLDRStatus.EMPTY_TLDR,
            tldr_length=0, reason="empty",
        ),
    ]

    _, unrecoverable = recoverable_paths(
        audit_results=audit_results, pdf_cache_dir=pdf_dir,
    )
    assert len(unrecoverable) == 1
