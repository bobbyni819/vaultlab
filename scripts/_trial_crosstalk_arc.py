"""Trial run for the adversarial arc-generation meeting.

Builds 5 synthetic per-paper summaries spanning history/development/sota,
runs the adversarial arc meeting with a stub runner, prints the
synthesizer's final 3-paragraph arc.

Usage::

    python scripts/_trial_crosstalk_arc.py
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
from vaultlab.research.summarize import PaperSummary
from vaultlab.workflows.crosstalk import adversarial_arc_meeting


def _summaries() -> dict[str, PaperSummary]:
    return {
        "10.1126/science.1225829": PaperSummary(
            doi="10.1126/science.1225829",
            title="Programmable Cas9",
            authors=["Jinek M"],
            year=2012,
            year_bucket="history",
            tier="A",
            og_score=0.70,
            forward_influence=120,
            tldr="Founded programmable RNA-guided cleavage. [p1]",
            key_findings=["dual-RNA guide [p3]"],
        ),
        "10.1038/nature17946": PaperSummary(
            doi="10.1038/nature17946",
            title="Cytidine base editor",
            authors=["Komor AC"],
            year=2016,
            year_bucket="development",
            tier="A",
            og_score=0.45,
            forward_influence=70,
            tldr="C->T conversion at target loci. [p1]",
            key_findings=["37% editing efficiency [p4]"],
        ),
        "10.1038/nature24644": PaperSummary(
            doi="10.1038/nature24644",
            title="Adenine base editor",
            authors=["Gaudelli NM"],
            year=2017,
            year_bucket="development",
            tier="A",
            og_score=0.40,
            forward_influence=55,
            tldr="A->G conversion expands the base-editing toolkit. [p1]",
            key_findings=["50% editing efficiency in HEK [p3]"],
        ),
        "10.1038/s41586-019-1711-4": PaperSummary(
            doi="10.1038/s41586-019-1711-4",
            title="Prime editor",
            authors=["Anzalone AV"],
            year=2019,
            year_bucket="sota",
            tier="A",
            og_score=0.30,
            forward_influence=30,
            tldr="Search-and-replace genome editing. [p1]",
            key_findings=["89 mutations installed [p2]"],
        ),
        "10.1038/s41586-022-04835-6": PaperSummary(
            doi="10.1038/s41586-022-04835-6",
            title="Twin prime editing",
            authors=["Anzalone AV"],
            year=2022,
            year_bucket="sota",
            tier="A",
            og_score=0.20,
            forward_influence=15,
            tldr="Bidirectional prime editing for larger insertions. [p1]",
            key_findings=["10 kb insertion [p4]"],
        ),
    }


def _stub_runner(meeting, roles):
    outputs: list[dict[str, Any]] = []
    for r in roles:
        if r.id == "synthesizer":
            payload = {
                "history": (
                    "The lineage opens with [[10.1126_science.1225829|Jinek 2012]]'s "
                    "demonstration of programmable RNA-guided DNA cleavage."
                ),
                "development": (
                    "[[10.1038_nature17946|Komor 2016]] introduced cytidine base "
                    "editing, and [[10.1038_nature24644|Gaudelli 2017]] extended "
                    "the toolkit to adenine."
                ),
                "sota": (
                    "[[10.1038_s41586-019-1711-4|Anzalone 2019]] introduced prime "
                    "editing; [[10.1038_s41586-022-04835-6|Anzalone 2022]] then "
                    "scaled it to multi-kilobase edits."
                ),
            }
            outputs.append({"output": json.dumps(payload, indent=2)})
        elif r.id == "methods_critic":
            outputs.append({
                "output": (
                    "Watch for overclaiming the chronology — Komor 2016 didn't "
                    "'lead to' Gaudelli 2017 in any causal sense; both built "
                    "directly on dCas9 fusions. Soften."
                )
            })
        else:
            outputs.append({"output": f"[{r.id}] commentary on bucketed corpus."})
    return outputs


def main() -> int:
    print("=" * 72)
    print("Trial: adversarial_arc_meeting (5-paper CRISPR base-editing corpus)")
    print("=" * 72)

    result = adversarial_arc_meeting(
        topic="CRISPR base editing",
        summaries=_summaries(),
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
        print(turn.output[:500])
        print()

    print("=" * 72)
    print("Synthesizer's final arc paragraphs:")
    print("=" * 72)
    fo = result.final_output
    for k in ("history", "development", "sota"):
        print(f"\n## {k.upper()}\n{fo.get(k, '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
