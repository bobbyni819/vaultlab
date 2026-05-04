"""Trial run for the adversarial picker meeting.

Builds a 5-paper synthetic corpus, defines a stub runner_callback that
emits canned analyst/critic/synthesizer outputs (no LLM), and prints
turn-by-turn output so we can see the meeting transcript.

Usage::

    python scripts/_trial_crosstalk_picker.py
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# ruff: noqa: E402
from vaultlab.research.picker import CandidatePaper
from vaultlab.workflows.crosstalk import adversarial_picker_meeting


def _candidates() -> list[CandidatePaper]:
    return [
        CandidatePaper(
            doi="10.1126/science.1225829",
            title="Programmable Cas9",
            authors=["Jinek M"],
            year=2012,
            journal="Science",
            abstract="Foundational programmable cleavage of dsDNA.",
            og_score=0.7,
            forward_influence=120,
            has_pdf=True,
        ),
        CandidatePaper(
            doi="10.1038/nature17946",
            title="Cytidine base editor",
            authors=["Komor AC"],
            year=2016,
            journal="Nature",
            abstract="Direct C->T conversion in genomic DNA.",
            og_score=0.45,
            forward_influence=70,
            has_pdf=True,
        ),
        CandidatePaper(
            doi="10.1038/nature24644",
            title="Adenine base editor",
            authors=["Gaudelli NM"],
            year=2017,
            journal="Nature",
            abstract="Direct A->G conversion in genomic DNA.",
            og_score=0.40,
            forward_influence=55,
            has_pdf=True,
        ),
        CandidatePaper(
            doi="10.1038/s41586-019-1711-4",
            title="Prime editor",
            authors=["Anzalone AV"],
            year=2019,
            journal="Nature",
            abstract="Search-and-replace genome editing.",
            og_score=0.30,
            forward_influence=30,
            has_pdf=True,
        ),
        CandidatePaper(
            doi="10.1038/s41587-022-09999-z",
            title="Off-topic application paper",
            authors=["Smith J"],
            year=2022,
            journal="Nat Biotech",
            abstract="A peripheral application using prior tools — high citation count for unrelated reasons.",
            og_score=0.25,
            forward_influence=80,
            has_pdf=False,
        ),
    ]


def _stub_runner(meeting, roles):
    """Canned outputs: analyst proposes 4, critic flags 1 off-topic, synthesizer drops it."""
    outputs: list[dict[str, Any]] = []
    for r in roles:
        if r.id == "synthesizer":
            payload = {
                "picks": [
                    {
                        "doi": "10.1126/science.1225829",
                        "rank": 1,
                        "rationale": "Foundational programmable cleavage paper.",
                    },
                    {
                        "doi": "10.1038/nature17946",
                        "rank": 2,
                        "rationale": "First cytidine base editor.",
                    },
                    {
                        "doi": "10.1038/nature24644",
                        "rank": 3,
                        "rationale": "First adenine base editor.",
                    },
                    {
                        "doi": "10.1038/s41586-019-1711-4",
                        "rank": 4,
                        "rationale": "Prime editing — major methodological extension.",
                    },
                ]
            }
            outputs.append({"output": json.dumps(payload, indent=2)})
        elif r.id == "literature_critic":
            outputs.append({
                "output": (
                    "I challenge the analyst's inclusion of "
                    "10.1038/s41587-022-09999-z — the abstract describes "
                    "a peripheral application; high citation count is a "
                    "deceptive signal here. Drop it. Add the analyst's "
                    "missing prime editing paper."
                )
            })
        else:
            outputs.append({
                "output": (
                    f"[{r.id}] proposed top-4 picks: jinek 2012, komor 2016, "
                    "gaudelli 2017, smith 2022 (high og_score)."
                )
            })
    return outputs


def main() -> int:
    print("=" * 72)
    print("Trial: adversarial_picker_meeting (synthetic 5-paper CRISPR corpus)")
    print("=" * 72)
    candidates = _candidates()
    abstracts_md = "\n\n".join(
        f"[{i+1}] {c.doi} {c.title} ({c.year}) — og={c.og_score:.2f}\n    {c.abstract}"
        for i, c in enumerate(candidates)
    )

    result = adversarial_picker_meeting(
        topic="CRISPR base editing",
        candidates=candidates,
        target_n=4,
        abstracts_md=abstracts_md,
        n_rounds=2,
        runner_callback=_stub_runner,
    )

    print(f"\nCrosstalk status: {result.crosstalk_status}")
    print(f"Runtime: {result.runtime_seconds:.2f}s")
    print(f"Total turns: {len(result.rounds)}")
    print()
    for i, turn in enumerate(result.rounds, 1):
        print("-" * 72)
        print(f"Turn {i}: {turn.role_id}")
        print("-" * 72)
        print(turn.output[:600])
        print()

    print("=" * 72)
    print("Synthesizer's final picks:")
    print("=" * 72)
    for pick in result.final_output.get("picks", []):
        print(
            f"  rank {pick.get('rank')}: {pick.get('doi')} — "
            f"{pick.get('rationale')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
