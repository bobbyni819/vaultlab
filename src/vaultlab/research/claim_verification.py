"""Claim-verification step for narrator-produced arc paragraphs.

Background
----------
The ``methods_critic`` role in the adversarial arc-narration meeting
sometimes catches overclaims (the canonical case: a draft saying
"Schurch 2020 cellular neighborhoods PREDICT survival" when Schurch 2020
was Tier-C and the system had no PDF to verify). But that catch is
opportunistic — the critic notices it because the claim happens to set
off heuristics in the role prompt.

This module mirrors the *figure-understanding* Step 4 verify pattern
(:class:`vaultlab.figures.understand._tasks.VerifyAnnotationTask`) and
applies it to text claims:

1. **Extract** — split a draft paragraph into individual factual claims
   (deterministic; no LLM needed).
2. **Verify** — for each claim, ask an LLM-side callback (or any
   ``ClaimVerifier`` callable) to re-read the cited papers' summaries
   and decide whether the claim is *supported*, *partial*, *unsupported*,
   or *unverifiable*. The verifier returns an evidence quote.
3. **Render** — produce a structured :class:`ClaimVerificationResult`
   that downstream callers (the synthesizer's revise step, or the arc's
   provenance receipt) can consume.

The pattern matches the prepare/render/orchestrate split used in
:mod:`~vaultlab.research.picker`, :mod:`~vaultlab.research.binning`, and
:mod:`~vaultlab.research.summarize` — so callers wire it into their
existing callback pipeline without a new architectural surface.

Verdicts
--------
* ``"supported"`` — the claim is present in at least one cited paper's
  summary, with a quotable [pN]-anchored statement that matches.
* ``"partial"`` — the cited paper supports a *weaker* version of the
  claim. Suggests softening (e.g. "shows survival association" rather
  than "predicts survival").
* ``"unsupported"`` — the cited paper does not support the claim. The
  paragraph should remove or revise the claim.
* ``"unverifiable"`` — no citation in the paragraph maps to a Tier-A
  summary we can read (e.g. paper is Tier-C, no PDF was acquired). The
  claim should either be downgraded ("appears to show X") or removed.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


VALID_VERDICTS: frozenset[str] = frozenset({"supported", "partial", "unsupported", "unverifiable"})


@dataclass(frozen=True)
class Claim:
    """One factual claim extracted from an arc paragraph.

    Attributes:
        text: The claim sentence, lightly cleaned (no leading bullet,
            no trailing period removed).
        cited_dois: DOIs the claim cites (lower-cased), as parsed from
            wikilinks in the paragraph. Empty when the claim does not
            cite a specific paper (e.g. transitional sentences).
        position: 0-indexed position in the paragraph (for line-up
            with the verifier output).
    """

    text: str
    cited_dois: tuple[str, ...]
    position: int = 0


@dataclass(frozen=True)
class ClaimVerificationTask:
    """A prepared claim-verification task ready for an LLM callback.

    Attributes:
        paragraph: The full draft paragraph being verified (for context).
        section_id: Which arc section this paragraph belongs to (e.g.
            ``"history"``, ``"sota"``, or any custom-structure id).
        claims: List of :class:`Claim` extracted from the paragraph.
        cited_summaries: Mapping doi -> summary text snippet (the
            ``key_findings`` block + TL;DR from the PaperSummary). The
            verifier reads these to ground each claim.
        system: System-message guard rails.
        prompt: User-message prompt the LLM should respond to.
        response_schema: JSON schema describing the expected response.
    """

    paragraph: str
    section_id: str
    claims: list[Claim]
    cited_summaries: dict[str, str]
    system: str
    prompt: str
    response_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClaimVerification:
    """A verifier's verdict on a single claim.

    Attributes:
        claim: The original :class:`Claim` being verified.
        verdict: One of :data:`VALID_VERDICTS`.
        evidence: A short quote from the cited paper's summary that
            supports or contradicts the claim. Empty for ``unverifiable``.
        evidence_doi: DOI of the paper the evidence quote comes from
            (lower-cased). Empty for ``unverifiable``.
        revision_suggestion: Optional rewording to address ``partial`` or
            ``unsupported`` verdicts.
    """

    claim: Claim
    verdict: str
    evidence: str = ""
    evidence_doi: str = ""
    revision_suggestion: str = ""


@dataclass
class ClaimVerificationResult:
    """Aggregate outcome of a claim-verification pass.

    Attributes:
        verifications: One :class:`ClaimVerification` per claim from the
            task, in input order.
        verdict_counts: ``{"supported": n, "partial": n, ...}`` summary.
        any_revisions_suggested: Convenience flag — True if any
            verification has a non-empty revision_suggestion.
    """

    verifications: list[ClaimVerification] = field(default_factory=list)
    verdict_counts: dict[str, int] = field(default_factory=dict)
    any_revisions_suggested: bool = False


# Type alias for the LLM-side verifier callback.
ClaimVerifier = Callable[[ClaimVerificationTask], dict[str, Any]]


# ---------------------------------------------------------------------------
# Claim extraction (deterministic)
# ---------------------------------------------------------------------------


# Wikilink pattern: [[<doi-slug>|<label>]] or [[<doi-slug>]].
# Slug shape: starts with literal "10." (the DOI prefix), followed by the
# registrant (digits, length varies by registrant — usually 4 but sometimes
# 1-3 for old / test DOIs), an underscore, then arbitrary chars until the
# pipe or closing bracket.
_WIKILINK_RE = re.compile(r"\[\[(?P<slug>10\.\d+_[^|\]]+)(?:\|[^\]]+)?\]\]")


def _slug_to_doi(slug: str) -> str:
    """Turn a wikilink slug ``10.1016_j.cell.2018.07.010`` into a DOI."""
    s = slug.strip().replace(" ", "")
    # Remove common artifact extensions defensively.
    for ext in (".pdf", ".md", ".json", ".xml", ".html", ".htm", ".txt"):
        if s.lower().endswith(ext):
            s = s[: -len(ext)]
    parts = s.split("_", 1)
    if len(parts) != 2:
        return s.lower()
    # Replace remaining "_" → "/" only on the FIRST split (registrant boundary).
    return (parts[0] + "/" + parts[1]).lower()


def extract_claims_from_paragraph(paragraph: str) -> list[Claim]:
    """Split a paragraph into individual claims with cited-DOI annotations.

    Splits on sentence boundaries (``.``, ``?``, ``!`` followed by space
    or end-of-string), then for each sentence pulls every wikilink and
    records the cited DOI list. No LLM call.

    Args:
        paragraph: Markdown text of one arc section. Wikilinks like
            ``[[10.1016_j.cell.2018.07.010|Goltsev 2018]]`` are parsed.

    Returns:
        Ordered list of :class:`Claim`. Empty when the paragraph has no
        sentence-like content.
    """
    text = (paragraph or "").strip()
    if not text:
        return []

    # Sentence split — naive but adequate for narrator output, which
    # uses standard punctuation.
    sentence_re = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[\(])")
    raw_sentences = sentence_re.split(text)

    claims: list[Claim] = []
    for i, sentence in enumerate(raw_sentences):
        s = sentence.strip()
        if not s:
            continue
        slugs = _WIKILINK_RE.findall(s)
        # Group 0 only because findall with a single named group returns
        # tuples when there's >1 group; here we want just the slug str.
        cited = tuple(_slug_to_doi(slug) for slug in slugs)
        claims.append(Claim(text=s, cited_dois=cited, position=i))
    return claims


# ---------------------------------------------------------------------------
# Prompt + schema
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = (
    "You are a literature-claim verifier. For each factual claim in a "
    "drafted lineage-arc paragraph, decide whether the cited paper's "
    "summary actually supports the claim. Re-read the supplied summary "
    "snippets carefully. If a claim has a [pN]-anchored statement in the "
    "summary that matches, mark it SUPPORTED and quote the matching "
    "phrase. If the summary supports a weaker version of the claim, mark "
    "it PARTIAL and suggest the weaker rewording. If the summary "
    "contradicts the claim or is silent on it, mark it UNSUPPORTED and "
    "explain. If no cited paper has a Tier-A summary in the supplied set, "
    "mark it UNVERIFIABLE — the claim cannot be checked. Output ONLY a "
    "JSON object matching the schema in the user message — no prose "
    "preamble, no markdown fencing."
)


def claim_verification_response_schema() -> dict[str, Any]:
    """JSON schema for the claim-verification response."""
    return {
        "type": "object",
        "required": ["verifications"],
        "properties": {
            "verifications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["position", "verdict"],
                    "properties": {
                        "position": {
                            "type": "integer",
                            "description": (
                                "0-indexed claim position from the task; "
                                "must match a Claim.position."
                            ),
                        },
                        "verdict": {
                            "type": "string",
                            "enum": sorted(VALID_VERDICTS),
                        },
                        "evidence": {
                            "type": "string",
                            "description": (
                                "Short quote from the cited paper's "
                                "summary supporting/contradicting the "
                                "claim. Empty for 'unverifiable'."
                            ),
                        },
                        "evidence_doi": {
                            "type": "string",
                            "description": ("DOI of the paper the evidence quote comes from."),
                        },
                        "revision_suggestion": {
                            "type": "string",
                            "description": (
                                "Optional rewording for partial / unsupported verdicts."
                            ),
                        },
                    },
                },
            }
        },
    }


def build_claim_verification_prompt(
    *,
    paragraph: str,
    section_id: str,
    claims: list[Claim],
    cited_summaries: dict[str, str],
) -> str:
    """Build the user-message prompt for the claim-verification LLM call."""
    lines: list[str] = [
        f"ARC SECTION: {section_id}",
        "",
        "DRAFTED PARAGRAPH (full context, do not modify):",
        "",
        paragraph.strip(),
        "",
        "CITED PAPER SUMMARIES (use these to verify each claim):",
        "",
    ]
    if not cited_summaries:
        lines.append("(none — no Tier-A summaries available; all claims will be UNVERIFIABLE)")
    else:
        for doi, summary_text in cited_summaries.items():
            lines.append(f"### {doi}")
            lines.append("")
            lines.append(summary_text.strip() or "(empty summary)")
            lines.append("")

    lines.extend(
        [
            "CLAIMS TO VERIFY:",
            "",
        ]
    )
    for claim in claims:
        cite_block = f" cites: [{', '.join(claim.cited_dois)}]" if claim.cited_dois else ""
        lines.append(f"[{claim.position}]{cite_block}  {claim.text}")
    lines.append("")

    lines.extend(
        [
            "OUTPUT FORMAT:",
            "Return ONLY a JSON object:",
            "",
            "{",
            '  "verifications": [',
            (
                '    {"position": 0, "verdict": "supported", '
                '"evidence": "<quote>", "evidence_doi": "<doi>", '
                '"revision_suggestion": ""},'
            ),
            (
                '    {"position": 1, "verdict": "partial", '
                '"evidence": "<weaker quote>", '
                '"evidence_doi": "<doi>", '
                '"revision_suggestion": "<softer wording>"},'
            ),
            "    ...",
            "  ]",
            "}",
            "",
            "Use the EXACT position numbers from the CLAIMS TO VERIFY "
            "list. Skip transitional sentences if needed (omit them from "
            "the output rather than fabricating a verdict).",
        ]
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API: prepare / render / orchestrate
# ---------------------------------------------------------------------------


def prepare_claim_verification_task(
    *,
    paragraph: str,
    section_id: str,
    cited_summaries: dict[str, str],
) -> ClaimVerificationTask:
    """Build a :class:`ClaimVerificationTask`. Does NOT call any LLM.

    Args:
        paragraph: The drafted arc-section paragraph to verify.
        section_id: Which arc section this paragraph belongs to.
        cited_summaries: Mapping doi -> summary text snippet (Tier-A
            papers only). Tier-C citations should be omitted; the
            verifier will mark claims citing them as ``unverifiable``.

    Returns:
        A :class:`ClaimVerificationTask` ready for the verifier callback.
    """
    claims = extract_claims_from_paragraph(paragraph)
    cs = {(k or "").strip().lower(): (v or "") for k, v in cited_summaries.items()}
    prompt = build_claim_verification_prompt(
        paragraph=paragraph,
        section_id=section_id,
        claims=claims,
        cited_summaries=cs,
    )
    return ClaimVerificationTask(
        paragraph=paragraph,
        section_id=section_id,
        claims=claims,
        cited_summaries=cs,
        system=_SYSTEM_PROMPT,
        prompt=prompt,
        response_schema=claim_verification_response_schema(),
    )


def render_verifications_from_response(
    response_json: dict[str, Any] | None,
    task: ClaimVerificationTask,
) -> ClaimVerificationResult:
    """Parse the verifier's JSON response into a structured result.

    Validation rules:

    * Each ``position`` must reference a claim from the task. Unknown
      positions are silently dropped.
    * Each ``verdict`` must be in :data:`VALID_VERDICTS`. Other strings
      are dropped.
    * Claims the verifier didn't return get an automatic
      ``unverifiable`` verdict, since silence == we couldn't verify.

    Args:
        response_json: Parsed JSON from the verifier callback, or None.
        task: The task this response belongs to.

    Returns:
        Populated :class:`ClaimVerificationResult`.
    """
    by_position: dict[int, dict[str, Any]] = {}
    raw_list: list[Any] = []
    if isinstance(response_json, dict):
        maybe = response_json.get("verifications")
        if isinstance(maybe, list):
            raw_list = maybe

    for item in raw_list:
        if not isinstance(item, dict):
            continue
        try:
            pos = int(item.get("position"))
        except (TypeError, ValueError):
            continue
        verdict = str(item.get("verdict") or "").strip().lower()
        if verdict not in VALID_VERDICTS:
            logger.debug("dropped invalid verdict %r at position %d", verdict, pos)
            continue
        # Last write wins on duplicate positions (rare).
        by_position[pos] = {
            "verdict": verdict,
            "evidence": str(item.get("evidence") or "").strip(),
            "evidence_doi": str(item.get("evidence_doi") or "").strip().lower(),
            "revision_suggestion": str(item.get("revision_suggestion") or "").strip(),
        }

    verifications: list[ClaimVerification] = []
    counts: dict[str, int] = dict.fromkeys(sorted(VALID_VERDICTS), 0)
    any_rev = False
    for claim in task.claims:
        entry = by_position.get(claim.position)
        if entry is None:
            ver = ClaimVerification(
                claim=claim,
                verdict="unverifiable",
            )
        else:
            ver = ClaimVerification(
                claim=claim,
                verdict=entry["verdict"],
                evidence=entry["evidence"],
                evidence_doi=entry["evidence_doi"],
                revision_suggestion=entry["revision_suggestion"],
            )
        verifications.append(ver)
        counts[ver.verdict] = counts.get(ver.verdict, 0) + 1
        if ver.revision_suggestion:
            any_rev = True

    return ClaimVerificationResult(
        verifications=verifications,
        verdict_counts=counts,
        any_revisions_suggested=any_rev,
    )


def verify_paragraph_claims(
    *,
    paragraph: str,
    section_id: str,
    cited_summaries: dict[str, str],
    verifier_callback: ClaimVerifier | None = None,
    max_retries: int = 1,
) -> ClaimVerificationResult:
    """High-level helper: prepare → call verifier → render, with retry.

    When no callback is given, returns a result with every claim marked
    ``unverifiable`` (the safe-default, equivalent to "we couldn't run
    the verifier").

    When a callback is given, calls it via
    :func:`vaultlab.research.retry.retry_with_feedback` so that an
    exception or empty/malformed response on the first attempt gets a
    bounded retry with the error context appended to the task prompt.
    The verifier sees what went wrong and can self-correct.

    Args:
        paragraph: The drafted arc-section paragraph to verify.
        section_id: Which arc section this paragraph belongs to.
        cited_summaries: Mapping doi -> summary text snippet.
        verifier_callback: Optional :data:`ClaimVerifier`.
        max_retries: How many retry-with-feedback attempts to allow on
            failure (default 1, matching AI-Scientist's pattern). Set
            to 0 to disable retries entirely.
    """
    task = prepare_claim_verification_task(
        paragraph=paragraph,
        section_id=section_id,
        cited_summaries=cited_summaries,
    )
    if verifier_callback is None:
        return render_verifications_from_response(None, task)

    from vaultlab.research.retry import retry_with_feedback

    retry_result = retry_with_feedback(
        verifier_callback,
        task,
        max_retries=max_retries,
    )
    if not retry_result.succeeded:
        # All attempts failed — log the final failure mode and fall back
        # to unverifiable for every claim.
        if retry_result.attempts:
            last = retry_result.attempts[-1]
            logger.warning(
                "verifier_callback exhausted retries (%d attempts, last "
                "failure_mode=%s); returning unverifiable verdicts",
                len(retry_result.attempts),
                last.failure_mode,
            )
        return render_verifications_from_response(None, task)
    return render_verifications_from_response(retry_result.response, task)


__all__ = [
    "VALID_VERDICTS",
    "Claim",
    "ClaimVerification",
    "ClaimVerificationResult",
    "ClaimVerificationTask",
    "ClaimVerifier",
    "build_claim_verification_prompt",
    "claim_verification_response_schema",
    "extract_claims_from_paragraph",
    "prepare_claim_verification_task",
    "render_verifications_from_response",
    "verify_paragraph_claims",
]
