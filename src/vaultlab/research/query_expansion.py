"""Multi-query expansion for the literature-search step.

Rationale
---------
Sending one query string to one search engine is fragile: the wording you
chose might match how a 2018 review of the field titled itself, but miss
how a 2024 SOTA paper titled itself. To compensate, we expand the topic
into multiple framings — methods-paper phrasing, review-paper phrasing,
clinical-application phrasing, recent-benchmark phrasing — and run each
variant against every source. After all variants have run, the results
are deduplicated by DOI exactly as in the single-query case.

Two execution paths
-------------------
1. **LLM expansion (preferred when available).** Pass a
   ``query_expander_callback`` that consumes a :class:`QueryExpansionTask`
   and returns ``{"variants": ["...", "...", ...]}``. The callback can be
   Claude Code via the standard tool-using harness, or any callable
   matching :data:`QueryExpansionCallback`.

2. **Deterministic fallback (no LLM needed).** When no callback is given,
   :func:`expand_topic_deterministic` produces a small set of common
   scholarly framings (review / methods / applications / recent /
   benchmark) by string templating. Useful for offline tests and when the
   user has not configured a callback.

Both paths produce a ``list[str]`` of query variants, which is then passed
to :func:`vaultlab.research.search.unified_search` via its ``queries=``
parameter.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Public typing surface
# ---------------------------------------------------------------------------


QueryExpansionCallback = Callable[["QueryExpansionTask"], dict[str, Any]]
"""A function that turns a :class:`QueryExpansionTask` into a JSON dict.

Expected shape::

    {"variants": ["...", "...", ...]}
