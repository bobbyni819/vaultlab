"""Tests for the per-KB papers ledger (vaultlab.research.papers_index).

The ledger is the source-of-truth corpus manifest, enumerated from disk by joining
``Sources/Papers/*.pdf`` to ``Wiki/Summaries/*.md`` on DOI-slug. These tests pin the
behaviours the rest of the spine relies on: the PDF/summary join, readability +
hashing, the read-depth ladder, the idempotency query helpers, and persistence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.kb.paths import papers_index_md_path, papers_index_path, slugify_doi
from vaultlab.research import papers_index as pidx

VALID_PDF = b"%PDF-1.4\n" + b"x" * 4096  # passes magic + min-bytes
STUB = b"<html>paywall login</html>"  # no %PDF- magic and < 1024 bytes

DOI_FULL = "10.1126/science.1225829"
DOI_BARE = "10.1038/s41586-023-05915-x"  # PDF only, no summary
DOI_ABSTRACT = "10.1016/j.cell.2018.07.010"  # summary only, no PDF
DOI_STUB = "10.1101/2020.01.01.000001"  # unreadable PDF + summary


def _papers_dir(kb: Path) -> Path:
    d = kb / "Sources" / "Papers"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _summaries_dir(kb: Path) -> Path:
    d = kb / "Wiki" / "Summaries"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_pdf(kb: Path, doi: str, data: bytes) -> Path:
    p = _papers_dir(kb) / f"{slugify_doi(doi)}.pdf"
    p.write_bytes(data)
    return p


def _write_summary(
    kb: Path,
    doi: str,
    *,
    tier: str = "A",
    sha: str = "",
    status: str = "",
    grounded: bool = False,
    body: str = "## TL;DR\nA substantial prose paragraph describing the paper in detail "
    "so the read-depth heuristic sees real content here, well over two hundred chars "
    "of body text to be safe and then some more padding to clear the threshold.",
) -> Path:
    fm = ["---", f"doi: {doi}", f"title: Title for {doi}", "year: 2020", f"tier: {tier}"]
    if sha:
        fm.append(f"source_pdf_sha256: {sha}")
    if status:
        fm.append(f"status: {status}")
    if grounded:
        fm.append("grounded: true")
    fm.append("---")
    text = "\n".join(fm) + "\n\n" + body + "\n\n## Methods\nstuff\n## Key findings\n- a [p1]\n"
    p = _summaries_dir(kb) / f"{slugify_doi(doi)}.md"
    p.write_text(text, encoding="utf-8")
    return p


@pytest.fixture()
def kb(tmp_path: Path) -> Path:
    """A KB with four papers spanning every state the ledger must distinguish."""
    # 1. Full read: valid PDF + Tier-A summary whose recorded hash matches the PDF.
    pdf = _write_pdf(tmp_path, DOI_FULL, VALID_PDF)
    sha = pidx.pdf_sha256(pdf)
    _write_summary(tmp_path, DOI_FULL, tier="A", sha=sha, status="VERIFIED")

    # 2. Bare PDF, no summary -> the reading backlog.
    _write_pdf(tmp_path, DOI_BARE, VALID_PDF)

    # 3. Tier-C summary, no PDF -> abstract-only.
    _write_summary(tmp_path, DOI_ABSTRACT, tier="C", body="## TL;DR\n_stub_")

    # 4. Unreadable PDF stub + Tier-A summary -> needs re-fetch.
    _write_pdf(tmp_path, DOI_STUB, STUB)
    _write_summary(tmp_path, DOI_STUB, tier="A")
    return tmp_path


def test_scan_joins_pdfs_and_summaries(kb: Path):
    index = pidx.scan_corpus(kb)
    assert index.counts["total"] == 4
    by_slug = index.by_slug
    assert set(by_slug) == {
        slugify_doi(DOI_FULL),
        slugify_doi(DOI_BARE),
        slugify_doi(DOI_ABSTRACT),
        slugify_doi(DOI_STUB),
    }


def test_full_read_row_is_current(kb: Path):
    e = pidx.scan_corpus(kb).entry_for_doi(DOI_FULL)
    assert e is not None
    assert e.pdf_present and e.pdf_readable
    assert e.summary_present
    assert e.read_depth == "full"
    assert e.verification == "VERIFIED"
    assert e.summary_current is True  # recorded sha == on-disk PDF sha
    assert pidx.needs_summary(e, target_depth="full") is False
    assert pidx.needs_fetch(e) is False


def test_bare_pdf_is_backlog_not_read(kb: Path):
    index = pidx.scan_corpus(kb)
    e = index.entry_for_doi(DOI_BARE)
    assert e.pdf_present and e.pdf_readable
    assert e.summary_present is False
    assert e.read_depth == "none"
    assert pidx.needs_summary(e) is True
    assert e in index.reading_backlog()


def test_abstract_only_row(kb: Path):
    e = pidx.scan_corpus(kb).entry_for_doi(DOI_ABSTRACT)
    assert e.pdf_present is False
    assert e.read_depth == "abstract"
    # Below the 'full' target on the ladder -> still wants a deeper read once a PDF lands.
    assert pidx.needs_summary(e, target_depth="full") is True
    # ...but no PDF, so it surfaces as a re-fetch candidate, not a backlog read.
    assert pidx.needs_fetch(e) is True
    assert e not in pidx.scan_corpus(kb).reading_backlog()


def test_unreadable_stub_needs_refetch(kb: Path):
    index = pidx.scan_corpus(kb)
    e = index.entry_for_doi(DOI_STUB)
    assert e.pdf_present is True
    assert e.pdf_readable is False
    assert e.pdf_sha256 == ""  # unreadable PDFs are not hashed
    assert pidx.needs_fetch(e) is True
    assert e in index.needs_refetch()


def test_pdf_change_invalidates_summary(kb: Path):
    # Rewrite the full-read paper's PDF with different bytes; its summary's recorded
    # hash no longer matches, so the summary is stale and must be re-read.
    _write_pdf(kb, DOI_FULL, b"%PDF-1.7\n" + b"y" * 5000)
    e = pidx.scan_corpus(kb).entry_for_doi(DOI_FULL)
    assert e.summary_current is False
    assert pidx.needs_summary(e, target_depth="full") is True


def test_grounded_depth(tmp_path: Path):
    pdf = _write_pdf(tmp_path, DOI_FULL, VALID_PDF)
    sha = pidx.pdf_sha256(pdf)
    _write_summary(tmp_path, DOI_FULL, tier="A", sha=sha, grounded=True)
    e = pidx.scan_corpus(tmp_path).entry_for_doi(DOI_FULL)
    assert e.read_depth == "grounded"
    assert pidx.needs_summary(e, target_depth="grounded") is False


def test_existing_summary_pdf_sha(kb: Path):
    pdf = _papers_dir(kb) / f"{slugify_doi(DOI_FULL)}.pdf"
    expected = pidx.pdf_sha256(pdf)
    assert pidx.existing_summary_pdf_sha(kb, DOI_FULL) == expected
    assert pidx.existing_summary_pdf_sha(kb, DOI_BARE) is None  # no summary


def test_save_and_load_roundtrip(kb: Path):
    index, json_path, md_path = pidx.build_and_save(kb)
    assert json_path == papers_index_path(kb)
    assert md_path == papers_index_md_path(kb)
    assert json_path.exists() and md_path.exists()

    payload = pidx.load_index(kb)
    assert payload is not None
    assert payload["counts"]["total"] == 4
    assert len(payload["entries"]) == 4

    md = md_path.read_text(encoding="utf-8")
    assert "# Papers index" in md
    assert "Reading backlog" in md  # the bare PDF surfaces here


def test_index_md_not_scanned_as_summary(kb: Path):
    # Persisting the index writes _papers_index.md into Wiki/Summaries/. A re-scan must
    # NOT pick it up as a 5th paper (underscore-prefixed files are skipped).
    pidx.build_and_save(kb)
    assert pidx.scan_corpus(kb).counts["total"] == 4


def test_needs_summary_rejects_unknown_depth(kb: Path):
    e = pidx.scan_corpus(kb).entry_for_doi(DOI_FULL)
    with pytest.raises(ValueError):
        pidx.needs_summary(e, target_depth="skimmed")
