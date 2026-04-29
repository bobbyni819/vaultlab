"""Generate markdown audit reports with evidence chunks."""

from __future__ import annotations

import os

from vaultlab.citations.models import AuditReport, Citation, VerificationStatus


def generate_report(
    report: AuditReport,
    output_path: str | None = None,
) -> str:
    """Generate a markdown audit report.

    Args:
        report: The AuditReport to render.
        output_path: Optional path to write the report to disk.

    Returns:
        The markdown string.
    """
    lines = [
        "# Citation Audit Report",
        "",
        f"**Date:** {report.audit_date}",
        f"**Files audited:** {', '.join(report.source_files)}",
        "",
        "## Summary",
        "",
        f"**Total citations:** {report.total}",
        "",
        "| Status | Count |",
        "|--------|-------|",
    ]

    for status, count in sorted(report.by_status.items()):
        label = status.replace("_", " ").title()
        lines.append(f"| {label} | {count} |")

    lines.append("")

    if report.high_risk_unverified > 0:
        lines.append(f"**High-risk unverified:** {report.high_risk_unverified}")
        lines.append("")

    # Hallucination flags
    if report.hallucination_flags:
        lines.append("## Hallucination Flags")
        lines.append("")
        for flag in report.hallucination_flags:
            lines.append(f"- {flag}")
        lines.append("")

    # Per-citation details
    lines.append("## Citations")
    lines.append("")

    for i, citation in enumerate(report.citations, 1):
        lines.extend(_render_citation(i, citation))
        lines.append("")

    # Action items
    if report.action_items:
        lines.append("## Action Items")
        lines.append("")
        for item in report.action_items:
            lines.append(f"- [ ] {item}")
        lines.append("")

    md = "\n".join(lines)

    if output_path:
        dirname = os.path.dirname(output_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md)

    return md


def _render_citation(index: int, citation: Citation) -> list[str]:
    """Render a single citation block."""
    status_icon = _status_icon(citation.status)
    lines = [
        f"### {index}. {citation.raw_text} {status_icon}",
        "",
        f"**Claim:** {citation.claim}",
        f"**Status:** {citation.status.value.replace('_', ' ').upper()}",
        f"**File:** {citation.source_file}:{citation.line_number}",
    ]

    if citation.title:
        lines.append(f"**Paper:** {citation.title}")
    if citation.doi:
        lines.append(f"**DOI:** [{citation.doi}](https://doi.org/{citation.doi})")
    if citation.pmid:
        lines.append(
            f"**PMID:** [{citation.pmid}](https://pubmed.ncbi.nlm.nih.gov/{citation.pmid}/)"
        )

    # Evidence section
    if citation.evidence and citation.evidence.claim_match:
        cm = citation.evidence.claim_match
        lines.append("")
        lines.append(f"**Match:** {cm.supported} (confidence: {cm.confidence:.2f})")

        if cm.evidence_chunk:
            lines.append("")
            lines.append("**Evidence chunk:**")
            lines.append(f"> {cm.evidence_chunk}")
            lines.append(f"> -- *{cm.chunk_location}*")

        if cm.reasoning:
            lines.append("")
            lines.append(f"**Reasoning:** {cm.reasoning}")

    # Hallucination flags
    if citation.hallucination_flags:
        lines.append("")
        lines.append("**Flags:**")
        for flag in citation.hallucination_flags:
            lines.append(f"- {flag}")

    return lines


def _status_icon(status: VerificationStatus) -> str:
    """Return an ASCII status indicator."""
    icons = {
        VerificationStatus.VERIFIED_FULLTEXT: "[VERIFIED-FULL]",
        VerificationStatus.VERIFIED_ABSTRACT: "[VERIFIED]",
        VerificationStatus.API_CONFIRMED: "[CONFIRMED]",
        VerificationStatus.UNVERIFIED: "[UNVERIFIED]",
        VerificationStatus.SUSPECT: "[SUSPECT]",
        VerificationStatus.CONTRADICTED: "[CONTRADICTED]",
    }
    return icons.get(status, "[?]")
