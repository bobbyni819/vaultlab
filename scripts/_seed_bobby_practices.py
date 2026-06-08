"""Seed Bobby's writing-style + PDF-citation-grounding practices into user_memory.

One-time seed. Mirrors scripts/_save_figure_decision_tree.py. The canonical, fuller
source of truth is docs/writing-and-citation-practices.md; these two memory entries are
the short, always-surfaced reminders that recall_all() loads at session start.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vaultlab.context.user_memory import remember


def main() -> None:
    remember(
        category="feedback",
        name="thesis-writing-style",
        description="Bobby's hard writing rules for thesis/proposal/grant prose; US English, no em-dashes/arrows/filler, anti-AI-tell flow.",
        content=(
            "Apply to any thesis, proposal, or grant prose without re-asking. Canonical source: "
            "docs/writing-and-citation-practices.md section A.\n\n"
            "**Why:** Bobby reviewed his R21 prelim line by line and these are the corrections he gave; "
            "they are hard rules, not preferences.\n\n"
            "**How to apply:**\n"
            "- No em-dashes (use commas, periods, parentheses). No arrow symbols (write 'to'/'then'/'into').\n"
            "- Few colons. No filler words: exactly, really, just, actually, of course, in turn, simply, clearly.\n"
            "- No rhetorical questions. No short, snappy, AI-sounding sentences.\n"
            "- US English, NOT British (this overrides /polish's British default). Define every abbreviation "
            "at first use; real Greek letters (IFN-gamma written as the symbol, not IFNG).\n"
            "- Capabilities-only for in-progress metrics (no brittle test percentages, counts, or runtimes); "
            "hedged voice always.\n"
            "- Anti-AI-tell flow (judgment-level, confirm before heavy rewrites): lead with the main clause, "
            "reduce comma-stops, vary sentence length.\n"
            "- Run /style-check before a draft goes out."
        ),
    )
    remember(
        category="feedback",
        name="pdf-citation-grounding",
        description="Bobby's zero-hallucination citation rule: read the actual PDF page images, identity-check first, no PDF means UNVERIFIED.",
        content=(
            "Apply to any document with references. Canonical source: docs/writing-and-citation-practices.md "
            "sections C and D; run via /cite audit.\n\n"
            "**Why:** a citation verified from an abstract, snippet, or memory is how hallucinated references "
            "and wrong-PDF mismatches slip into a draft.\n\n"
            "**How to apply (the 3-step loop):**\n"
            "1. INVENTORY: split the reference list into have-PDF vs no-PDF (check Sources/Papers/).\n"
            "2. GROUND (have-PDF): open the actual PDF page images with the Read tool, NOT text extraction. "
            "Confirm paper identity (title/authors/journal/DOI) BEFORE confirming any claim; on mismatch, "
            "quarantine the file and mark UNVERIFIED. Quote high-stakes numbers verbatim with their location. "
            "Record one line per citation in Output/<project>/VERIFICATION_LEDGER.md.\n"
            "3. HARVEST (no-PDF): emit a flat clickable link list (one DOI/publisher/PubMed URL per line, "
            "grouped by publisher) for bulk download; `vaultlab fetch-list paywalled` produces it. Re-run step 2 "
            "on the downloaded PDFs.\n\n"
            "**Hard rule:** never verify from memory, an abstract alone, or a search snippet. No PDF means the "
            "citation is UNVERIFIED, not assumed correct."
        ),
    )
    print("Seeded 2 feedback memories: thesis-writing-style, pdf-citation-grounding")


if __name__ == "__main__":
    main()
