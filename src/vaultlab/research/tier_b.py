"""Tier-B abstract-only summarization.

Background
----------
Today the corpus ships papers in two states:

* **Tier A** — PDF acquired, full-text Claude read with [pN] page anchors.
* **Tier C** — no PDF; we emit a metadata stub with empty ``tldr``,
  ``why_it_matters``, ``methods_summary``, and ``key_findings`` fields.

The Tier-C tier is wasteful: the candidate metadata (from PubMed /
S2 / CrossRef / OpenAlex) typically carries a 200-400-word abstract
that *would* support a meaningful short summary, but the existing
``summarize_one`` function short-circuits to a stub before any LLM
call happens.

This module fills the gap. **Tier B** is an abstract-only
summarization: a short LLM call that reads the abstract + author /
journal / year metadata and produces a narrower version of the
Tier-A schema (no methods detail, no [pN] anchors, no extracted
references — just TL;DR, 1-2 "Why it matters" bullets, and a
provenance caveat noting the summary is abstract-derived).

Why this matters
----------------
Bobby surfaced this on 2026-05-01: papers like Black, Phillips,
Hickey et al. 2021 *Nature Protocols* — the canonical CODEX-protocols
paper, paywalled at Nature Protocols — are clearly important for any
CODEX-related arc but stay invisible to the narrator stage when
they're Tier C. Tier-B summaries become **citable** by the narrator
(with ``(abstract-only)`` notation indicating shallower provenance)
without requiring full-text acquisition.

Tier-B is the prerequisite for Bobby's principle "default to MORE
context — let the system read more" because it raises the
*proportion* of corpus papers the narrator can substantively cite
from ~20% (Tier-A only) to ~80% (Tier-A + Tier-B, since most papers
have abstracts even when paywalled).

Architecture
------------
``prepare_tier_b_task(paper, corpus, corpus_metrics, kb_root)`` builds
a ``Tier_B_Task`` containing the prompt + response schema. The
Claude-Code-callable path passes the task to a reader callback (same
mechanism as Tier-A); the SDK path calls a short Anthropic messages
API request with the abstract as text input.

``render_tier_b_summary(task, response, ...)`` applies the LLM response
to a ``PaperSummary`` instance with ``tier="B"`` and a provenance
caveat baked into ``methods_summary``.

``should_run_tier_b(paper)`` is the gate: returns ``True`` when no
PDF was acquired AND the abstract is at least 100 characters long
(short abstracts are usually search-result snippets, not real
abstracts, and don't yield meaningful summaries).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vaultlab.kb.paths import slugify_doi


# ---------------------------------------------------------------------------
# Gate: when to run Tier-B
# ---------------------------------------------------------------------------


# Minimum abstract length to bother summarizing. Below this, the
# "abstract" is usually a truncated search-result snippet (e.g.,
# CrossRef sometimes returns just a title fragment) and won't yield
# a meaningful summary.
MIN_ABSTRACT_CHARS = 100


def should_run_tier_b(
    *,
    pdf_acquired: bool,
    abstract: str,
) -> bool:
    """Return True if this paper qualifies for Tier-B summarization.

    Tier-B fires when:
    * No PDF was acquired (so Tier-A is impossible).
    * The abstract is at least :data:`MIN_ABSTRACT_CHARS` characters.

    Args:
        pdf_acquired: Whether a Tier-A summary will be written.
        abstract: The abstract text from the candidate metadata.

    Returns:
        True if Tier-B should run; False otherwise.
    """
    if pdf_acquired:
        return False
    if not abstract:
        return False
    if len(abstract.strip()) < MIN_ABSTRACT_CHARS:
        return False
    return True


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


_TIER_B_SYSTEM_PROMPT = """\
You are summarizing a research paper from its ABSTRACT ONLY (no
full text). Your summary will be marked Tier-B and will carry a
provenance caveat indicating the summary is abstract-derived.

GUARDRAILS:
- DO NOT invent details that aren't in the abstract. If the abstract
  doesn't say it, your summary doesn't say it.
