"""Tier-3 citation gate and promotion queue for manuscripts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vaultlab.citations import Citation, VerificationStatus, extract_citations_from_text
from vaultlab.manuscript.claim_ledger import CitationLink, CitationTier, ClaimLedger


@dataclass(frozen=True)
class CitationTierStatus:
    """Gate status for one citation."""

    citation_key: str
    tier: CitationTier | None
    status: VerificationStatus | None
    blocked: bool
    claim_text: str = ""
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize the citation status to a JSON-ready dict."""
        return {
            "citation_key": self.citation_key,
            "tier": self.tier.value if self.tier is not None else None,
            "status": self.status.value if self.status is not None else None,
            "blocked": self.blocked,
            "claim_text": self.claim_text,
            "source": self.source,
        }


@dataclass(frozen=True)
class PromotionAction:
    """Concrete next action needed to promote a citation to Tier-3."""

    citation_key: str
    current_tier: CitationTier | None
    target_tier: CitationTier
    action: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize the promotion action to a JSON-ready dict."""
        return {
            "citation_key": self.citation_key,
            "current_tier": self.current_tier.value if self.current_tier is not None else None,
            "target_tier": self.target_tier.value,
            "action": self.action,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CitationGateReport:
    """Result from the Tier-3 citation gate."""

    ok: bool
    statuses: list[CitationTierStatus]
    blocked: list[CitationTierStatus]
    promotion_queue: list[PromotionAction]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the gate report to a JSON-ready dict."""
        return {
            "ok": self.ok,
            "statuses": [status.to_dict() for status in self.statuses],
            "blocked": [status.to_dict() for status in self.blocked],
            "promotion_queue": [action.to_dict() for action in self.promotion_queue],
        }

    def to_markdown(self) -> str:
        """Render the gate status and promotion queue as markdown tables."""
        lines = [
            "# Citation Tier Gate",
            "",
            f"- ok: {self.ok}",
            f"- blocked: {len(self.blocked)}",
            "",
            "| citation | tier | status | blocked |",
            "|---|---|---|---|",
        ]
        for status in self.statuses:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(status.citation_key),
                        _cell(_tier_label(status.tier)),
                        _cell(_status_label(status.status)),
                        "yes" if status.blocked else "no",
                    ]
                )
                + " |"
            )
        lines.extend(
            [
                "",
                "## Promotion queue",
                "",
                "| citation | current tier | target tier | action | reason |",
                "|---|---|---|---|---|",
            ]
        )
        if not self.promotion_queue:
            lines.append("| none |  |  |  |  |")
        for action in self.promotion_queue:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(action.citation_key),
                        _cell(_tier_label(action.current_tier)),
                        _cell(_tier_label(action.target_tier)),
                        _cell(action.action),
                        _cell(action.reason),
                    ]
                )
                + " |"
            )
        return "\n".join(lines) + "\n"


def run_citation_gate(
    *,
    manuscript_md: str | None = None,
    citations: list[Citation] | None = None,
    ledger: ClaimLedger | None = None,
    require_tier: CitationTier = CitationTier.TIER_3,
) -> CitationGateReport:
    """Gate manuscript citations against the required verification tier."""
    if citations is not None:
        statuses = [_status_from_citation(citation, require_tier) for citation in citations]
    elif manuscript_md is not None:
        extracted = extract_citations_from_text(manuscript_md, source_file="<manuscript_md>")
        statuses = [_status_from_citation(citation, require_tier) for citation in extracted]
    elif ledger is not None:
        statuses = [_status_from_link(link, ledger, require_tier) for link in ledger.citation_links]
    else:
        raise ValueError("provide manuscript_md, citations, or ledger")

    blocked = sorted(
        [status for status in statuses if status.blocked],
        key=_status_sort_key,
    )
    promotion_queue = sorted(
        [_promotion_action(status) for status in blocked],
        key=_action_sort_key,
    )
    return CitationGateReport(
        ok=not blocked,
        statuses=statuses,
        blocked=blocked,
        promotion_queue=promotion_queue,
    )


