"""Tests for claim-ledger to deck figure sync."""

from __future__ import annotations

from vaultlab.manuscript.claim_ledger import ClaimLedger
from vaultlab.manuscript.deck_sync import figure_key, sync_claims_to_deck
from vaultlab.slides.deck import Deck, DeckPlan, DeckSlide, Slide


def _ledger() -> ClaimLedger:
    ledger = ClaimLedger()
    ledger.add_claim("C1", "R5 supports the main result.")
    ledger.add_claim("C2", "R6 supports the secondary result.")
    ledger.link_figure("C1", "figR5")
    ledger.link_figure("C2", "figR6")
    return ledger


def test_sync_claims_to_deck_flags_missing_claim_figure_and_orphan_deck_figure() -> None:
    deck = Deck(
        title="Demo",
        slides=[
            Slide(layout="figure_with_caption", figure_path="out/figR5.png"),
            Slide(layout="figure_with_caption", figure_path="out/figX.png"),
        ],
    )

    report = sync_claims_to_deck(_ledger(), deck)

    assert report.ok is False
    assert report.matched == ["r5"]
    assert report.claim_figures == ["r5", "r6"]
    assert report.deck_figures == ["r5", "x"]
    assert [problem.kind for problem in report.problems] == [
        "claim_figure_missing_from_deck",
        "deck_figure_not_in_claims",
    ]
    assert report.problems[0].figure == "r6"
    assert report.problems[0].claim_ids == ["C2"]
    assert report.problems[1].figure == "x"
    assert "r6" in report.to_markdown()
    assert report.to_dict()["matched"] == ["r5"]


def test_sync_claims_to_deck_reports_ok_for_fully_synced_deck() -> None:
    deck = Deck(
        title="Demo",
        slides=[
            Slide(layout="figure_with_caption", figure_path="out/figR5.png"),
            Slide(layout="figure_with_caption", figure_path="out/figR6.png"),
        ],
    )

    report = sync_claims_to_deck(_ledger(), deck)

    assert report.ok is True
    assert report.problems == []
    assert report.matched == ["r5", "r6"]


def test_sync_claims_to_deck_reads_deck_plan_figure_path_content() -> None:
    plan = DeckPlan(
        title="Demo",
        subtitle="",
        speaker="",
        affiliation="",
        slides=[
            DeckSlide(
                kind="figure",
                title="R5",
                content={"figure_path": "out/figR5.png"},
            ),
            DeckSlide(
                kind="figure",
                title="R6",
                content={"figure_path": "out/figR6.png"},
            ),
        ],
    )

    report = sync_claims_to_deck(_ledger(), plan)

    assert report.ok is True
    assert report.deck_figures == ["r5", "r6"]


def test_figure_key_normalizes_path_stem_case_and_figure_prefix() -> None:
    assert figure_key("out/FigR5.PNG") == "r5"
    assert figure_key("FigureR6") == "r6"
    assert figure_key("r7") == "r7"


def test_sync_claims_to_deck_tolerates_odd_deck_shape_with_extra_figures() -> None:
    report = sync_claims_to_deck(_ledger(), object(), extra_deck_figures=["out/figR5.png"])

    assert report.ok is False
    assert report.deck_figures == ["r5"]
    assert report.matched == ["r5"]
    assert len(report.problems) == 1
    assert report.problems[0].kind == "claim_figure_missing_from_deck"
    assert report.problems[0].figure == "r6"
