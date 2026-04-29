"""ResearchSession — programmatic API for multi-round research analysis.

Wraps the /research-reason workflow as reusable Python code.
Manages rounds, findings, and chain-of-reasoning provenance.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class FindingStatus(Enum):
    """Status of a research finding through the reasoning process."""

    PRELIMINARY = "preliminary"  # Data Analyst identified, not yet reviewed
    NEEDS_VALIDATION = "needs_validation"  # Domain Expert flagged, Critic hasn't ruled
    ROBUST = "robust"  # Critic confirmed, ready for manuscript
    WEAK = "weak"  # Critic found insufficient evidence
    UNSUPPORTED = "unsupported"  # Critic rejected
    NEEDS_FOLLOWUP = "needs_followup"  # Hit max rounds without resolution


class FindingCategory(Enum):
    """How a finding relates to existing knowledge."""

    EXPECTED = "expected"  # Validates known science
    NOVEL = "novel"  # Extends known science
    SURPRISING = "surprising"  # Contradicts known science
    UNEXPLAINED = "unexplained"  # No existing framework


@dataclass
class ChainLink:
    """One step in the chain of reasoning for a finding."""

    step: str  # "data_query", "interpretation", "challenge", "resolution", "literature"
    agent: str  # "analyst", "expert", "critic"
    round_num: int
    content: str  # What was said/done
    data_source: str = ""  # CSV path, DOI, etc.
    query: str = ""  # The actual query/code run
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "agent": self.agent,
            "round": self.round_num,
            "content": self.content,
            "data_source": self.data_source,
            "query": self.query,
            "timestamp": self.timestamp or datetime.now().isoformat(),
        }


@dataclass
class Finding:
    """A research finding with full provenance chain."""

    id: str  # F001, F002, etc.
    claim: str  # One-sentence finding
    status: FindingStatus = FindingStatus.PRELIMINARY
    category: FindingCategory = FindingCategory.UNEXPLAINED
    confidence: float = 0.0  # 0.0-1.0
    data_source: str = ""  # Primary data file
    exact_value: str = ""  # The key number (rho=0.78, p<0.05)
    null_baseline: str = ""  # Null distribution comparison
    mechanism: str = ""  # Proposed mechanism
    literature: list[str] = field(default_factory=list)  # Supporting DOIs
    chain: list[ChainLink] = field(default_factory=list)  # Full reasoning chain
    branch_dir: str = ""  # KB path to branch docs

    def add_link(self, step: str, agent: str, round_num: int, content: str, **kwargs) -> None:
        """Add a step to the chain of reasoning."""
        self.chain.append(
            ChainLink(
                step=step,
                agent=agent,
                round_num=round_num,
                content=content,
                **kwargs,
            )
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "claim": self.claim,
            "status": self.status.value,
            "category": self.category.value,
            "confidence": self.confidence,
            "data_source": self.data_source,
            "exact_value": self.exact_value,
            "null_baseline": self.null_baseline,
            "mechanism": self.mechanism,
            "literature": self.literature,
            "chain": [link.to_dict() for link in self.chain],
            "branch_dir": self.branch_dir,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Finding:
        chain = [
            ChainLink(
                **{k: v for k, v in link.items() if k != "round"}
                | {"round_num": link.get("round", 0)}
            )
            for link in d.get("chain", [])
        ]
        return cls(
            id=d["id"],
            claim=d["claim"],
            status=FindingStatus(d.get("status", "preliminary")),
            category=FindingCategory(d.get("category", "unexplained")),
            confidence=d.get("confidence", 0.0),
            data_source=d.get("data_source", ""),
            exact_value=d.get("exact_value", ""),
            null_baseline=d.get("null_baseline", ""),
            mechanism=d.get("mechanism", ""),
            literature=d.get("literature", []),
            chain=chain,
            branch_dir=d.get("branch_dir", ""),
        )

    def summary(self) -> str:
        """One-line summary for passing between agents."""
        return f"{self.id}: {self.claim} [{self.status.value.upper()}] ({self.exact_value})"


class ResearchSession:
    """Manage a multi-round research analysis session.

    Usage:
        session = ResearchSession(project_name="Metabolism", kb_dir="G:/My Drive/Knowledge/metabolism")
        session.add_finding("F001", "LPI correlates with epithelial cells", data_source="correlations.csv")
        session.update_finding("F001", status=FindingStatus.ROBUST, confidence=0.95)
        session.save()

        # Later, resume:
        session = ResearchSession.load(kb_dir)
    """

    def __init__(self, project_name: str = "", kb_dir: str = "", domain: str = ""):
        self.project_name = project_name
        self.kb_dir = kb_dir
        self.domain = domain
        self.findings: dict[str, Finding] = {}
        self.current_round = 0
        self.max_rounds = 4
        self.started = datetime.now().isoformat()
        self._next_id = 1

    def next_finding_id(self) -> str:
        """Generate the next finding ID."""
        fid = f"F{self._next_id:03d}"
        self._next_id += 1
        return fid

    def add_finding(self, finding_id: str, claim: str, **kwargs) -> Finding:
        """Add a new finding to the session."""
        f = Finding(id=finding_id, claim=claim, **kwargs)
        self.findings[finding_id] = f
        return f

    def update_finding(self, finding_id: str, **kwargs) -> Finding:
        """Update a finding's fields."""
        f = self.findings[finding_id]
        for key, value in kwargs.items():
            if hasattr(f, key):
                setattr(f, key, value)
        return f

    def get_finding(self, finding_id: str) -> Finding | None:
        """Get a finding by ID."""
        return self.findings.get(finding_id)

    def findings_by_status(self, status: FindingStatus) -> list[Finding]:
        """Get all findings with a given status."""
        return [f for f in self.findings.values() if f.status == status]

    def needs_another_round(self) -> bool:
        """Check if another reasoning round is needed."""
        if self.current_round >= self.max_rounds:
            return False
        return bool(self.findings_by_status(FindingStatus.NEEDS_VALIDATION))

    def finalize(self) -> None:
        """Finalize the session — convert remaining NEEDS_VALIDATION to NEEDS_FOLLOWUP."""
        for f in self.findings_by_status(FindingStatus.NEEDS_VALIDATION):
            f.status = FindingStatus.NEEDS_FOLLOWUP

    def summary_table(self) -> str:
        """Generate a markdown summary table of all findings."""
        lines = [
            "| ID | Claim | Status | Category | Value | Confidence |",
            "|-----|-------|--------|----------|-------|------------|",
        ]
        for f in sorted(self.findings.values(), key=lambda x: x.id):
            lines.append(
                f"| {f.id} | {f.claim[:60]} | {f.status.value} | "
                f"{f.category.value} | {f.exact_value} | {f.confidence:.2f} |"
            )
        return "\n".join(lines)

    def save(self, path: str | None = None) -> str:
        """Save session to JSON file."""
        if path is None:
            path = os.path.join(self.kb_dir, "Output", "research-session.json")

        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            "project_name": self.project_name,
            "kb_dir": self.kb_dir,
            "domain": self.domain,
            "current_round": self.current_round,
            "max_rounds": self.max_rounds,
            "started": self.started,
            "next_id": self._next_id,
            "findings": {fid: f.to_dict() for fid, f in self.findings.items()},
        }
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
        return path

    @classmethod
    def load(cls, path_or_kb_dir: str) -> ResearchSession:
        """Load a session from JSON file or KB directory."""
        if os.path.isdir(path_or_kb_dir):
            path = os.path.join(path_or_kb_dir, "Output", "research-session.json")
        else:
            path = path_or_kb_dir

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        session = cls(
            project_name=data.get("project_name", ""),
            kb_dir=data.get("kb_dir", ""),
            domain=data.get("domain", ""),
        )
        session.current_round = data.get("current_round", 0)
        session.max_rounds = data.get("max_rounds", 4)
        session.started = data.get("started", "")
        session._next_id = data.get("next_id", 1)
        session.findings = {
            fid: Finding.from_dict(fdata) for fid, fdata in data.get("findings", {}).items()
        }
        return session

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "domain": self.domain,
            "current_round": self.current_round,
            "finding_count": len(self.findings),
            "robust": len(self.findings_by_status(FindingStatus.ROBUST)),
            "needs_validation": len(self.findings_by_status(FindingStatus.NEEDS_VALIDATION)),
            "needs_followup": len(self.findings_by_status(FindingStatus.NEEDS_FOLLOWUP)),
            "weak": len(self.findings_by_status(FindingStatus.WEAK)),
        }
