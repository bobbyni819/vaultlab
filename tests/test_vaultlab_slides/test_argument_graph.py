"""Tests for vaultlab.slides.argument_graph."""

from __future__ import annotations

from pathlib import Path

from vaultlab.slides.argument_graph import (
    render_argument_graph,
    write_argument_graph,
)


def _mk_plan() -> dict:
    return {
        "title": "Test deck",
        "topic": "test",
        "author": "Tester",
        "slides": [
            {
                "type": "title",
                "title": "Test deck",
                "speaker_notes": {
                    "hook": "Why this matters.",
                    "key_claim": "We will show three things.",
                    "transition": "Outline first.",
                },
            },
            {
                "type": "figure",
                "title": "X causes Y because of Z",
                "speaker_notes": {
                    "hook": "What's the mechanism?",
                    "key_claim": "Z is the load-bearing piece.",
                    "evidence": "Fig 2D shows the dose-response.",
                    "key_terms": ["X", "Y", "Z"],
                    "transition": "Now what about W?",
                },
            },
            {
                "type": "text",
                "title": "Take-aways",
                "speaker_notes": {},  # nothing attached
            },
        ],
    }


def test_render_includes_all_slides():
    md = render_argument_graph(_mk_plan())
    assert "Slide 1 — Test deck" in md
    assert "Slide 2 — X causes Y because of Z" in md
    assert "Slide 3 — Take-aways" in md


def test_render_includes_mental_map_fields():
    md = render_argument_graph(_mk_plan())
    assert "**Hook**: What's the mechanism?" in md
    assert "**Key claim**: Z is the load-bearing piece." in md
    assert "**Evidence**: Fig 2D shows the dose-response." in md
    assert "**Key terms**: X, Y, Z" in md
    assert "**Transition**: Now what about W?" in md


def test_render_marks_slides_without_notes():
    md = render_argument_graph(_mk_plan())
    assert "(no speaker notes attached)" in md


def test_render_includes_deck_metadata():
    md = render_argument_graph(_mk_plan())
    assert "Test deck" in md
    assert "Topic: `test`" in md
    assert "Speaker: `Tester`" in md


def test_render_handles_empty_plan():
    md = render_argument_graph({"slides": []})
    assert "Slide 1" not in md
    assert "Generated" in md


def test_write_creates_sidecar(tmp_path):
    deck = tmp_path / "deck.pptx"
    deck.write_bytes(b"fake")
    out = write_argument_graph(_mk_plan(), deck)
    assert out.exists()
    assert out.suffix == ".md"
    assert out.name == "deck.argument-graph.md"
    content = out.read_text(encoding="utf-8")
    assert "Test deck" in content
