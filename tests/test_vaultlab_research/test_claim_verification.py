"""Tests for the claim-verification module (mirror of the figure-understanding
verify pattern, applied to text claims in arc paragraphs)."""

from __future__ import annotations

from vaultlab.research.claim_verification import (
    VALID_VERDICTS,
    ClaimVerificationTask,
    claim_verification_response_schema,
    extract_claims_from_paragraph,
    prepare_claim_verification_task,
    render_verifications_from_response,
    verify_paragraph_claims,
)

# ---------------------------------------------------------------------------
# extract_claims_from_paragraph
# ---------------------------------------------------------------------------


def test_extract_claims_handles_empty_paragraph():
    assert extract_claims_from_paragraph("") == []
    assert extract_claims_from_paragraph("   \n  ") == []


def test_extract_claims_splits_on_sentence_boundaries():
    text = "First claim. Second claim. Third claim."
    out = extract_claims_from_paragraph(text)
    # Three sentences, three claims
    assert len(out) == 3
    assert out[0].text.startswith("First")
    assert out[2].text.startswith("Third")


def test_extract_claims_pulls_dois_from_wikilinks():
    text = (
        "[[10.1016_j.cell.2018.07.010|Goltsev 2018]] introduced CODEX. "
        "[[10.1038_nmeth.2869|Giesen 2014]] introduced IMC."
    )
    out = extract_claims_from_paragraph(text)
    assert len(out) == 2
    assert "10.1016/j.cell.2018.07.010" in out[0].cited_dois
    assert "10.1038/nmeth.2869" in out[1].cited_dois


def test_extract_claims_handles_multiple_dois_in_one_sentence():
    text = (
        "Both [[10.1038_nmeth.2869|Giesen 2014]] and [[10.1038_nm.3488|Angelo 2014]] "
        "introduced mass-cytometry imaging."
    )
    out = extract_claims_from_paragraph(text)
    assert len(out) == 1
    assert set(out[0].cited_dois) == {
        "10.1038/nmeth.2869",
        "10.1038/nm.3488",
    }


def test_extract_claims_handles_pdf_extension_in_slug():
    """Defensive: wikilink slugs that accidentally carry .pdf get stripped."""
    text = "[[10.7554_elife-31657.pdf|Lin 2018]] released t-CyCIF."
    out = extract_claims_from_paragraph(text)
    assert len(out) == 1
    assert "10.7554/elife-31657" in out[0].cited_dois


def test_extract_claims_position_indices():
    out = extract_claims_from_paragraph("A. B. C.")
    assert [c.position for c in out] == [0, 1, 2]


# ---------------------------------------------------------------------------
# prepare_claim_verification_task
# ---------------------------------------------------------------------------


def test_prepare_task_embeds_paragraph_and_summaries():
    paragraph = "[[10.1_X|Smith 2020]] reported 85:1 SNR."
    summaries = {
        "10.1/X": "TL;DR: signal-to-noise ratio is ~85:1 [p2].",
    }
    task = prepare_claim_verification_task(
        paragraph=paragraph,
        section_id="history",
        cited_summaries=summaries,
    )
    assert task.paragraph == paragraph
    assert task.section_id == "history"
    assert "85:1" in task.prompt
    # Summary text appears in the prompt body
    assert "[p2]" in task.prompt
    # Claims extracted
    assert len(task.claims) == 1
    assert task.claims[0].cited_dois == ("10.1/x",)


def test_prepare_task_lowercases_and_trims_summary_keys():
    summaries = {"  10.1/Foo  ": "TL;DR: blah"}
    task = prepare_claim_verification_task(
        paragraph="t.", section_id="sota", cited_summaries=summaries
    )
    # Key is lowercased + stripped
    assert "10.1/foo" in task.cited_summaries


def test_prepare_task_with_empty_summaries():
    """When no summaries supplied, prompt notes claims will be UNVERIFIABLE."""
    task = prepare_claim_verification_task(
        paragraph="A bold claim.",
        section_id="history",
        cited_summaries={},
    )
    assert "no Tier-A summaries" in task.prompt or "UNVERIFIABLE" in task.prompt


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def test_response_schema_lists_all_valid_verdicts():
    schema = claim_verification_response_schema()
    items = schema["properties"]["verifications"]["items"]
    enum = items["properties"]["verdict"]["enum"]
    assert sorted(enum) == sorted(VALID_VERDICTS)


def test_response_schema_requires_position_and_verdict():
    schema = claim_verification_response_schema()
    items = schema["properties"]["verifications"]["items"]
    assert set(items["required"]) == {"position", "verdict"}


# ---------------------------------------------------------------------------
# render_verifications_from_response
# ---------------------------------------------------------------------------


def _task_with_two_claims() -> ClaimVerificationTask:
    return prepare_claim_verification_task(
        paragraph=(
            "[[10.1_X|Smith 2020]] showed 85:1 SNR. [[10.1_Y|Jones 2021]] reproduced this finding."
        ),
        section_id="history",
        cited_summaries={
            "10.1/x": "TL;DR: SNR is ~85:1 [p2].",
            "10.1/y": "TL;DR: confirms ~85:1 SNR [p3].",
        },
    )