- DO NOT fabricate quantitative claims (numbers of cells, p-values,
  fold-changes) unless they appear verbatim in the abstract.
- DO NOT write "[pN]" page anchors — Tier-B summaries don't have
  page provenance.
- Hedged voice when the abstract is itself hedged. "Reports" /
  "claims" / "according to the abstract" rather than "shows" /
  "proves."

OUTPUT RULES:
- TL;DR: 2 sentences. First names the paper's central contribution
  (method / finding / framework). Second names the practical
  consequence or scope.
- why_it_matters: 1-2 bullets. Each is a single sentence on why this
  paper is cited / what role it plays in its field. May draw on
  author affiliations, journal, year if relevant.
- role_context: 1 sentence describing where this paper sits in its
  field's lineage based on title + abstract + author network.
"""


def build_tier_b_prompt(
    *,
    paper_metadata: dict[str, Any],
    abstract: str,
    role_hint: str = "",
) -> str:
    """Build the user-message text for the Tier-B summarization call.

    Args:
        paper_metadata: ``title``, ``authors``, ``year``, ``journal``,
            ``doi`` from the candidate.
        abstract: The abstract text.
        role_hint: Optional pre-computed role string (e.g.,
            ``"foundational"``, ``"sota"``) from corpus metrics.

    Returns:
        The full user-message prompt.
    """
    title = paper_metadata.get("title", "(unknown title)")
    authors_list = paper_metadata.get("authors", [])
    if isinstance(authors_list, list):
        authors = ", ".join(str(a) for a in authors_list[:5])
        if len(authors_list) > 5:
            authors += f" + {len(authors_list) - 5} others"
    else:
        authors = str(authors_list)
    year = paper_metadata.get("year", "?")
    journal = paper_metadata.get("journal", "?")
    doi = paper_metadata.get("doi", "?")

    role_line = (
        f"\nROLE HINT (from corpus metrics): {role_hint}\n"
        if role_hint
        else ""
    )

    return f"""\
PAPER METADATA:
- DOI: {doi}
- Title: {title}
- Authors: {authors}
- Year: {year}
- Journal: {journal}{role_line}

ABSTRACT:
{abstract}

TASK:
Produce a Tier-B summary of this paper from its abstract only.
Return ONLY a JSON object matching this schema:

{{
  "tldr": "<2 sentences. First names the central contribution, second names practical consequence/scope.>",
  "why_it_matters": [
    "<bullet 1: why this paper is cited / what role it plays>",
    "<optional bullet 2: additional context>"
  ],
  "role_context": "<1 sentence on where this paper sits in its field's lineage>"
}}

