from __future__ import annotations

from vaultlab.figures.contract import FigureContract
from vaultlab.figures.tournament import TournamentResult
from vaultlab.recombine import (
    recombine,
    recombine_figure_contracts,
    recombine_top_two,
)


def test_recombine_merges_dicts_and_records_parents() -> None:
    result = recombine(
        {"a": 1},
        {"b": 2},
        combine_fn=lambda parent_a, parent_b: parent_a | parent_b,
        parent_a_id="alpha",
        parent_b_id="beta",
    )

    assert result.child == {"a": 1, "b": 2}
    assert result.parent_a_id == "alpha"
    assert result.parent_b_id == "beta"
    assert result.verified is None
    assert "alpha" in result.rationale
    assert "beta" in result.rationale


def test_recombine_accepts_ok_dict_verdict() -> None:
    result = recombine(
        {"a": 1},
        {"b": 2},
        combine_fn=lambda parent_a, parent_b: parent_a | parent_b,
        verify_fn=lambda child: {"ok": "a" in child and "b" in child},
    )

    assert result.child == {"a": 1, "b": 2}
    assert result.verdict == {"ok": True}
    assert result.verified is True


def test_recombine_accept_fn_overrides_default_verdict_acceptance() -> None:
    result = recombine(
        {"score": 0.2},
        {"score": 0.9},
        combine_fn=lambda parent_a, parent_b: {"score": max(parent_a["score"], parent_b["score"])},
        verify_fn=lambda child: {"score": child["score"]},
        accept_fn=lambda verdict: verdict["score"] >= 0.8,
    )

    assert result.child == {"score": 0.9}
    assert result.verified is True


def test_recombine_verify_exception_returns_failed_result_without_crashing() -> None:
    def verify(_child: dict[str, int]) -> dict[str, bool]:
        raise RuntimeError("verifier unavailable")

    result = recombine(
        {"a": 1},
        {"b": 2},
        combine_fn=lambda parent_a, parent_b: parent_a | parent_b,
        verify_fn=verify,
    )

    assert result.child == {"a": 1, "b": 2}
    assert result.verified is False
    assert result.verdict is None
    assert "verifier unavailable" in result.rationale


def test_recombine_figure_contracts_unions_evidence_and_carries_max_dpi() -> None:
    parent_a = FigureContract(
        conclusion="A short claim.",
        evidence_chain={"a": "UMAP shows clusters", "shared": "parent a evidence"},
        dpi=300,
        notes="first draft",
    )
    parent_b = FigureContract(
        conclusion="A longer hedged claim is consistent with stronger support.",
        evidence_chain={"b": "Bar plot quantifies effect", "shared": "parent b evidence"},
        dpi=900,
        notes="second draft",
    )

    child = recombine_figure_contracts(parent_a, parent_b)

    assert child.evidence_chain == {
        "a": "UMAP shows clusters",
        "shared": "parent b evidence",
        "b": "Bar plot quantifies effect",
    }
    assert child.conclusion == parent_b.conclusion
    assert child.dpi == 900
    assert "first draft" in child.notes
    assert "second draft" in child.notes
    assert "shared" in child.notes


def test_recombine_top_two_uses_tournament_ranking_and_handles_small_rankings() -> None:
    tournament = TournamentResult(
        ranking=[("winner", 2.0), ("runner_up", 1.0), ("third", 0.0)],
        matches=[],
        winner_id="winner",
        n_candidates=3,
    )
    candidates = {
        "winner": {"winner": True},
        "runner_up": {"runner_up": True},
        "third": {"third": True},
    }

    result = recombine_top_two(
        tournament,
        candidates,
        combine_fn=lambda parent_a, parent_b: parent_a | parent_b,
        verify_fn=lambda child: {"ok": set(child) == {"winner", "runner_up"}},
    )
    too_small = recombine_top_two(
        TournamentResult(ranking=[("only", 0.0)], matches=[], winner_id="only", n_candidates=1),
        {"only": {"only": True}},
        combine_fn=lambda parent_a, parent_b: parent_a | parent_b,
    )

    assert result is not None
    assert result.child == {"winner": True, "runner_up": True}
    assert result.parent_a_id == "winner"
    assert result.parent_b_id == "runner_up"
    assert result.verified is True
    assert too_small is None
