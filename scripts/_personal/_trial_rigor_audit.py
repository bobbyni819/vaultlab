"""Trial run for rigor_audit on a synthetic deck-text input.

Builds a fake deck-flatten-text containing a couple of intentionally
broken claims, runs rigor_audit with a stub auditor that flags them,
and prints the structured fix-list.

Usage::

    python scripts/_trial_rigor_audit.py
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
from vaultlab.workflows.crosstalk import rigor_audit


SYNTHETIC_DECK_TEXT = """\
# CRISPR base editing — journal club deck

## [title] CRISPR base editing
Speaker: Bobby

## [text] Foundational findings
- Jinek 2012 [[10.1126_science.1225829|Jinek 2012]] showed dual-RNA guides [p3]
- Smith 2099 conclusively proved that base editing is risk-free [p99]

## [text] Recent developments
- Komor 2016 [[10.1038_nature17946|Komor 2016]] reports 37% efficiency [p4]
- An undocumented paper claims revolutionary results without citation
"""


def _summaries() -> dict[str, PaperSummary]:
    return {
        "10.1126/science.1225829": PaperSummary(
            doi="10.1126/science.1225829",
            title="Programmable Cas9",
            authors=["Jinek M"],
            year=2012,
            tier="A",
            tldr="Founded programmable cleavage.",
            key_findings=["dual-RNA guide [p3]"],
        ),
        "10.1038/nature17946": PaperSummary(
            doi="10.1038/nature17946",
            title="Cytidine base editor",
            authors=["Komor AC"],
            year=2016,
            tier="A",
            tldr="C->T conversion at target loci.",
            key_findings=["37% editing efficiency [p4]"],
        ),
    }


def _stub_auditor(meeting, roles):
    """Returns fix-list for the two intentional issues."""
    payload = {
        "passed": False,
        "issues": [
            {
                "loc": "Foundational findings — Smith 2099 line",
                "severity": "blocker",
                "kind": "ungrounded_claim",
                "fix": (
                    "Smith 2099 has no [[wikilink]] target in Wiki/Summaries; "
                    "remove the claim or replace with a grounded citation."
                ),
            },
            {
                "loc": "Foundational findings — Smith 2099 line",
                "severity": "major",
                "kind": "overclaim",
                "fix": (
                    "Drop 'conclusively proved ... risk-free' — language "
                    "exceeds evidence tier; nothing in the corpus supports it."
                ),
            },
            {
                "loc": "Recent developments — undocumented paper line",
                "severity": "blocker",
                "kind": "ungrounded_claim",
                "fix": "Cite a real paper or remove the bullet entirely.",
            },
        ],
    }
    return [{"output": json.dumps(payload, indent=2)}]


def main() -> int:
    print("=" * 72)
    print("Trial: rigor_audit on synthetic deck text with intentional issues")
    print("=" * 72)
    print()
    print("Document under audit:")
    print("-" * 72)
    print(SYNTHETIC_DECK_TEXT)

    result = rigor_audit(
        document=SYNTHETIC_DECK_TEXT,
        summaries=_summaries(),
        audit_kind="deck",
        runner_callback=_stub_auditor,
    )

    print()
    print("=" * 72)
    print(f"Audit result: passed={result['passed']}")
    print("=" * 72)
    for i, issue in enumerate(result["issues"], 1):
        print(
            f"  [{i}] severity={issue.get('severity')} "
            f"kind={issue.get('kind')}\n"
            f"      loc: {issue.get('loc')}\n"
            f"      fix: {issue.get('fix')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
