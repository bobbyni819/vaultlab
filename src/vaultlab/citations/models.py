"""Data models for citation auditing."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from vaultlab.research.verification import EvidenceRecord


class VerificationStatus(Enum):
    VERIFIED_FULLTEXT = "verified_fulltext"
    VERIFIED_ABSTRACT = "verified_abstract"
    API_CONFIRMED = "api_confirmed"
    UNVERIFIED = "unverified"
    SUSPECT = "suspect"
    CONTRADICTED = "contradicted"


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Citation:
    """A single citation extracted from a markdown document."""

    raw_text: str
    authors: str
    year: int
    claim: str
    source_file: str
    line_number: int
    doi: str = ""
    pmid: str = ""
    title: str = ""
    journal: str = ""
    status: VerificationStatus = VerificationStatus.UNVERIFIED
    risk: RiskLevel = RiskLevel.MEDIUM
    evidence: EvidenceRecord | None = None
    hallucination_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "raw_text": self.raw_text,
            "authors": self.authors,
            "year": self.year,
            "claim": self.claim,
            "source_file": self.source_file,
            "line_number": self.line_number,
            "doi": self.doi,
            "pmid": self.pmid,
            "title": self.title,
            "journal": self.journal,
            "status": self.status.value,
            "risk": self.risk.value,
            "evidence": self.evidence.to_dict() if self.evidence else None,
            "hallucination_flags": self.hallucination_flags,
        }


@dataclass
class AuditReport:
    """Summary of a citation audit across one or more documents."""

    total: int
    by_status: dict[str, int]
    high_risk_unverified: int
    citations: list[Citation]
    hallucination_flags: list[str]
    action_items: list[str]
    source_files: list[str]
    audit_date: str

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "by_status": self.by_status,
            "high_risk_unverified": self.high_risk_unverified,
            "citations": [c.to_dict() for c in self.citations],
            "hallucination_flags": self.hallucination_flags,
            "action_items": self.action_items,
            "source_files": self.source_files,
            "audit_date": self.audit_date,
        }