def test_render_supported_verdict():
    task = _task_with_two_claims()
    response = {
        "verifications": [
            {
                "position": 0,
                "verdict": "supported",
                "evidence": "SNR is ~85:1 [p2]",
                "evidence_doi": "10.1/x",
            },
            {
                "position": 1,
                "verdict": "supported",
                "evidence": "confirms ~85:1 SNR [p3]",
                "evidence_doi": "10.1/y",
            },
        ]
    }
    result = render_verifications_from_response(response, task)
    assert len(result.verifications) == 2
    assert all(v.verdict == "supported" for v in result.verifications)
    assert result.verdict_counts["supported"] == 2
    assert not result.any_revisions_suggested


def test_render_partial_verdict_with_revision_suggestion():
    task = _task_with_two_claims()
    response = {
        "verifications": [
            {
                "position": 0,
                "verdict": "partial",
                "evidence": "shows 85:1 ratio in best case",
                "evidence_doi": "10.1/x",
                "revision_suggestion": "Soften to 'achieves up to 85:1 SNR'",
            },
        ]
    }
    result = render_verifications_from_response(response, task)
    # Position 0 = partial, position 1 = unverifiable (silence)
    assert result.verifications[0].verdict == "partial"
    assert result.verifications[1].verdict == "unverifiable"
    assert result.any_revisions_suggested is True
    assert result.verifications[0].revision_suggestion.startswith("Soften")


def test_render_drops_invalid_verdict():
    task = _task_with_two_claims()
    response = {
        "verifications": [
            {
                "position": 0,
                "verdict": "MAYBE",  # not in VALID_VERDICTS
                "evidence": "...",
            },
        ]
    }
    result = render_verifications_from_response(response, task)
    # Invalid verdict at position 0 → dropped, position 0 falls back to unverifiable
    assert result.verifications[0].verdict == "unverifiable"


def test_render_drops_unknown_position():
    task = _task_with_two_claims()
    response = {
        "verifications": [
            {
                "position": 99,  # not a real claim
                "verdict": "supported",
                "evidence": "...",
            },
        ]
    }
    result = render_verifications_from_response(response, task)
    # All claims fall back to unverifiable
    assert all(v.verdict == "unverifiable" for v in result.verifications)


def test_render_handles_none_response():
    task = _task_with_two_claims()
    result = render_verifications_from_response(None, task)
    assert all(v.verdict == "unverifiable" for v in result.verifications)


def test_render_handles_malformed_response():
    task = _task_with_two_claims()
    # Wrong shape — missing 'verifications' key
    result = render_verifications_from_response({"unexpected": "shape"}, task)
    assert all(v.verdict == "unverifiable" for v in result.verifications)


def test_render_silent_claim_marked_unverifiable():
    """Claims the verifier didn't return get auto-marked unverifiable."""
    task = _task_with_two_claims()
    response = {"verifications": []}  # verifier said nothing
    result = render_verifications_from_response(response, task)
    assert all(v.verdict == "unverifiable" for v in result.verifications)
    assert result.verdict_counts["unverifiable"] == 2


# ---------------------------------------------------------------------------
# verify_paragraph_claims (high-level helper)
# ---------------------------------------------------------------------------


def test_verify_paragraph_claims_no_callback_returns_unverifiable():
    """Without a callback, every claim is auto-marked unverifiable."""
    result = verify_paragraph_claims(
        paragraph="[[10.1_X|Smith]] said something.",
        section_id="history",
        cited_summaries={"10.1/x": "TL;DR: ..."},
    )
    assert all(v.verdict == "unverifiable" for v in result.verifications)


def test_verify_paragraph_claims_uses_callback_when_supplied():
    captured: list[ClaimVerificationTask] = []

    def cb(task: ClaimVerificationTask) -> dict:
        captured.append(task)
        return {
            "verifications": [
                {
                    "position": 0,
                    "verdict": "supported",
                    "evidence": "matches the summary",
                    "evidence_doi": "10.1/x",
                }
            ]
        }

    result = verify_paragraph_claims(
        paragraph="[[10.1_X|Smith]] said something.",
        section_id="history",
        cited_summaries={"10.1/x": "TL;DR: said something [p1]."},
        verifier_callback=cb,
    )
    assert len(captured) == 1
    assert result.verifications[0].verdict == "supported"


def test_verify_paragraph_claims_callback_exception_falls_back_unverifiable():
    """If the callback raises, the result is still well-formed (all unverifiable)."""

    def cb(task):
        raise RuntimeError("LLM down")

    result = verify_paragraph_claims(
        paragraph="A claim.",
        section_id="sota",
        cited_summaries={},
        verifier_callback=cb,
    )
    assert all(v.verdict == "unverifiable" for v in result.verifications)


# ---------------------------------------------------------------------------
# Real-world overclaim catch (the Schurch 2020 case Bobby flagged)
# ---------------------------------------------------------------------------


def test_catches_schurch_2020_style_overclaim():
    """The motivating example: paragraph cites a Tier-C paper that wasn't read,
    and the verifier marks the claim unverifiable rather than silently passing."""
    # Schurch 2020 was Tier-C in the CODEX run — no PDF, no summary.
    paragraph = (
        "[[10.1016_j.cell.2020.07.005|Schurch 2020]] showed cellular "
        "neighborhood structure predicts patient survival in colorectal "
        "cancer."
    )
    # No summary supplied for Schurch — Tier-C, we never read it.
    result = verify_paragraph_claims(
        paragraph=paragraph,
        section_id="development",
        cited_summaries={},  # the critical part: empty summary set
    )
    # The claim is unverifiable, not supported — the system flags it
    # rather than silently propagating.
    assert result.verifications[0].verdict == "unverifiable"
    assert result.verdict_counts["unverifiable"] == 1
