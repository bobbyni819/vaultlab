"""Tests for vaultlab.research.abstract_recall."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vaultlab.research.abstract_recall import (
    BackfillResult,
    _extract_body_abstract_heading,
    _extract_frontmatter_abstract,
    _inject_abstract_into_frontmatter,
    backfill_abstracts_in_kb,
    get_abstract_for_doi,
)


@dataclass
class _FakePaper:
    abstract: str = ""


@dataclass
class _FakeCorpus:
    papers: dict = field(default_factory=dict)


def _write_stub(path: Path, *, doi: str, abstract_in_body: str = "",
                abstract_in_fm: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_lines = [f'doi: "{doi}"', 'title: "Test paper"']
    if abstract_in_fm:
        fm_lines.append("abstract: |")
        for line in abstract_in_fm.split("\n"):
            fm_lines.append(f"  {line}")
    parts = ["---"] + fm_lines + ["---", "", "# Test paper", ""]
    if abstract_in_body:
        parts.extend(["## Abstract", "", abstract_in_body, ""])
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# get_abstract_for_doi — priority order
# ---------------------------------------------------------------------------


def test_corpus_papers_takes_priority_over_kb():
    """When corpus.papers has the abstract, don't read from disk."""
    corpus = _FakeCorpus(
        papers={"10.1/x": _FakePaper(abstract="from corpus  ")}
    )
    result = get_abstract_for_doi(
        doi="10.1/x",
        corpus=corpus,
        kb_root=None,
    )
    assert result == "from corpus"  # whitespace stripped


def test_falls_back_to_frontmatter_when_corpus_empty(tmp_path: Path):
    _write_stub(
        tmp_path / "Sources" / "Articles" / "10.1_x.md",
        doi="10.1/x",
        abstract_in_fm="from frontmatter",
    )
    result = get_abstract_for_doi(
        doi="10.1/x",
        kb_root=tmp_path,
    )
    assert result == "from frontmatter"


def test_falls_back_to_body_when_frontmatter_empty(tmp_path: Path):
    _write_stub(
        tmp_path / "Sources" / "Articles" / "10.1_x.md",
        doi="10.1/x",
        abstract_in_body="from body heading",
    )
    result = get_abstract_for_doi(
        doi="10.1/x",
        kb_root=tmp_path,
    )
    assert result == "from body heading"


def test_returns_empty_when_no_source_has_abstract(tmp_path: Path):
    _write_stub(
        tmp_path / "Sources" / "Articles" / "10.1_x.md",
        doi="10.1/x",
    )
    result = get_abstract_for_doi(
        doi="10.1/x",
        corpus=_FakeCorpus(papers={"10.1/x": _FakePaper(abstract="")}),
        kb_root=tmp_path,
    )
    assert result == ""


def test_crossref_fetch_when_allow_fetch_true(tmp_path: Path):
    """allow_fetch=True escalates to live CrossRef when cached is empty."""
    mock_client = MagicMock()
    mock_client.resolve_doi.return_value = MagicMock(
        abstract="from CrossRef live fetch"
    )

    result = get_abstract_for_doi(
        doi="10.1/x",
        kb_root=tmp_path,
        allow_fetch=True,
        crossref_client=mock_client,
    )

    assert result == "from CrossRef live fetch"
    mock_client.resolve_doi.assert_called_once_with("10.1/x")


def test_crossref_not_called_when_allow_fetch_false(tmp_path: Path):
    """Without allow_fetch, never hit the network."""
    mock_client = MagicMock()
    result = get_abstract_for_doi(
        doi="10.1/x",
        kb_root=tmp_path,
        allow_fetch=False,
        crossref_client=mock_client,
    )

    assert result == ""
    mock_client.resolve_doi.assert_not_called()


def test_handles_empty_doi():
    assert get_abstract_for_doi(doi="") == ""
    assert get_abstract_for_doi(doi="   ") == ""


def test_caps_extremely_long_abstracts():
    """Defensive: a 50,000-char 'abstract' (probably a paper body) gets capped."""
    huge = "x" * 50000
    corpus = _FakeCorpus(papers={"10.1/x": _FakePaper(abstract=huge)})
    result = get_abstract_for_doi(doi="10.1/x", corpus=corpus)
    assert len(result) == 5000  # _MAX_ABSTRACT_CHARS


def test_crossref_fetch_failure_returns_empty(tmp_path: Path):
    """A CrossRef exception doesn't crash; returns empty string."""
    mock_client = MagicMock()
    mock_client.resolve_doi.side_effect = RuntimeError("network failed")

    result = get_abstract_for_doi(
        doi="10.1/x",
        kb_root=tmp_path,
        allow_fetch=True,
        crossref_client=mock_client,
    )

    assert result == ""


# ---------------------------------------------------------------------------
# _extract_* helpers
# ---------------------------------------------------------------------------


def test_extract_frontmatter_handles_multi_line_scalar():
    text = """---
doi: "10.1/x"
abstract: |
  Line one of abstract.
  Line two of abstract.
---

# Title
"""
    assert _extract_frontmatter_abstract(text) == (
        "Line one of abstract.\nLine two of abstract."
    )