def _status_from_citation(
    citation: Citation,
    require_tier: CitationTier,
) -> CitationTierStatus:
    tier = CitationTier.from_verification_status(citation.status)
    return CitationTierStatus(
        citation_key=_citation_key(citation),
        tier=tier,
        status=citation.status,
        blocked=_is_blocked(tier, require_tier),
        claim_text=citation.claim,
        source=_citation_source(citation),
    )


def _status_from_link(
    link: CitationLink,
    ledger: ClaimLedger,
    require_tier: CitationTier,
) -> CitationTierStatus:
    return CitationTierStatus(
        citation_key=link.citation_key,
        tier=link.tier,
        status=link.status,
        blocked=_is_blocked(link.tier, require_tier),
        claim_text=_claim_text(ledger, link.claim_id),
        source=link.claim_id,
    )


def _is_blocked(tier: CitationTier | None, require_tier: CitationTier) -> bool:
    return tier is None or tier.rank < require_tier.rank


def _promotion_action(status: CitationTierStatus) -> PromotionAction:
    action: str
    reason: str
    if status.status in {VerificationStatus.SUSPECT, VerificationStatus.CONTRADICTED}:
        action = "RESOLVE: this citation is suspect/contradicted — do not cite until fixed"
        reason = "The verifier marked the citation as unsafe to cite."
    elif status.tier is CitationTier.TIER_2:
        action = "fetch full text and extract a verbatim quote with section label (-> Tier-3)"
        reason = "Tier-2 abstract support is below the Tier-3 manuscript gate."
    elif status.tier is CitationTier.TIER_1:
        action = "fetch the abstract and confirm it supports the claim (-> Tier-2)"
        reason = "Tier-1 API existence is below the Tier-3 manuscript gate."
    elif _has_identifier(status.citation_key):
        action = "verify DOI/PMID exists (Tier-1), then fetch abstract"
        reason = "The citation has an identifier but has not been verified into the tier ladder."
    else:
        action = "find the DOI/PMID for this citation; it cannot be tiered yet"
        reason = "Untiered citations without DOI/PMID evidence cannot enter the tier ladder."
    return PromotionAction(
        citation_key=status.citation_key,
        current_tier=status.tier,
        target_tier=CitationTier.TIER_3,
        action=action,
        reason=reason,
    )


def _citation_key(citation: Citation) -> str:
    if citation.doi:
        return citation.doi
    if citation.pmid:
        return citation.pmid
    author_year = f"{citation.authors} {citation.year}".strip()
    if author_year and citation.year:
        return author_year
    return citation.raw_text


def _citation_source(citation: Citation) -> str:
    if citation.source_file and citation.line_number:
        return f"{citation.source_file}:{citation.line_number}"
    return citation.source_file


def _claim_text(ledger: ClaimLedger, claim_id: str) -> str:
    for claim in ledger.claims:
        if claim.claim_id == claim_id:
            return claim.text
    return ""


def _has_identifier(citation_key: str) -> bool:
    normalized = citation_key.strip().lower()
    return normalized.startswith("10.") or normalized.isdigit()


def _status_sort_key(status: CitationTierStatus) -> tuple[int, str]:
    return (_tier_rank(status.tier), status.citation_key)


def _action_sort_key(action: PromotionAction) -> tuple[int, str]:
    return (_tier_rank(action.current_tier), action.citation_key)


def _tier_rank(tier: CitationTier | None) -> int:
    return 0 if tier is None else tier.rank


def _tier_label(tier: CitationTier | None) -> str:
    return "untiered" if tier is None else tier.value


def _status_label(status: VerificationStatus | None) -> str:
    return "unknown" if status is None else status.value


def _cell(value: str) -> str:
    return value.replace("\n", " ").replace("|", "\\|")


__all__ = [
    "CitationGateReport",
    "CitationTierStatus",
    "PromotionAction",
    "run_citation_gate",
]
