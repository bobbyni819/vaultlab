"""Tests for vaultlab.manuscript.respond."""

from __future__ import annotations

from vaultlab.manuscript.respond import (
    ActionType,
    CommentKind,
    ResponseLetter,
    ReviewerComment,
    classify_comment,
    parse_reviewer_block,
    render_response_letter,
    stable_id,
    suggest_action,
)


def test_stable_id_format():
    assert stable_id(1, 1) == "R1-C1"
    assert stable_id(3, 12) == "R3-C12"


def test_classify_missing_experiment():
    assert (
        classify_comment("The authors should perform a knockout experiment.")
        == CommentKind.MISSING_EXPERIMENT
    )


def test_classify_overclaim():
    assert (
        classify_comment("This claim is too strong; the evidence does not support it.")
        == CommentKind.OVERCLAIM
    )


def test_classify_missing_citation():
    assert (
        classify_comment("The authors miss the important reference of Park 2023.")
        == CommentKind.MISSING_CITATION
    )


def test_classify_method_critique():
    assert classify_comment("The sample size n=3 is underpowered.") == CommentKind.METHOD_CRITIQUE


def test_classify_positive():
    assert classify_comment("This is excellent work.") == CommentKind.POSITIVE


def test_classify_falls_back_to_method_question():
    assert classify_comment("Just a generic statement.") == CommentKind.METHOD_QUESTION


def test_suggest_action_per_kind():
    assert suggest_action(CommentKind.OVERCLAIM) == ActionType.SOFTEN_CLAIM
    assert suggest_action(CommentKind.MISSING_EXPERIMENT) == ActionType.AUTHOR_INPUT_NEEDED
    assert suggest_action(CommentKind.MISSING_CITATION) == ActionType.ACCEPT_CITATION


def test_parse_reviewer_block_numbered():
    block = """
    1. The authors should clarify the n in Fig 2c.
    2. The claim of "novel mechanism" is too strong.
    3. Missing citation of Smith 2020.
    """
    comments = parse_reviewer_block(block, reviewer_index=2)
    assert len(comments) == 3
    assert comments[0].stable_id == "R2-C1"
    assert comments[1].stable_id == "R2-C2"
    assert comments[1].kind == CommentKind.OVERCLAIM
    assert comments[2].kind == CommentKind.MISSING_CITATION


def test_parse_reviewer_block_with_comment_prefix():
    block = """
    Comment 1: The figure quality is low.
    Comment 2: The sample size needs justification.
    """
    comments = parse_reviewer_block(block, reviewer_index=1)
    assert len(comments) == 2
    assert comments[0].kind == CommentKind.PRESENTATION


def test_render_response_letter():
    letter = ResponseLetter(
        reviewer=1,
        opening="We thank the reviewer for the constructive comments.",
        comments=[
            ReviewerComment(
                stable_id="R1-C1",
                reviewer=1,
                quote="The sample size is underpowered.",
                kind=CommentKind.METHOD_CRITIQUE,
                action=ActionType.ACCEPT_ANALYSIS,
                evidence_ref="§Results, p.7 lines 12-18",
                response_text="We agree and have added a power analysis showing n=8 detects 0.5 SD with 80% power.",
            ),
            ReviewerComment(
                stable_id="R1-C2",
                reviewer=1,
                quote="Should run KO mouse experiment.",
                kind=CommentKind.MISSING_EXPERIMENT,
                action=ActionType.AUTHOR_INPUT_NEEDED,
                open_question="Do we have a KO line accessible within the 8-week revision window?",
            ),
        ],
        closing="Thank you for your time.",
    )
    md = render_response_letter(letter)
    assert "# Response to Reviewer 1" in md
    assert "### R1-C1" in md
    assert "### R1-C2" in md
    assert "**Action:** `ACCEPT_ANALYSIS`" in md
    assert "§Results, p.7 lines 12-18" in md
    assert "AUTHOR INPUT NEEDED" in md
    assert "8-week revision window" in md
    assert "Thank you for your time." in md
