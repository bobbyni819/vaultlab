"""Claims-to-evidence ledger for manuscript backbone checks."""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal, TypeVar, cast

from vaultlab.citations.models import RiskLevel, VerificationStatus
from vaultlab.provenance import ProvenanceRecord, write_receipts

SCHEMA = "vaultlab-claim-ledger/v1"

logger = logging.getLogger(__name__)

LinkT = TypeVar("LinkT", bound="FigureLink | NumericLink | CitationLink")
EnumT = TypeVar("EnumT", bound=Enum)


class ClaimReadiness(Enum):
    """Lifecycle state for a manuscript claim."""

    DRAFTED = "drafted"
    EVIDENCE_LINKED = "evidence_linked"
    FIGURE_SYNCED = "figure_synced"
    CITATION_TIERED = "citation_tiered"
    VERIFIED = "verified"
    AT_RISK = "at_risk"
    NEEDS_HEDGE = "needs_hedge"


class CitationTier(Enum):
    """Citation verification tier used by the claim ledger."""

    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"

    @property
    def rank(self) -> int:
        """Numeric ordering for tier-gate comparisons."""
        return {
            CitationTier.TIER_1: 1,
            CitationTier.TIER_2: 2,
            CitationTier.TIER_3: 3,
        }[self]

    @classmethod
    def from_verification_status(cls, status: VerificationStatus) -> CitationTier | None:
        """Map citation verifier statuses onto ledger tiers."""
        if status is VerificationStatus.VERIFIED_FULLTEXT:
            return cls.TIER_3
        if status is VerificationStatus.VERIFIED_ABSTRACT:
            return cls.TIER_2
        if status is VerificationStatus.API_CONFIRMED:
            return cls.TIER_1
        return None


@dataclass
class Claim:
    """One manuscript claim that must map to evidence before shipping."""

    claim_id: str
    text: str
    section: str | None = None
    kind: str = "quantitative"
    status: ClaimReadiness = ClaimReadiness.DRAFTED
    risk: RiskLevel = RiskLevel.MEDIUM

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "section": self.section,
            "kind": self.kind,
            "status": self.status.value,
            "risk": self.risk.value,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Claim:
        return cls(
            claim_id=str(payload.get("claim_id", "")),
            text=str(payload.get("text", "")),
            section=_optional_str(payload.get("section")),
            kind=str(payload.get("kind", "quantitative")),
            status=_enum_from_value(
                ClaimReadiness, payload.get("status"), ClaimReadiness.DRAFTED
            ),
            risk=_enum_from_value(RiskLevel, payload.get("risk"), RiskLevel.MEDIUM),
        )


@dataclass
class FigureLink:
    """A link from a claim to a publication figure or panel."""

    claim_id: str
    figure_id: str
    panel: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "figure_id": self.figure_id,
            "panel": self.panel,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> FigureLink:
        return cls(
            claim_id=str(payload.get("claim_id", "")),
            figure_id=str(payload.get("figure_id", "")),
            panel=_optional_str(payload.get("panel")),
        )


@dataclass
class NumericLink:
    """A link from a claim to the exact statistic and source file."""

    claim_id: str
    value: str
    source_file: str
    stat_method: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "value": self.value,
            "source_file": self.source_file,
            "stat_method": self.stat_method,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> NumericLink:
        return cls(
            claim_id=str(payload.get("claim_id", "")),
            value=str(payload.get("value", "")),
            source_file=str(payload.get("source_file", "")),
            stat_method=_optional_str(payload.get("stat_method")),
        )


@dataclass
class CitationLink:
    """A link from a claim to a citation and verification tier."""

    claim_id: str
    citation_key: str
    tier: CitationTier
    status: VerificationStatus | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "citation_key": self.citation_key,
            "tier": self.tier.value,
            "status": self.status.value if self.status is not None else None,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CitationLink:
        raw_status = payload.get("status")
        status = _optional_enum_from_value(VerificationStatus, raw_status)
        tier = _optional_enum_from_value(CitationTier, payload.get("tier"))
        if tier is None and status is not None:
            tier = CitationTier.from_verification_status(status)
        return cls(
            claim_id=str(payload.get("claim_id", "")),
            citation_key=str(payload.get("citation_key", "")),
            tier=tier or CitationTier.TIER_1,
            status=status,
        )