def test_extract_frontmatter_returns_empty_when_no_field():
    text = """---
doi: "10.1/x"
---

# Title
"""
    assert _extract_frontmatter_abstract(text) == ""


def test_extract_frontmatter_returns_empty_for_invalid_yaml():
    text = """---
broken: [unclosed
---
body
"""
    assert _extract_frontmatter_abstract(text) == ""


def test_extract_body_finds_abstract_heading():
    text = """---
doi: "10.1/x"
---

# Title

## Abstract

This is the abstract body.

## Methods

(other content)
"""
    assert _extract_body_abstract_heading(text) == "This is the abstract body."


def test_extract_body_returns_empty_when_no_heading():
    text = "---\ndoi: x\n---\n\nNo heading here\n"
    assert _extract_body_abstract_heading(text) == ""


# ---------------------------------------------------------------------------
# _inject_abstract_into_frontmatter
# ---------------------------------------------------------------------------


def test_inject_adds_abstract_to_existing_frontmatter():
    text = """---
doi: "10.1/x"
title: "Test"
---

# Title

Some body content.
"""
    result = _inject_abstract_into_frontmatter(text, "New abstract.")
    assert "abstract: |" in result
    assert "  New abstract." in result
    assert "doi: \"10.1/x\"" in result
    assert "Some body content." in result


def test_inject_replaces_existing_abstract_field():
    text = """---
doi: "10.1/x"
abstract: |
  Old abstract.
title: "Test"
---

Body
"""
    result = _inject_abstract_into_frontmatter(text, "Replacement abstract.")
    assert "Replacement abstract." in result
    assert "Old abstract." not in result


def test_inject_handles_multi_line_abstract():
    text = "---\ndoi: x\n---\nbody\n"
    result = _inject_abstract_into_frontmatter(
        text, "Line 1\nLine 2\nLine 3"
    )
    assert "  Line 1" in result
    assert "  Line 2" in result
    assert "  Line 3" in result


# ---------------------------------------------------------------------------
# backfill_abstracts_in_kb
# ---------------------------------------------------------------------------


def test_backfill_skips_stubs_with_existing_abstract(tmp_path: Path):
    _write_stub(
        tmp_path / "Sources" / "Articles" / "10.1_with-abstract.md",
        doi="10.1/with-abstract",
        abstract_in_body="Already here",
    )
    mock_client = MagicMock()

    result = backfill_abstracts_in_kb(kb_root=tmp_path, crossref_client=mock_client)

    assert result.scanned == 1
    assert result.already_present == 1
    assert result.fetched == 0
    mock_client.resolve_doi.assert_not_called()


def test_backfill_fetches_when_abstract_missing(tmp_path: Path):
    _write_stub(
        tmp_path / "Sources" / "Articles" / "10.1_no-abstract.md",
        doi="10.1/no-abstract",
    )
    mock_client = MagicMock()
    mock_client.resolve_doi.return_value = MagicMock(
        abstract="Fetched from CrossRef"
    )

    result = backfill_abstracts_in_kb(kb_root=tmp_path, crossref_client=mock_client)

    assert result.scanned == 1
    assert result.fetched == 1
    mock_client.resolve_doi.assert_called_once_with("10.1/no-abstract")

    # Verify abstract written back to file
    stub_path = tmp_path / "Sources" / "Articles" / "10.1_no-abstract.md"
    text = stub_path.read_text(encoding="utf-8")
    assert "Fetched from CrossRef" in text


def test_backfill_handles_no_abstract_from_crossref(tmp_path: Path):
    _write_stub(
        tmp_path / "Sources" / "Articles" / "10.1_x.md",
        doi="10.1/x",
    )
    mock_client = MagicMock()
    mock_client.resolve_doi.return_value = MagicMock(abstract="")

    result = backfill_abstracts_in_kb(kb_root=tmp_path, crossref_client=mock_client)
    assert result.no_abstract_available == 1
    assert result.fetched == 0


def test_backfill_handles_missing_articles_dir(tmp_path: Path):
    """No Sources/Articles dir = no-op."""
    result = backfill_abstracts_in_kb(kb_root=tmp_path)
    assert result.scanned == 0


def test_backfill_respects_max_papers(tmp_path: Path):
    for i in range(5):
        _write_stub(
            tmp_path / "Sources" / "Articles" / f"10.1_{i}.md",
            doi=f"10.1/{i}",
        )
    mock_client = MagicMock()
    mock_client.resolve_doi.return_value = MagicMock(abstract="x" * 200)

    result = backfill_abstracts_in_kb(
        kb_root=tmp_path, crossref_client=mock_client, max_papers=3
    )
    assert result.scanned == 3
    assert mock_client.resolve_doi.call_count == 3