"""


@dataclass
class QueryExpansionTask:
    """Data + prompts for the query-expansion LLM call.

    Attributes:
        topic: User-supplied topic, raw.
        target_n: How many variants to produce (typically 4-6).
        prompt: User-message body explaining what variants to produce.
        system_prompt: System-message guard rails.
        response_schema: JSON schema describing the expected response.
    """

    topic: str
    target_n: int
    prompt: str
    system_prompt: str
    response_schema: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Schema + prompt building
# ---------------------------------------------------------------------------


def query_expansion_response_schema(target_n: int) -> dict[str, Any]:
    """JSON schema for the expansion response."""
    return {
        "type": "object",
        "properties": {
            "variants": {
                "type": "array",
                "minItems": 1,
                "maxItems": max(1, target_n),
                "items": {"type": "string"},
                "description": (
                    "List of up to target_n distinct query strings, each one "
                    "framing the topic from a different angle (methods, "
                    "review, applications, recent advances, benchmark, etc.)."
                ),
            }
        },
        "required": ["variants"],
        "additionalProperties": False,
    }


_SYSTEM_PROMPT = (
    "You are a scholarly-literature query expansion assistant. Given a "
    "research topic, produce a small set of distinct search queries that "
    "together cover the conversation around that topic. Each variant should "
    "rephrase the topic from a different angle so that the union of search "
    "results is broader than what any single phrasing would return.\n\n"
    "Good variants cover: (a) the methods/instrumentation perspective, "
    "(b) the review / state-of-the-art perspective, (c) the applications / "
    "clinical / domain perspective, (d) recent advances or benchmarks, "
    "(e) historically related precursors. Use scientific terminology that "
    "would actually appear in titles/abstracts in the field. Do not produce "
    "boolean queries — produce natural keyword phrases that work in PubMed, "
    "Semantic Scholar, CrossRef. Keep each variant under 12 words."
)


def prepare_query_expansion_task(
    topic: str, *, target_n: int = 5
) -> QueryExpansionTask:
    """Build a :class:`QueryExpansionTask` for ``topic``."""
    user_prompt = (
        f"Topic: {topic}\n\n"
        f"Produce up to {target_n} distinct search-query variants that "
        f"together cover the literature on this topic. Return as JSON "
        f'matching the schema: {{"variants": ["...", "...", ...]}}.\n\n'
        "Aim for breadth across angles: methods, review/SOTA, applications, "
        "recent benchmarks, historical precursors. Each variant should be a "
        "natural-language keyword phrase under 12 words."
    )
    return QueryExpansionTask(
        topic=topic,
        target_n=int(target_n),
        prompt=user_prompt,
        system_prompt=_SYSTEM_PROMPT,
        response_schema=query_expansion_response_schema(target_n),
    )


# ---------------------------------------------------------------------------
# Response rendering
# ---------------------------------------------------------------------------


def render_queries_from_response(
    response: dict[str, Any] | str, *, topic: str, target_n: int = 5
) -> list[str]:
    """Parse a callback response into a clean list of query variants.

    The original ``topic`` is always included as the first variant so the
    caller's literal phrasing is preserved (it tends to match conventional
    search expectations).

    Args:
        response: Either a dict matching the response schema, or a JSON
            string the callback returned.
        topic: The original topic — always prepended to the variant list.
        target_n: Cap on returned variants (defaults to 5).

    Returns:
        Ordered list of query strings, deduplicated case-insensitively,
        with the original topic at index 0.
    """
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except json.JSONDecodeError:
            response = {}

    raw_variants: list[str] = []
    if isinstance(response, dict):
        v = response.get("variants")
        if isinstance(v, list):
            raw_variants = [str(x).strip() for x in v if str(x).strip()]

    # Always lead with the literal topic.
    out: list[str] = [topic.strip()]
    seen_lower: set[str] = {topic.strip().lower()}
    for q in raw_variants:
        q_lower = q.lower()
        if q_lower in seen_lower:
            continue
        out.append(q)
        seen_lower.add(q_lower)
        if len(out) >= max(1, target_n):
            break
    return out


# ---------------------------------------------------------------------------
# Deterministic fallback (no LLM required)
# ---------------------------------------------------------------------------


def expand_topic_deterministic(topic: str, *, target_n: int = 5) -> list[str]:
    """Produce query variants from string templates — no LLM needed.

    The variants are simple suffix expansions over the topic that bias
    each query toward a different scholarly angle:

    1. The literal topic.
    2. ``"<topic> review"`` — pulls in review/SOTA articles.
    3. ``"<topic> methods"`` — pulls in methods/protocol papers.
    4. ``"<topic> applications"`` — pulls in clinical / application papers.
    5. ``"<topic> recent advances"`` — biases toward newer work.
    6. ``"<topic> benchmark comparison"`` — pulls in benchmarking studies.

    Args:
        topic: User-supplied topic.
        target_n: How many variants to return (capped at the table above).

    Returns:
        Ordered list of variants. Always at least one (the literal topic).
    """
    base = topic.strip()
    if not base:
        return [topic]
    suffixed = [
        base,
        f"{base} review",
        f"{base} methods",
        f"{base} applications",
        f"{base} recent advances",
        f"{base} benchmark comparison",
    ]
    return suffixed[: max(1, target_n)]


# ---------------------------------------------------------------------------
# High-level helper
# ---------------------------------------------------------------------------


def expand_query(
    topic: str,
    *,
    target_n: int = 5,
    callback: QueryExpansionCallback | None = None,
) -> list[str]:
    """Produce query variants for ``topic`` using a callback or fallback.

    Args:
        topic: The user-supplied topic.
        target_n: Target number of variants (default 5).
        callback: Optional :data:`QueryExpansionCallback`. When ``None``,
            uses :func:`expand_topic_deterministic`.

    Returns:
        Ordered list of query strings. The literal topic is always first.
    """
    if callback is None:
        return expand_topic_deterministic(topic, target_n=target_n)

    task = prepare_query_expansion_task(topic, target_n=target_n)
    try:
        response = callback(task)
    except Exception:
        # Defensive — fall back to deterministic variants if the callback
        # raises. We don't want the search step to die because the LLM
        # had a transient failure.
        return expand_topic_deterministic(topic, target_n=target_n)
    return render_queries_from_response(
        response, topic=topic, target_n=target_n
    )


__all__ = [
    "QueryExpansionTask",
    "QueryExpansionCallback",
    "query_expansion_response_schema",
    "prepare_query_expansion_task",
    "render_queries_from_response",
    "expand_topic_deterministic",
    "expand_query",
]
