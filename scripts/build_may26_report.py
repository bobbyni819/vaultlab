"""Build may26report.pdf — 1-page synthesis of the vaultlab stress-test audit.

Reads the audit artifacts under
/Users/arnav/vaultlab-kb/elife-91157-stress/ and emits a single-page PDF
report into the Vaultlab repo root.
"""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib import colors

REPO = Path("/Users/arnav/Library/CloudStorage/OneDrive-Personal/Desktop/Vaultlab")
KB = Path("/Users/arnav/vaultlab-kb/elife-91157-stress")
RUN = KB / "Output" / "run-2026-05-26"
RUBRIC = json.loads((RUN / "rubric-scores.json").read_text())
BUGS = [json.loads(l) for l in (RUN / "bug-reports.jsonl").read_text().splitlines() if l.strip()]
AUDIT = [json.loads(l) for l in (RUN / "audit-rows.jsonl").read_text().splitlines() if l.strip()]
OUT_PDF = REPO / "may26report.pdf"


def main() -> int:
    doc = SimpleDocTemplate(
        str(OUT_PDF),
        pagesize=LETTER,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
        title="vaultlab stress test — 2026-05-26",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "title", parent=styles["Heading1"], fontSize=13, spaceAfter=4, leading=15
    )
    sub_style = ParagraphStyle(
        "sub", parent=styles["Normal"], fontSize=8, textColor=colors.grey, spaceAfter=8
    )
    h2 = ParagraphStyle(
        "h2", parent=styles["Heading2"], fontSize=9.5, spaceBefore=4, spaceAfter=2, leading=11
    )
    body = ParagraphStyle(
        "body", parent=styles["Normal"], fontSize=8.5, leading=10.5,
        alignment=TA_LEFT, spaceAfter=4
    )
    small = ParagraphStyle(
        "small", parent=styles["Normal"], fontSize=7.5, leading=9, textColor=colors.HexColor("#444"),
    )

    cm = RUBRIC["conclusion_match"]
    pl = RUBRIC["per_lane"]

    elements = []
    elements.append(Paragraph("vaultlab stress test — eLife 91157, Figure 4 — synthesis report", title_style))
    elements.append(Paragraph(
        "Run: 2026-05-26 · Project slug: <b>elife-91157-stress</b> · KB: /Users/arnav/vaultlab-kb · "
        f"54 QA tests pass · Verdict: <b>conclusion_match = {cm['verdict']}</b>",
        sub_style,
    ))

    # --- Headline finding ---
    elements.append(Paragraph("Headline finding", h2))
    elements.append(Paragraph(
        "The vaultlab <code>/run-analysis</code> pipeline does not author conclusions. "
        "Across 9 Figure-4 panels, the produced <code>methods.md</code> is a descriptive-stats template — "
        "no direction, magnitude, significance, or citations. Independent Welch's t-tests on the tidy CSVs "
        "recovered the paper's direction in every panel where the paper makes one (4E↑, 4F/G/H↓ with p<0.05; 4I↓ trend; 4A/B/C/D ns or null). "
        "So the data and paper would agree if vaultlab had said anything — the verdict collapses to "
        "<b>no</b> because vaultlab said nothing.",
        body,
    ))

    # --- Numbers table ---
    elements.append(Paragraph("Audit numbers at a glance", h2))
    table_data = [
        ["Lane", "Verdict", "High/Fail", "Med/Warn", "Structural gap?"],
        ["rigor_auditor", pl["rigor"]["verdict"],
         f"{pl['rigor']['high']} (incl. {pl['rigor']['blocker']} blocker)",
         str(pl["rigor"]["medium"]), str(pl["rigor"]["structural_gap"])],
        ["methods_critic", pl["methods_critic"]["verdict"],
         str(pl["methods_critic"]["unsupported"]),
         str(pl["methods_critic"]["overclaim"]),
         str(pl["methods_critic"]["structural_gap"])],
        ["cite_audit", pl["cite"]["verdict"],
         str(pl["cite"]["unresolved"] + pl["cite"]["wrong_paper"]),
         str(pl["cite"]["claim_unsupported"]),
         str(pl["cite"]["structural_gap"])],
        ["figure faithfulness", pl["figure"]["verdict"],
         str(pl["figure"]["disagree_with_data"]),
         str(pl["figure"]["disagree_with_paper"]),
         str(pl["figure"]["structural_gap"])],
    ]
    t = Table(table_data, colWidths=[1.5 * inch, 0.7 * inch, 1.5 * inch, 0.8 * inch, 1.1 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dcd5c4")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#999")),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 6))

    # --- Bugs ---
    n_crit = sum(1 for b in BUGS if b["severity"] == "critical")
    n_maj = sum(1 for b in BUGS if b["severity"] == "major")
    n_min = sum(1 for b in BUGS if b["severity"] == "minor")
    elements.append(Paragraph(
        f"<b>{len(BUGS)} bugs filed</b> — {n_crit} critical, {n_maj} major, {n_min} minor — "
        "all <code>provenance-break</code>, all attributed to producer <code>run-analysis</code>. "
        "Three of the four lanes (methods_critic / cite / figure) pass only because they had nothing to evaluate; "
        "rigor_auditor fails honestly on the template.",
        body,
    ))

    # --- Insights ---
    elements.append(Paragraph("Insights you should know", h2))
    elements.append(Paragraph(
        "<b>1. The audit infrastructure outclassed the audited primitive.</b> "
        "54 QA tests across 4 phases, deterministic ground-truth-first blinding (no-paper-leakage + mtime-ordering tests both passed), byte-reproducible rubric aggregator, "
        "two isolated subagent contexts that never crossed — this scaffolding works. The subject under test, <code>/run-analysis</code>, is far less ambitious than the audit assumes: "
        "it's a stats-summary tool wearing methods-drafting clothes. The mismatch surfaced in one run.",
        body,
    ))
    elements.append(Paragraph(
        "<b>2. Templates that don't speak get audited as silence, not safety.</b> "
        "Lane D's 9 <code>vaultlab_silent_paper_data_agree</code> rows say the template literally never claims anything about the figures it renders — "
        "the audit rubric correctly treats this as critical, not as a clean pass. A future v2 with a synthesizer step would actually expose "
        "where vaultlab disagrees with reality; today's run can't, because there's nothing to disagree.",
        body,
    ))
    elements.append(Paragraph(
        "<b>3. rigor_auditor's contract is mismatched to template-only producers.</b> "
        "It demands <code>[[doi-slug]]</code> wikilinks on every claim and a References section. <code>compose_methods_paragraph</code> has no literature input channel and emits no bibliography, "
        "so the auditor fires on boilerplate it was never meant to flag. Either the producer needs to advertise <i>template-only</i> in its provenance and the auditor needs to honor that flag, "
        "or the template needs hedge-tagged scaffolding (References stub, hedge tokens around every comparative).",
        body,
    ))
    elements.append(Paragraph(
        "<b>4. The data was tidied correctly on the second try.</b> "
        "First-pass xlsx→CSV used pandas' default <code>header=0</code> and produced garbage groups (\"Unnamed: 0\", NaN values). "
        "Real layout: 2–4 row stacked headers (Vehicle/(R)-DI-87 × S. aureus × cell-type or kidney-side) plus blank-row separators for multi-block sheets (Fig4G). "
        "Walk-up algorithm — for each numeric cell, ascend until you hit the previous block's data — handled all 9 panels (54+8+8+8+8+32+96+32+32 = 278 numeric cells, all preserved).",
        body,
    ))

    # --- Next steps ---
    elements.append(Paragraph("Next steps (ranked)", h2))
    elements.append(Paragraph(
        "<b>A.</b> Add a per-figure interpretation pass to <code>run_pipeline</code>. Cheapest path: a template extension that emits "
        "\"<i>{y} appears to {direction} between {group_a} and {group_b}; recomputed Welch's t-test n={n_a}/{n_b}, p={p}</i>\" using the stats summary the pipeline already computes. "
        "Closes cluster 1 (9 critical bugs) and unlocks Lanes B/C/D to find real disagreements in v2.",
        body,
    ))
    elements.append(Paragraph(
        "<b>B.</b> Add <code>provenance.producer = template-only</code> to the methods.md sidecar and have rigor_auditor downgrade or skip "
        "claim-grounding + reference-completeness rules when present. Closes clusters 2 + 3 (7 bugs) without weakening the audit for real LLM-drafted manuscripts.",
        body,
    ))
    elements.append(Paragraph(
        "<b>C.</b> Re-run this audit on the next vaultlab primitive that actually authors prose (<code>/lit-arc</code>, <code>/build-deck</code>, <code>/respond</code>) — "
        "the 4-lane framework will produce its first non-trivial Lane B/C findings there.",
        body,
    ))
    elements.append(Paragraph(
        "<b>D.</b> Make ground-truth extraction a reusable primitive — a paper PDF → structured <code>ground-truth-figN.md</code> writer with the same isolation guardrails. "
        "Worth packaging because every future audit needs one.",
        body,
    ))

    # --- Footer / pointers ---
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        "Deliverable: <code>/Users/arnav/vaultlab-kb/elife-91157-stress/Output/vaultlab-stress-test-2026-05-26.md</code> · "
        "Bugs: <code>Output/run-2026-05-26/bug-reports.jsonl</code> · "
        "Rubric: <code>Output/run-2026-05-26/rubric-scores.json</code> · "
        "Reproducers: <code>scripts/{xlsx_to_tidy,recompute_panel_stats,build_phase4_deliverable}.py</code>, <code>tests/test_phase{1,2,3,4}.py</code>",
        small,
    ))

    doc.build(elements)
    print(f"wrote {OUT_PDF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
