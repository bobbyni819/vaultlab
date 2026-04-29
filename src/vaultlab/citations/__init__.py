"""bobby_citations --- Citation verification and auditing for scientific documents.

Extract citations from markdown, verify papers exist, match claims against
abstracts and full text, detect hallucinations, and generate evidence-rich
audit reports.

Usage:
    from vaultlab.citations import audit_file, audit_directory

    report = audit_file("paper_draft.md", kb_dir="G:/My Drive/Knowledge/research")
    print(report.total, "citations found")
"""

from vaultlab.citations.auditor import audit_directory, audit_file
from vaultlab.citations.evidence import EvidenceIndex
from vaultlab.citations.extractor import extract_citations, extract_citations_from_text
from vaultlab.citations.models import (
    AuditReport,
    Citation,
    RiskLevel,
    VerificationStatus,
)
from vaultlab.citations.reporter import generate_report
from vaultlab.citations.verifier import verify_citation

__all__ = [
    "AuditReport",
    "Citation",
    "EvidenceIndex",
    "RiskLevel",
    "VerificationStatus",
    "audit_directory",
    "audit_file",
    "extract_citations",
    "extract_citations_from_text",
    "generate_report",
    "verify_citation",
]
