"""Tests for vaultlab.manuscript.respond_html."""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.manuscript.respond import (
    ActionType,
    CommentKind,
    ResponseLetter,
    ReviewerComment,
)
from vaultlab.manuscript.respond_html import (
    build_response_letter_html,
    write_response_letter_html,
)


@pytest.fixture
def letter() -> ResponseLetter:
    return ResponseLetter(
        reviewer=1,
        opening="We thank Reviewer 1 for the constructive comments.",
        comments=[
            ReviewerComment(
                stable_id="R1-C1",
                reviewer=1,
                quote="The sample size is underpowered.",
                kind=CommentKind.METHOD_CRITIQUE,
                action=ActionType.ACCEPT_ANALYSIS,
                evidence_ref="§Results, p.7 lines 12-18",
                response_text="We agree and have added a power analysis.",
            ),
            ReviewerComment(
                stable_id="R1-C2",
                reviewer=1,
                quote="Should run KO mouse experiment.",
                kind=CommentKind.MISSING_EXPERIMENT,
                action=ActionType.AUTHOR_INPUT_NEEDED,
                open_question="Is the KO line available in the 8-week revision window?",
            ),
            ReviewerComment(
                stable_id="R1-C3",
                reviewer=1,
                quote="The claim is too strong.",
                kind=CommentKind.OVERCLAIM,
                action=ActionType.SOFTEN_CLAIM,
                evidence_ref="§Discussion, p.14 lines 8-15",
                response_text="We have softened from 'causes' to 'is associated with'.",
            ),
        ],
        closing="We hope this addresses all concerns.",
    )


def test_renders_basic_letter(letter):
    html = build_response_letter_html(letter)
    assert "<!doctype html>" in html
    assert "Response to Reviewer 1" in html
    assert "3 comments" in html


def test_open_questions_flagged(letter):
    html = build_response_letter_html(letter)
    assert "1 need author input" in html
    assert "AUTHOR INPUT NEEDED" in html
    assert "8-week revision window" in html


def test_comment_cards_render(letter):
    html = build_response_letter_html(letter)
    assert "R1-C1" in html
    assert "R1-C2" in html
    assert "R1-C3" in html
    assert "underpowered" in html
    assert "softened from" in html


def test_evidence_refs_rendered(letter):
    html = build_response_letter_html(letter)
    assert "§Results, p.7 lines 12-18" in html
    assert "§Discussion, p.14 lines 8-15" in html


def test_action_badges_per_card(letter):
    html = build_response_letter_html(letter)
    assert "ACCEPT_ANALYSIS" in html
    assert "AUTHOR_INPUT_NEEDED" in html
    assert "SOFTEN_CLAIM" in html


def test_filter_bar_per_action(letter):
    html = build_response_letter_html(letter)
    assert 'data-filter="ACCEPT_ANALYSIS"' in html
    assert 'data-filter="AUTHOR_INPUT_NEEDED"' in html
    assert 'data-filter="SOFTEN_CLAIM"' in html


def test_opening_and_closing_sections(letter):
    html = build_response_letter_html(letter)
    assert "Opening" in html
    assert "We thank Reviewer 1" in html
    assert "Closing" in html
    assert "We hope this addresses" in html


def test_accepts_dict_input():
    """Should accept dict-shaped letters too."""
    d = {
        "reviewer": 2,
        "opening": "",
        "closing": "",
        "comments": [
            {
                "stable_id": "R2-C1",
                "quote": "q",
                "kind": "method_question",
                "action": "ACCEPT_TEXT",
                "evidence_ref": "p.5",
                "response_text": "r",
            }
        ],
    }
    html = build_response_letter_html(d)
    assert "Response to Reviewer 2" in html
    assert "R2-C1" in html


def test_empty_letter():
    html = build_response_letter_html(ResponseLetter(reviewer=1))
    assert "0 comments" in html
    assert "No comments" in html


def test_copy_actions_present(letter):
    html = build_response_letter_html(letter)
    # Copy quote / Copy response buttons
    assert "Copy quote" in html
    assert "Copy response" in html


def test_xss_safe_against_evil_response_text():
    cm = ReviewerComment(
        stable_id="R1-C1",
        reviewer=1,
        quote="<script>alert(1)</script>",
        kind=CommentKind.METHOD_QUESTION,
        action=ActionType.ACCEPT_TEXT,
        response_text="<img src=x onerror=alert(1)>",
    )
    letter_obj = ResponseLetter(reviewer=1, comments=[cm])
    html = build_response_letter_html(letter_obj)
    assert "<script>alert(1)</script>" not in html
    assert "<img src=x onerror" not in html
    assert "&lt;script&gt;" in html


def test_write_response_letter_html(tmp_path: Path, letter):
    out = tmp_path / "response.html"
    written = write_response_letter_html(out, letter)
    assert written == out
    assert out.exists()