AuditSeverity = Literal["error", "warning"]


@dataclass(frozen=True)
class LedgerProblem:
    """One structured claim-ledger audit problem."""

    claim_id: str
    severity: AuditSeverity
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "claim_id": self.claim_id,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass(frozen=True)
class LedgerAudit:
    """Structured result from :meth:`ClaimLedger.audit`."""

    ok: bool
    problems: list[LedgerProblem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "problems": [problem.to_dict() for problem in self.problems],
        }


@dataclass
class ClaimLedger:
    """Manuscript claims mapped to figures, statistics, and citation tiers."""

    claims: list[Claim] = field(default_factory=list)
    figure_links: list[FigureLink] = field(default_factory=list)
    numeric_links: list[NumericLink] = field(default_factory=list)
    citation_links: list[CitationLink] = field(default_factory=list)
    parse_warnings: list[str] = field(default_factory=list)

    def add_claim(
        self,
        claim_id: str,
        text: str,
        *,
        section: str | None = None,
        kind: str = "quantitative",
        status: ClaimReadiness = ClaimReadiness.DRAFTED,
        risk: RiskLevel = RiskLevel.MEDIUM,
    ) -> Claim:
        """Add a claim and return it."""
        claim = Claim(
            claim_id=claim_id,
            text=text,
            section=section,
            kind=kind,
            status=status,
            risk=risk,
        )
        self.claims.append(claim)
        return claim

    def link_figure(self, claim_id: str, figure_id: str, *, panel: str | None = None) -> FigureLink:
        """Link a claim to a figure or figure panel."""
        link = FigureLink(claim_id=claim_id, figure_id=figure_id, panel=panel)
        self.figure_links.append(link)
        return link

    def link_numeric(
        self,
        claim_id: str,
        value: str,
        source_file: str,
        *,
        stat_method: str | None = None,
    ) -> NumericLink:
        """Link a claim to an exact statistic and source file."""
        link = NumericLink(
            claim_id=claim_id,
            value=value,
            source_file=source_file,
            stat_method=stat_method,
        )
        self.numeric_links.append(link)
        return link

    def link_citation(
        self,
        claim_id: str,
        citation_key: str,
        tier: CitationTier,
        *,
        status: VerificationStatus | None = None,
    ) -> CitationLink:
        """Link a claim to a citation verification tier."""
        link = CitationLink(
            claim_id=claim_id,
            citation_key=citation_key,
            tier=tier,
            status=status,
        )
        self.citation_links.append(link)
        return link

    @classmethod
    def from_markdown(cls, text: str) -> ClaimLedger:
        """Parse inline claim-ledger tags from manuscript markdown."""
        ledger = cls()
        for paragraph in _paragraphs(text):
            current_claim_id: str | None = None
            for raw_line in paragraph.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                claim_match = _first_claim_tag(line)
                if claim_match is not None:
                    current_claim_id = ledger._parse_claim_tag(line, claim_match)
                ledger._parse_link_tags(line, current_claim_id)
        return ledger

    def audit(
        self,
        *,
        base_dir: Path | str | None = None,
        coverage_dir: Path | str | None = None,
    ) -> LedgerAudit:
        """Audit the no-untiered-claim gate and optional source-path checks."""
        problems: list[LedgerProblem] = []
        figure_by_claim = _links_by_claim(self.figure_links)
        numeric_by_claim = _links_by_claim(self.numeric_links)
        citation_by_claim = _links_by_claim(self.citation_links)

        for claim in self.claims:
            figure_links = figure_by_claim.get(claim.claim_id, [])
            numeric_links = numeric_by_claim.get(claim.claim_id, [])
            citation_links = citation_by_claim.get(claim.claim_id, [])
            if claim.kind == "quantitative" and not figure_links:
                problems.append(
                    LedgerProblem(claim.claim_id, "error", "quantitative claim missing figure link")
                )
            if claim.kind == "quantitative" and not numeric_links:
                problems.append(
                    LedgerProblem(claim.claim_id, "error", "quantitative claim missing numeric link")
                )
            if claim.kind != "novel" and not citation_links:
                problems.append(LedgerProblem(claim.claim_id, "error", "claim missing citation link"))
            for citation in citation_links:
                if citation.tier is not CitationTier.TIER_3:
                    problems.append(
                        LedgerProblem(
                            claim.claim_id,
                            "error",
                            (
                                f"citation {citation.citation_key} ships untiered/under-tiered: "
                                "needs Tier-3"
                            ),
                        )
                    )
            if base_dir is not None:
                problems.extend(_source_file_problems(claim.claim_id, numeric_links, Path(base_dir)))
            if coverage_dir is not None:
                problems.extend(
                    _coverage_manifest_problems(
                        claim.claim_id,
                        figure_links,
                        Path(coverage_dir),
                    )
                )

        return LedgerAudit(ok=not problems, problems=problems)

    def needs_tier3(self) -> list[CitationLink]:
        """Return citation links that must be promoted to Tier 3."""
        return [link for link in self.citation_links if link.tier is not CitationTier.TIER_3]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the ledger to a JSON-ready dict."""
        return {
            "schema": SCHEMA,
            "claims": [claim.to_dict() for claim in self.claims],
            "figure_links": [link.to_dict() for link in self.figure_links],
            "numeric_links": [link.to_dict() for link in self.numeric_links],
            "citation_links": [link.to_dict() for link in self.citation_links],
            "parse_warnings": list(self.parse_warnings),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ClaimLedger:
        """Build a ledger from a parsed JSON payload."""
        ledger = cls()
        ledger.claims = [
            Claim.from_dict(item) for item in _dict_list(payload.get("claims", []))
        ]
        ledger.figure_links = [
            FigureLink.from_dict(item) for item in _dict_list(payload.get("figure_links", []))
        ]
        ledger.numeric_links = [
            NumericLink.from_dict(item) for item in _dict_list(payload.get("numeric_links", []))
        ]
        ledger.citation_links = [
            CitationLink.from_dict(item) for item in _dict_list(payload.get("citation_links", []))
        ]
        ledger.parse_warnings = _string_list(payload.get("parse_warnings", []))
        return ledger

    def to_json(self, path: Path | str) -> Path:
        """Atomically write the ledger JSON and best-effort provenance receipts."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.tmp")
        tmp.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, target)
        self._write_provenance_receipts(target)
        return target

    @classmethod
    def read_json(cls, path: Path | str) -> ClaimLedger:
        """Read a claim ledger from JSON."""
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"claim ledger must be a JSON object: {path}")
        return cls.from_dict(cast("dict[str, Any]", payload))

    def to_markdown(self) -> str:
        """Render the claim -> figure -> stat -> citation ledger as a table."""
        audit = self.audit()
        issues_by_claim: dict[str, list[str]] = {}
        for problem in audit.problems:
            issues_by_claim.setdefault(problem.claim_id, []).append(problem.message)

        rows = [
            "| claim | section | readiness | figures | stat(source) | citation(tier) | issues |",
            "|---|---|---|---|---|---|---|",
        ]
        for claim in self.claims:
            rows.append(
                "| "
                + " | ".join(
                    [
                        _cell(f"{claim.claim_id}: {claim.text}"),
                        _cell(claim.section or ""),
                        _cell(claim.status.name),
                        _cell(_render_figures(self.figure_links, claim.claim_id)),
                        _cell(_render_numeric(self.numeric_links, claim.claim_id)),
                        _cell(_render_citations(self.citation_links, claim.claim_id)),
                        _cell("; ".join(issues_by_claim.get(claim.claim_id, [])) or "ok"),
                    ]
                )
                + " |"
            )
        return "\n".join(rows) + "\n"

    def _parse_claim_tag(self, line: str, match: re.Match[str]) -> str:
        claim_id = match.group("target")
        attrs = _parse_attrs(match.group("attrs"))
        if claim_id in {claim.claim_id for claim in self.claims}:
            self.parse_warnings.append(f"duplicate claim id: {claim_id}")
        text = _TAG_RE.sub("", line[match.end() :]).strip()
        self.add_claim(
            claim_id,
            text,
            section=attrs.get("section"),
            kind=attrs.get("kind", "quantitative"),
            status=_enum_from_string(
                ClaimReadiness,
                attrs.get("status"),
                ClaimReadiness.DRAFTED,
            ),
            risk=_enum_from_string(RiskLevel, attrs.get("risk"), RiskLevel.MEDIUM),
        )
        return claim_id

    def _parse_link_tags(self, line: str, current_claim_id: str | None) -> None:
        for match in _TAG_RE.finditer(line):
            tag = match.group("tag")
            if tag == "CLAIM":
                continue
            if current_claim_id is None:
                self.parse_warnings.append(f"{tag} tag without a preceding claim: {match.group(0)}")
                continue
            attrs = _parse_attrs(match.group("attrs"))
            target = match.group("target")
            if tag == "FIG":
                self.link_figure(current_claim_id, target, panel=attrs.get("panel"))
            elif tag == "STAT":
                source_file = attrs.get("src") or attrs.get("source_file") or ""
                if not source_file:
                    self.parse_warnings.append(f"STAT tag missing src: {match.group(0)}")
                self.link_numeric(
                    current_claim_id,
                    target,
                    source_file,
                    stat_method=attrs.get("method") or attrs.get("stat_method"),
                )
            elif tag == "CITE":
                status = _optional_enum_from_string(VerificationStatus, attrs.get("status"))
                tier = _parse_tier(attrs.get("tier"), status)
                if "tier" not in attrs and status is None:
                    self.parse_warnings.append(
                        f"CITE tag missing tier/status; defaulting to Tier-1: {target}"
                    )
                self.link_citation(current_claim_id, target, tier, status=status)

    def _write_provenance_receipts(self, target: Path) -> None:
        record = ProvenanceRecord(
            generated_by="vaultlab.manuscript.claim_ledger.ClaimLedger.to_json",
            kind="manuscript_claim_ledger",
            inputs=[link.source_file for link in self.numeric_links if link.source_file],
            params={
                "n_claims": len(self.claims),
                "n_figure_links": len(self.figure_links),
                "n_numeric_links": len(self.numeric_links),
                "n_citation_links": len(self.citation_links),
                "n_tier3_needed": len(self.needs_tier3()),
            },
            tags=["claims", "evidence", "manuscript"],
        )
        try:
            write_receipts(str(target), record)
        except Exception:
            logger.exception("failed to write claim-ledger provenance receipts")