NO markdown fencing, NO commentary outside the JSON, NO [pN] anchors,
NO fabricated numbers.
"""


def tier_b_response_schema() -> dict[str, Any]:
    """JSON schema for a Tier-B response.

    Narrower than :func:`summarize.summary_response_schema` —
    no methods_summary, no key_findings, no extracted_references.
    """
    return {
        "type": "object",
        "required": ["tldr", "why_it_matters", "role_context"],
        "properties": {
            "tldr": {
                "type": "string",
                "description": "Exactly 2 sentences summarizing the abstract.",
            },
            "why_it_matters": {
                "type": "array",
                "items": {"type": "string"},
                "description": "1-2 bullets on why this paper is cited.",
                "minItems": 1,
                "maxItems": 2,
            },
            "role_context": {
                "type": "string",
                "description": "1 sentence on lineage role.",
            },
        },
    }


# ---------------------------------------------------------------------------
# Task envelope (Claude-Code-callable path)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Tier_B_Task:
    """A prepared Tier-B summarization task.

    Attributes:
        doi: Lower-cased DOI.
        paper_metadata: title / authors / year / journal / doi.
        abstract: The abstract text being summarized.
        prompt: Full user-message prompt.
        system_prompt: System message (the Tier-B guardrails).
        response_schema: JSON schema for validation.
        output_path: Canonical destination for the summary markdown.
        role_hint: The role string from corpus metrics (passed in for
            provenance).
    """

    doi: str
    paper_metadata: dict[str, Any]
    abstract: str
    prompt: str
    system_prompt: str
    response_schema: dict[str, Any]
    output_path: Path
    role_hint: str = ""


def prepare_tier_b_task(
    *,
    doi: str,
    paper_metadata: dict[str, Any],
    abstract: str,
    output_path: Path,
    role_hint: str = "",
) -> Tier_B_Task:
    """Build a :class:`Tier_B_Task` ready for the reader callback or SDK call.

    Args:
        doi: Lower-cased DOI of the paper.
        paper_metadata: Identity fields (title, authors, year, journal, doi).
        abstract: The abstract text.
        output_path: Where the summary markdown will be written.
        role_hint: Optional role string from corpus metrics.

    Returns:
        A :class:`Tier_B_Task` object.
    """
    prompt = build_tier_b_prompt(
        paper_metadata=paper_metadata,
        abstract=abstract,
        role_hint=role_hint,
    )
    return Tier_B_Task(
        doi=doi,
        paper_metadata=paper_metadata,
        abstract=abstract,
        prompt=prompt,
        system_prompt=_TIER_B_SYSTEM_PROMPT,
        response_schema=tier_b_response_schema(),
        output_path=output_path,
        role_hint=role_hint,
    )


# ---------------------------------------------------------------------------
# Response → PaperSummary
# ---------------------------------------------------------------------------


def apply_tier_b_response(
    *,
    summary,  # PaperSummary; not type-imported to avoid circular dep
    response: dict[str, Any],
) -> None:
    """Apply a Tier-B LLM response to a :class:`PaperSummary` in place.

    Sets ``tier="B"``, populates ``tldr`` and ``why_it_matters``, and
    bakes the provenance caveat into ``methods_summary``. ``key_findings``
    and ``extracted_references`` stay empty for Tier-B.

    Args:
        summary: The :class:`PaperSummary` to mutate.
        response: The LLM response dict (validated against
            :func:`tier_b_response_schema`).
    """
    summary.tier = "B"
    summary.tldr = (response.get("tldr") or "").strip()
    summary.why_it_matters = list(response.get("why_it_matters") or [])

    # Bake the role_context + Tier-B provenance into methods_summary so
    # downstream rendering captures it without needing a new field.
    role_context = (response.get("role_context") or "").strip()
    caveat_lines = [
        "**Tier-B summary provenance**: this summary is built from the"
        " paper's abstract + corpus metadata, NOT from the full PDF."
        " Specific quantitative claims and methodological details are"
        " UNVERIFIED. To upgrade to Tier-A, acquire the PDF and re-run"
        " summarization.",
    ]
    if role_context:
        caveat_lines.insert(0, f"**Role context**: {role_context}")
    summary.methods_summary = "\n\n".join(caveat_lines)

    # Tier-B leaves these empty by design:
    summary.key_findings = []
    summary.extracted_references = []

    summary.extracted_at = datetime.now(timezone.utc).isoformat()
    summary.extracted_via = "claude-tier-b"
    summary.source_pdf = ""  # No PDF → empty path


def render_tier_b_summary(
    *,
    task: Tier_B_Task,
    response: dict[str, Any],
    base_summary,  # PaperSummary
) -> "PaperSummary":  # noqa: F821
    """Apply a Tier-B response to ``base_summary`` and return it.

    Convenience wrapper around :func:`apply_tier_b_response` that
    returns the mutated summary for chaining.
    """
    apply_tier_b_response(summary=base_summary, response=response)
    return base_summary


__all__ = [
    "MIN_ABSTRACT_CHARS",
    "Tier_B_Task",
    "apply_tier_b_response",
    "build_tier_b_prompt",
    "prepare_tier_b_task",
    "render_tier_b_summary",
    "should_run_tier_b",
    "tier_b_response_schema",
]