def test_backfill_only_dois_filters(tmp_path: Path):
    for slug in ["a", "b", "c"]:
        _write_stub(
            tmp_path / "Sources" / "Articles" / f"10.1_{slug}.md",
            doi=f"10.1/{slug}",
        )
    mock_client = MagicMock()
    mock_client.resolve_doi.return_value = MagicMock(abstract="fetched")

    result = backfill_abstracts_in_kb(
        kb_root=tmp_path,
        crossref_client=mock_client,
        only_dois=["10.1/b"],
    )

    # Scans all 3, but only fetches for 'b'
    assert result.scanned == 3
    assert result.fetched == 1
    mock_client.resolve_doi.assert_called_once_with("10.1/b")


def test_backfill_handles_crossref_exception(tmp_path: Path):
    _write_stub(
        tmp_path / "Sources" / "Articles" / "10.1_x.md",
        doi="10.1/x",
    )
    mock_client = MagicMock()
    mock_client.resolve_doi.side_effect = RuntimeError("api down")

    result = backfill_abstracts_in_kb(kb_root=tmp_path, crossref_client=mock_client)
    assert result.errors == 1
    assert result.fetched == 0


# ---------------------------------------------------------------------------
# ensure_article_stub_for_doi (stub-creation-on-demand)
# ---------------------------------------------------------------------------


def test_ensure_stub_returns_existing_path_without_fetch(tmp_path: Path):
    """If a stub already exists, no CrossRef call happens."""
    from vaultlab.research.abstract_recall import ensure_article_stub_for_doi

    _write_stub(
        tmp_path / "Sources" / "Articles" / "10.1_existing.md",
        doi="10.1/existing",
    )
    mock_client = MagicMock()

    result = ensure_article_stub_for_doi(
        doi="10.1/existing",
        kb_root=tmp_path,
        crossref_client=mock_client,
    )

    assert result is not None
    assert result.exists()
    mock_client.resolve_doi.assert_not_called()


def test_ensure_stub_creates_stub_from_crossref(tmp_path: Path):
    """When stub doesn't exist, fetch from CrossRef and write."""
    from vaultlab.research.abstract_recall import ensure_article_stub_for_doi

    mock_paper = MagicMock(
        doi="10.1/new",
        title="A foundational paper",
        authors=["Author A", "Author B"],
        year=2018,
        journal="Cell",
        abstract="The abstract text from CrossRef.",
        pmid="",
        citation_count=42,
        source_api="crossref",
    )
    mock_client = MagicMock()
    mock_client.resolve_doi.return_value = mock_paper

    result = ensure_article_stub_for_doi(
        doi="10.1/new",
        kb_root=tmp_path,
        crossref_client=mock_client,
    )

    assert result is not None
    assert result.exists()

    text = result.read_text(encoding="utf-8")
    assert "A foundational paper" in text
    assert "Author A" in text
    assert "Author B" in text
    assert "2018" in text
    assert "abstract: |" in text
    assert "The abstract text from CrossRef." in text


def test_ensure_stub_returns_none_when_crossref_unknown(tmp_path: Path):
    from vaultlab.research.abstract_recall import ensure_article_stub_for_doi

    mock_client = MagicMock()
    mock_client.resolve_doi.return_value = None  # DOI unknown

    result = ensure_article_stub_for_doi(
        doi="10.1/unknown",
        kb_root=tmp_path,
        crossref_client=mock_client,
    )
    assert result is None


def test_ensure_stub_handles_crossref_exception(tmp_path: Path):
    from vaultlab.research.abstract_recall import ensure_article_stub_for_doi

    mock_client = MagicMock()
    mock_client.resolve_doi.side_effect = RuntimeError("api error")

    result = ensure_article_stub_for_doi(
        doi="10.1/x",
        kb_root=tmp_path,
        crossref_client=mock_client,
    )
    assert result is None


def test_ensure_stub_overwrite_regenerates_existing(tmp_path: Path):
    from vaultlab.research.abstract_recall import ensure_article_stub_for_doi

    # Pre-write a stub with stale info
    stub_path = tmp_path / "Sources" / "Articles" / "10.1_x.md"
    _write_stub(stub_path, doi="10.1/x", abstract_in_body="Old abstract")

    mock_paper = MagicMock(
        doi="10.1/x",
        title="Updated title",
        authors=["New Author"],
        year=2020,
        journal="Nature",
        abstract="Fresh abstract",
        pmid="",
        citation_count=0,
        source_api="crossref",
    )
    mock_client = MagicMock()
    mock_client.resolve_doi.return_value = mock_paper

    result = ensure_article_stub_for_doi(
        doi="10.1/x",
        kb_root=tmp_path,
        crossref_client=mock_client,
        overwrite=True,
    )

    assert result is not None
    text = result.read_text(encoding="utf-8")
    assert "Updated title" in text
    assert "Fresh abstract" in text
    # Old stub content gone
    assert "Old abstract" not in text


def test_ensure_stub_handles_empty_doi(tmp_path: Path):
    from vaultlab.research.abstract_recall import ensure_article_stub_for_doi

    assert ensure_article_stub_for_doi(doi="", kb_root=tmp_path) is None
    assert ensure_article_stub_for_doi(doi="   ", kb_root=tmp_path) is None