_TAG_RE = re.compile(
    r"\[(?P<tag>CLAIM|FIG|STAT|CITE):(?P<target>[^\]\s]+)(?P<attrs>[^\]]*)\]"
)


def _paragraphs(text: str) -> list[str]:
    return [part for part in re.split(r"\n\s*\n", text.strip()) if part.strip()]


def _first_claim_tag(line: str) -> re.Match[str] | None:
    for match in _TAG_RE.finditer(line):
        if match.group("tag") == "CLAIM":
            return match
    return None


def _parse_attrs(raw_attrs: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    if not raw_attrs.strip():
        return attrs
    try:
        tokens = shlex.split(raw_attrs.strip())
    except ValueError:
        tokens = raw_attrs.strip().split()
    for token in tokens:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        attrs[key.strip()] = value.strip()
    return attrs


def _parse_tier(raw_tier: str | None, status: VerificationStatus | None) -> CitationTier:
    if raw_tier is not None:
        normalized = raw_tier.strip().lower().replace("-", "_")
        tier_by_token = {
            "1": CitationTier.TIER_1,
            "tier1": CitationTier.TIER_1,
            "tier_1": CitationTier.TIER_1,
            "2": CitationTier.TIER_2,
            "tier2": CitationTier.TIER_2,
            "tier_2": CitationTier.TIER_2,
            "3": CitationTier.TIER_3,
            "tier3": CitationTier.TIER_3,
            "tier_3": CitationTier.TIER_3,
        }
        if normalized in tier_by_token:
            return tier_by_token[normalized]
    if status is not None:
        tier = CitationTier.from_verification_status(status)
        if tier is not None:
            return tier
    return CitationTier.TIER_1


def _links_by_claim(links: list[LinkT]) -> dict[str, list[LinkT]]:
    grouped: dict[str, list[LinkT]] = {}
    for link in links:
        grouped.setdefault(link.claim_id, []).append(link)
    return grouped


def _source_file_problems(
    claim_id: str,
    numeric_links: list[NumericLink],
    base_dir: Path,
) -> list[LedgerProblem]:
    problems: list[LedgerProblem] = []
    for link in numeric_links:
        if not link.source_file:
            problems.append(LedgerProblem(claim_id, "error", "numeric link missing source file"))
            continue
        source_path = Path(link.source_file)
        if not source_path.is_absolute():
            source_path = base_dir / source_path
        if not source_path.exists():
            problems.append(
                LedgerProblem(
                    claim_id,
                    "error",
                    f"numeric source file does not exist: {link.source_file}",
                )
            )
    return problems


def _coverage_manifest_problems(
    claim_id: str,
    figure_links: list[FigureLink],
    coverage_dir: Path,
) -> list[LedgerProblem]:
    problems: list[LedgerProblem] = []
    for link in figure_links:
        candidates = [
            coverage_dir / f"{link.figure_id}.json",
            coverage_dir / f"{link.figure_id}.coverage.json",
            coverage_dir / f"{link.figure_id}.coverage-manifest.json",
        ]
        if not any(candidate.exists() for candidate in candidates):
            problems.append(
                LedgerProblem(
                    claim_id,
                    "warning",
                    f"coverage manifest not found for figure: {link.figure_id}",
                )
            )
    return problems


def _render_figures(links: list[FigureLink], claim_id: str) -> str:
    values = [
        f"{link.figure_id}:{link.panel}" if link.panel else link.figure_id
        for link in links
        if link.claim_id == claim_id
    ]
    return ", ".join(values)


def _render_numeric(links: list[NumericLink], claim_id: str) -> str:
    values: list[str] = []
    for link in links:
        if link.claim_id != claim_id:
            continue
        source = link.source_file
        if link.stat_method:
            source = f"{source}; {link.stat_method}"
        values.append(f"{link.value} ({source})")
    return ", ".join(values)


def _render_citations(links: list[CitationLink], claim_id: str) -> str:
    values = [
        f"{link.citation_key} ({link.tier.name})"
        for link in links
        if link.claim_id == claim_id
    ]
    return ", ".join(values)


def _cell(value: str) -> str:
    return value.replace("\n", " ").replace("|", "\\|")


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [cast("dict[str, Any]", item) for item in value if isinstance(item, dict)]


def _enum_from_value(enum_cls: type[EnumT], value: Any, default: EnumT) -> EnumT:
    parsed = _optional_enum_from_value(enum_cls, value)
    return parsed if parsed is not None else default


def _optional_enum_from_value(enum_cls: type[EnumT], value: Any) -> EnumT | None:
    if value is None:
        return None
    for member in enum_cls:
        if value == member.value or value == member.name:
            return member
    return None


def _enum_from_string(
    enum_cls: type[EnumT],
    value: str | None,
    default: EnumT,
) -> EnumT:
    parsed = _optional_enum_from_string(enum_cls, value)
    return parsed if parsed is not None else default


def _optional_enum_from_string(
    enum_cls: type[EnumT],
    value: str | None,
) -> EnumT | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    for member in enum_cls:
        if normalized in {str(member.value).lower(), member.name.lower()}:
            return member
    return None


__all__ = [
    "CitationLink",
    "CitationTier",
    "Claim",
    "ClaimLedger",
    "ClaimReadiness",
    "FigureLink",
    "LedgerAudit",
    "LedgerProblem",
    "NumericLink",
]
