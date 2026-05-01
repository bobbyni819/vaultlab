"""Tests for Elsevier originalText full-text path.

This is the cleaner alternative to PDF parsing for Elsevier-published
papers: the same Article Retrieval API that returns metadata also
returns the full article body as machine-extracted plain text under
``full-text-retrieval-response.originalText``.
"""

from __future__ import annotations

from unittest.mock import patch

from pathlib import Path

import pytest

from vaultlab.research.corpus import Corpus
from vaultlab.research.graph_metrics import compute_metrics
from vaultlab.research.paper import Paper
from vaultlab.research.sources.elsevier import ElsevierClient
from vaultlab.research.summarize import prepare_summary_task


# ---------------------------------------------------------------------------
# fetch_full_text_json
# ---------------------------------------------------------------------------


def test_fetch_full_text_json_returns_originaltext_string():
    """When metadata response has originalText as a string, return it directly."""
    fake_meta = {
        "full-text-retrieval-response": {
            "originalText": "Abstract\n\nWe introduce CODEX...\n\nIntroduction\n\n...",
        }
    }
    client = ElsevierClient(api_key="fake-key")
    with patch.object(client, "fetch_metadata", return_value=fake_meta):
        text = client.fetch_full_text_json("10.1016/j.cell.2018.07.010")
    assert "We introduce CODEX" in text
    assert text.startswith("Abstract")


def test_fetch_full_text_json_handles_dollar_dict_shape():
    """Some Elsevier responses wrap originalText as ``{"$": "..."}``."""
    fake_meta = {
        "full-text-retrieval-response": {
            "originalText": {"$": "Body text from dollar-dict shape"},
        }
    }
    client = ElsevierClient(api_key="fake-key")
    with patch.object(client, "fetch_metadata", return_value=fake_meta):
        text = client.fetch_full_text_json("10.1/X")
    assert text == "Body text from dollar-dict shape"


def test_fetch_full_text_json_returns_empty_when_metadata_unauthorized():
    """fetch_metadata returning None (e.g. 403) yields empty string, not crash."""
    client = ElsevierClient(api_key="bad-key")
    with patch.object(client, "fetch_metadata", return_value=None):
        text = client.fetch_full_text_json("10.1/anything")
    assert text == ""


def test_fetch_full_text_json_returns_empty_when_field_missing():
    """Metadata that exists but has no originalText yields empty string."""
    fake_meta = {"full-text-retrieval-response": {"coredata": {"prism:doi": "..."}}}
    client = ElsevierClient(api_key="fake-key")
    with patch.object(client, "fetch_metadata", return_value=fake_meta):
        text = client.fetch_full_text_json("10.1/X")
    assert text == ""


# ---------------------------------------------------------------------------
# SummarizationTask.text_path auto-detection
# ---------------------------------------------------------------------------


def _make_minimal_corpus() -> Corpus:
    seed = Paper(
        title="Goltsev",
        authors=["Goltsev Y"],
        year=2018,
        journal="Cell",
        doi="10.1016/j.cell.2018.07.010",
        source_api="pubmed",
    )
    corpus = Corpus(
        topic="t", seeds=[seed], papers={seed.doi: seed}
    )
    compute_metrics(corpus)
    return corpus


def test_prepare_summary_task_picks_up_sibling_text_file(tmp_path: Path):
    """When ``<pdf>.elsevier.txt`` exists next to the PDF, ``text_path`` is set."""
    pdf = tmp_path / "10.1016_j.cell.2018.07.010.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    sibling = tmp_path / "10.1016_j.cell.2018.07.010.elsevier.txt"
    sibling.write_text("Full clean Elsevier text body...")

    corpus = _make_minimal_corpus()
    task = prepare_summary_task(
        doi="10.1016/j.cell.2018.07.010",
        pdf_path=pdf,
        paper_metadata={
            "title": "Goltsev",
            "authors": ["Goltsev Y"],
            "year": 2018,
            "journal": "Cell",
        },
        corpus_metrics=corpus.metrics,
        corpus=corpus,
        crossref_refs_missing=False,
        kb_root=tmp_path,
    )

    assert task.text_path is not None
    assert task.text_path == sibling
    # Prompt mentions the text file
    assert "elsevier.txt" in task.prompt
    assert "Prefer reading this file" in task.prompt


def test_prepare_summary_task_no_text_file_leaves_text_path_none(
    tmp_path: Path,
):
    """When the sibling .elsevier.txt is absent, ``text_path`` stays None."""
    pdf = tmp_path / "10.1016_j.cell.2018.07.010.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    # No sibling .elsevier.txt

    corpus = _make_minimal_corpus()
    task = prepare_summary_task(
        doi="10.1016/j.cell.2018.07.010",
        pdf_path=pdf,
        paper_metadata={
            "title": "Goltsev",
            "authors": ["Goltsev Y"],
            "year": 2018,
            "journal": "Cell",
        },
        corpus_metrics=corpus.metrics,
        corpus=corpus,
        crossref_refs_missing=False,
        kb_root=tmp_path,
    )

    assert task.text_path is None
    assert "elsevier.txt" not in task.prompt


def test_prepare_summary_task_skips_empty_text_file(tmp_path: Path):
    """A zero-byte .elsevier.txt sibling is treated as absent."""
    pdf = tmp_path / "10.1016_j.cell.2018.07.010.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    sibling = tmp_path / "10.1016_j.cell.2018.07.010.elsevier.txt"
    sibling.write_bytes(b"")  # empty

    corpus = _make_minimal_corpus()
    task = prepare_summary_task(
        doi="10.1016/j.cell.2018.07.010",
        pdf_path=pdf,
        paper_metadata={
            "title": "Goltsev",
            "authors": ["Goltsev Y"],
            "year": 2018,
            "journal": "Cell",
        },
        corpus_metrics=corpus.metrics,
        corpus=corpus,
        crossref_refs_missing=False,
        kb_root=tmp_path,
    )

    assert task.text_path is None
