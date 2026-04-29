"""Data structures for paper verification and claim matching."""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field

from vaultlab.research.paper import Paper

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-sonnet-4-6-20250514"


@dataclass
class VerificationResult:
    """Result of checking whether a paper exists across APIs."""

    exists: bool
    paper: Paper | None
    sources_checked: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "exists": self.exists,
            "paper": self.paper.to_dict() if self.paper else None,
            "sources_checked": self.sources_checked,
            "confidence": self.confidence,
        }


@dataclass
class ClaimMatch:
    """Result of matching a claim against a paper's text."""

    supported: str  # "supported", "unsupported", "partial", "unrelated"
    evidence_chunk: str  # actual text passage from the paper
    chunk_location: str  # "abstract", "results p3", "discussion"
    confidence: float  # 0.0-1.0
    reasoning: str  # explanation of why it matches/doesn't

    def to_dict(self) -> dict:
        return {
            "supported": self.supported,
            "evidence_chunk": self.evidence_chunk,
            "chunk_location": self.chunk_location,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }


@dataclass
class EvidenceRecord:
    """Complete evidence record for a single citation verification."""

    citation_text: str
    verification: VerificationResult
    claim_match: ClaimMatch | None = None
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "citation_text": self.citation_text,
            "verification": self.verification.to_dict(),
            "claim_match": self.claim_match.to_dict() if self.claim_match else None,
            "timestamp": self.timestamp,
        }


def match_claim_with_llm(
    claim: str,
    text: str,
    text_source: str = "abstract",
    anthropic_client=None,
    model: str | None = None,
) -> ClaimMatch:
    """Use Claude to assess whether paper text supports a claim.

    Args:
        claim: The claim being made about the paper.
        text: The paper text to check against (abstract or full text).
        text_source: Where the text came from ("abstract", "full_text").
        anthropic_client: An anthropic.Anthropic() instance. Created if None.
        model: Model ID override. Defaults to claude-sonnet-4-6.

    Returns:
        ClaimMatch with evidence chunk and reasoning.
    """
    if not model:
        model = os.environ.get("BOBBY_CITATIONS_MODEL", _DEFAULT_MODEL)

    if anthropic_client is None:
        try:
            import anthropic

            anthropic_client = anthropic.Anthropic()
        except Exception as e:
            logger.warning("Could not create Anthropic client: %s", e)
            return ClaimMatch(
                supported="unrelated",
                evidence_chunk="",
                chunk_location=text_source,
                confidence=0.0,
                reasoning=f"Error: could not initialize Anthropic client: {e}",
            )

    system_prompt = (
        "You are a scientific claim verifier. Given a claim and paper text, "
        "determine if the text supports the claim. "
        "Extract the exact passage that supports or contradicts it.\n\n"
        "Respond with ONLY a JSON object (no markdown fencing):\n"
        '{"supported": "supported"|"unsupported"|"partial"|"unrelated", '
        '"evidence_chunk": "exact quote from the text", '
        '"chunk_location": "where in the text (e.g. abstract, results paragraph 3)", '
        '"confidence": 0.0-1.0, '
        '"reasoning": "brief explanation"}'
    )

    user_prompt = f'Claim: "{claim}"\n\nPaper text ({text_source}):\n"{text[:8000]}"'

    try:
        response = anthropic_client.messages.create(
            model=model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = response.content[0].text.strip()

        # Handle potential markdown code fencing (with or without newline)
        if raw.startswith("```"):
            raw = re.sub(r"^```\w*\n?", "", raw)
            raw = raw.rsplit("```", 1)[0].strip()

        data = json.loads(raw)
        return ClaimMatch(
            supported=data.get("supported", "unrelated"),
            evidence_chunk=data.get("evidence_chunk", ""),
            chunk_location=data.get("chunk_location", text_source),
            confidence=float(data.get("confidence", 0.0)),
            reasoning=data.get("reasoning", ""),
        )
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON response for claim matching")
        return ClaimMatch(
            supported="unrelated",
            evidence_chunk="",
            chunk_location=text_source,
            confidence=0.0,
            reasoning="Error: LLM returned non-JSON response",
        )
    except Exception as e:
        logger.warning("Claim matching failed: %s", e)
        return ClaimMatch(
            supported="unrelated",
            evidence_chunk="",
            chunk_location=text_source,
            confidence=0.0,
            reasoning=f"Error: {e}",
        )
