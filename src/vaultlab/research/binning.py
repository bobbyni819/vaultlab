"""LLM-driven year-bucket assignment for vaultlab corpora.

Background
----------
:func:`vaultlab.research.graph_metrics._year_bucket_assignments` assigns
each paper to ``"history" | "development" | "sota"`` by ranking the
within-corpus year distribution and slicing into quartiles. That works
when the publication years span a long arc — but on real corpora it
shipped EMPTY history buckets. Bobby (2026-04-30, after the L4 CODEX
run produced slides reading "(no history-bucket papers in corpus)"):

    "I really want you to actually like pipe the results into yourself
    rather than relying only on deterministic code to decide like what
    band say like a file would belong to ... read the abstract but even
    like full paper reading would actually still be good ... actually
    read them about that and decide on what should belong where because
    given the amount of papers that we are like fetching and all that it
    seems kind of crazy how some like bands like history end up with
    nothing and I think I'm pretty sure that would be a shortfall that
    that is a shortfall of a purely deterministic system you know like
    ranking just not using LLMS but the reason I'm using you is so that
    you can read through everything right"

Fix
---
A single LLM call reads every corpus paper's abstract (title + year +
deterministic-bucket hint included) and decides per-paper whether it is:

* **history** — foundational method, precursor concept, paradigm-defining
  work for the topic — regardless of publication year.
* **development** — intermediate refinement, scaling, methodological
  adaptation, mid-arc work.
* **sota** — current frontier — most recent meaningful advance, even if
  not the most-recent paper by date.

The LLM outputs ``{"assignments": [{"doi": ..., "bucket": ...,
"rationale": ...}, ...]}``; we map back into ``corpus.metrics.year_buckets``
in :func:`vaultlab.research.lineage.run_lit_arc` so all downstream
consumers (summaries, arc narration, slides) see the LLM's assignments.

This module mirrors the **prepare / render / orchestrate** pattern from
:mod:`vaultlab.research.picker` and :mod:`vaultlab.research.summarize`:

1. :func:`prepare_binning_task` — pure-Python prompt + candidate build,
   no LLM call.
2. :func:`render_binning_from_response` — parse the LLM JSON into a
   :class:`BinningResult`.
3. :func:`assign_buckets_with_llm` — high-level orchestration: prepare,
   call the supplied callback (or the Anthropic SDK), render, fall back
   to the deterministic buckets if no callback / SDK is wired.

The binning module is INDEPENDENT of crosstalk meetings — it's a single
LLM call, not a multi-turn meeting. Keep it simple.

Token-budget constraint
-----------------------
For corpora over ``max_candidates`` (default 200), candidates are picked
deterministically by ``og_score + forward_influence`` so the prompt fits
the model context. The dropped tail keeps its deterministic bucket.

Authentication (SDK fallback)
-----------------------------
The SDK fallback path uses :func:`vaultlab.research.summarize.load_anthropic_api_key`
to discover the key. The Claude-Code-callable path needs no key — the
slash command body runs the LLM step in-session.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from vaultlab.research.corpus import Corpus
    from vaultlab.research.arc_structure import ArcStructure

logger = logging.getLogger(__name__)

__all__ = [
    "BinningCallback",
    "BinningCandidate",
    "BinningResult",
    "BinningTask",
    "MissingBinningCallback",
    "assign_buckets_with_llm",
    "binning_response_schema",
    "build_binning_prompt",
    "prepare_binning_task",
    "render_binning_from_response",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MissingBinningCallback(RuntimeError):
    """Raised when no callback / SDK is supplied and fallback is disabled."""


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


_LEGACY_VALID_BUCKETS: frozenset[str] = frozenset({"history", "development", "sota"})
"""Legacy 3-bucket set, retained for back-compat in ``_coverage`` defaults.

Per-task valid buckets are now derived from the ``ArcStructure`` passed
to :func:`prepare_binning_task`. This constant is only used as a
fallback when no task is in scope.
"""


@dataclass(frozen=True)
class BinningCandidate:
    """One row of the binning candidate pool fed to the LLM.

    Attributes:
        doi: Lower-cased DOI.
        title: Paper title (may be empty for sparse-metadata refs).
        year: Publication year (0 when unknown).
        abstract: Abstract text. Falls back to ``"[no abstract]"`` when
            the in-memory ``Paper.abstract`` field is empty.
        og_score: Citation-graph OG score (fraction of corpus papers
            citing this DOI).
        forward_influence: In-degree on the seed-x-seed subgraph.
        deterministic_bucket: The bucket :func:`graph_metrics.compute_metrics`
            already produced — passed as a hint so the LLM can confirm or
            override it. Also used as the safe fallback when the LLM
            assignment is missing or invalid.
    """

    doi: str
    title: str
    year: int
    abstract: str
    og_score: float
    forward_influence: int
    deterministic_bucket: str


@dataclass(frozen=True)
class BinningTask:
    """A prepared binning task ready for a Claude Code session to execute.

    No LLM is called when this object is built. The slash command body
    inside Claude Code (or any caller wiring a custom callback) inspects
    :attr:`candidates` + :attr:`prompt`, classifies each candidate per
    the system-prompt criteria, and returns JSON matching
    :attr:`response_schema`.

    Attributes:
        topic: The user-supplied topic (raw, not slugified).
        candidates: Papers to be classified. Capped at ``max_candidates``
            via ``og_score + forward_influence`` ranking.
        system: The system-message guard rails.
        prompt: The full user-message prompt the LLM should respond to.
        response_schema: JSON schema describing the expected response.
    """

    topic: str
    candidates: list[BinningCandidate]
    system: str
    prompt: str
    response_schema: dict[str, Any] = field(default_factory=dict)
    valid_section_ids: tuple[str, ...] = ("history", "development", "sota")
    """The set of valid section IDs for this binning run, derived from the
    :class:`~vaultlab.research.arc_structure.ArcStructure` passed to
    :func:`prepare_binning_task`. Default tuple matches the legacy 3-bucket
    SHORT structure for back-compat."""


@dataclass
class BinningResult:
    """Maps DOI -> bucket assignment with rationale.

    Attributes:
        bucket_by_doi: ``doi -> {"history", "development", "sota"}``.
            Always covers every DOI in the original corpus (LLM picks
            land here; missing / invalid LLM picks fall back to the
            deterministic bucket).
        rationale_by_doi: ``doi -> short rationale string``. Empty for
            DOIs that fell back to the deterministic bucket.
        coverage_summary: ``{"history": n, "development": n, "sota": n,
            "unknown": n}`` — the count per bucket after merging.
    """

    bucket_by_doi: dict[str, str] = field(default_factory=dict)
    rationale_by_doi: dict[str, str] = field(default_factory=dict)
    coverage_summary: dict[str, int] = field(default_factory=dict)


# Type alias for the Claude-Code-side binning callback.
BinningCallback = Callable[["BinningTask"], dict[str, Any]]


# ---------------------------------------------------------------------------
# Prompt + schema
# ---------------------------------------------------------------------------


_BINNING_SYSTEM_PROMPT = (
    "You are a literature-lineage classifier. For each candidate paper, "
    "decide whether it is HISTORY (foundational method, precursor concept, "
    "or paradigm-defining work for the given topic — regardless of "
    "publication year), DEVELOPMENT (intermediate refinement, scaling, "
    "methodological adaptation, mid-arc work), or SOTA (current frontier "
    "— the most recent meaningful advance for the topic, even if not the "
    "most-recent paper by date). Read each abstract carefully before "
    "deciding. Year is a HINT, not a rule: a 2018 paper introducing "
    "CODEX is HISTORY for spatial transcriptomics; a 2024 incremental "
    "application is DEVELOPMENT, not SOTA. Aim for non-empty bins where "
    "the corpus reasonably supports it — if a clearly foundational method "
    "is present, that goes in HISTORY. Output ONLY a JSON object matching "
    "the schema in the user message — no prose preamble, no markdown "
    "fencing."
)


def binning_response_schema(
    valid_section_ids: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Return the JSON schema for the binning response.

    The LLM returns a list of ``{doi, bucket, rationale}`` items, one per
    candidate (papers it cannot classify can be omitted — the orchestrator
    falls back to the deterministic bucket for missing DOIs).

    Args:
        valid_section_ids: Allowed values for the ``bucket`` field.
            ``None`` (default) uses the legacy 3-bucket set
            ``("history", "development", "sota")`` for back-compat.
            Pass an :class:`~vaultlab.research.arc_structure.ArcStructure`'s
            ``section_ids`` for variable-length arcs.
    """
    if valid_section_ids is None:
        valid_section_ids = sorted(_LEGACY_VALID_BUCKETS)
    valid_list = sorted(set(valid_section_ids))
    return {
        "type": "object",
        "required": ["assignments"],
        "properties": {
            "assignments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["doi", "bucket"],
                    "properties": {
                        "doi": {
                            "type": "string",
                            "description": "DOI of the candidate paper.",
                        },
                        "bucket": {
                            "type": "string",
                            "enum": valid_list,
                            "description": (
                                "Section ID — one of: "
                                + ", ".join(repr(b) for b in valid_list)
                            ),
                        },
                        "rationale": {
                            "type": "string",
                            "description": (
                                "Short justification (1-2 sentences) "
                                "grounded in the abstract."
                            ),
                        },
                    },
                },
            },
        },
    }


def _truncate_abstract(text: str, *, max_chars: int = 500) -> str:
    """Trim an abstract for prompt budget without breaking mid-word.

    The binning prompt embeds N abstracts; keeping each at ~500 chars
    means ~200 candidates fit comfortably under the model context limit.
    """
    if not text:
        return "[no abstract]"
    if len(text) <= max_chars:
        return text.strip()
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut.strip() + " …"


def build_binning_prompt(
    *,
    topic: str,
    candidates: list[BinningCandidate],
    arc_structure: "ArcStructure | None" = None,
) -> str:
    """Build the user-message prompt for the binning LLM.

    The prompt embeds the topic, the per-section criteria from the arc
    structure, and the candidate list with abstracts + deterministic
    bucket hints. The LLM is asked to decide *per topic* — the same paper
    can be SOTA in one lineage and a foundational paper in another.

    Args:
        topic: User-supplied topic.
        candidates: Papers to classify.
        arc_structure: Section taxonomy. ``None`` (default) uses the
            legacy SHORT structure (history/development/sota).
    """
    # Lazy import to avoid circulars at module load.
    if arc_structure is None:
        from vaultlab.research.arc_structure import SHORT as _SHORT
        arc_structure = _SHORT

    section_ids_str = " / ".join(s.id.upper() for s in arc_structure.sections)
    lines: list[str] = [
        f"TOPIC: {topic}",
        "",
        f"Classify each of the {len(candidates)} candidates below into "
        f"one of these sections of the lineage arc: {section_ids_str}.",
        "",
        f"ARC STRUCTURE: {arc_structure.name} "
        f"({len(arc_structure.sections)} sections; total target "
        f"paragraphs={arc_structure.total_target_paragraphs}).",
        "",
        "SECTION DEFINITIONS:",
    ]
    for section in arc_structure.sections:
        lines.append(f"- **{section.id}** ({section.title}): {section.criterion}")
    lines.extend(
        [
            "",
            "DETERMINISTIC HINT:",
            "- Each candidate carries a `deterministic_bucket` field showing "
            "what year-quartile bucketing produced. Use it as a HINT, not a "
            "rule — override it when the abstract clearly says otherwise.",
            "- Aim for non-empty bins where the corpus reasonably supports "
            "it. If the deterministic system left a section empty but a "
            "fitting paper is present, move that paper there.",
            "",
            f"CANDIDATES ({len(candidates)} total):",
            "",
        ]
    )
    for i, c in enumerate(candidates, 1):
        header = f"[{i}] {c.title or '(untitled)'}"
        year_str = str(c.year) if c.year else "n.d."
        lines.append(header)
        lines.append(
            f"    DOI: {c.doi}  | year={year_str}  "
            f"og_score={c.og_score:.2f}  "
            f"forward_influence={c.forward_influence}  "
            f"deterministic_bucket={c.deterministic_bucket}"
        )
        lines.append(f"    Abstract: {_truncate_abstract(c.abstract)}")
        lines.append("")

    valid_section_ids_str = ", ".join(
        repr(s.id) for s in arc_structure.sections
    )
    example_id_a = arc_structure.sections[0].id
    example_id_b = (
        arc_structure.sections[1].id
        if len(arc_structure.sections) > 1
        else example_id_a
    )
    lines.extend(
        [
            "OUTPUT FORMAT:",
            "Return ONLY a JSON object:",
            "",
            "{",
            '  "assignments": [',
            (
                f'    {{"doi": "<doi>", "bucket": "{example_id_a}", '
                '"rationale": "<1-2 sentences grounded in the abstract>"},'
            ),
            (
                f'    {{"doi": "<doi>", "bucket": "{example_id_b}", '
                '"rationale": "..."},'
            ),
            "    ...",
            "  ]",
            "}",
            "",
            "Use the candidate DOIs EXACTLY as listed above. Do NOT "
            f"invent DOIs. Use ONLY one of: {valid_section_ids_str} "
            "as bucket values.",
        ]
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Candidate selection (top-N by deterministic citation score)
# ---------------------------------------------------------------------------


def _build_candidates(
    corpus: "Corpus",
    *,
    max_candidates: int,
) -> list[BinningCandidate]:
    """Build the candidate list, capped at ``max_candidates``.

    For corpora larger than ``max_candidates``, papers are ranked by
    ``og_score + forward_influence`` (the same coarse pool the picker
    uses) and the tail is dropped — those papers keep their deterministic
    bucket because the LLM never saw them.

    Empty corpus -> empty candidate list (the caller short-circuits).
    """
    metrics = corpus.metrics
    dois = list(corpus.papers.keys())
    if not dois:
        return []

    if metrics is None:
        ranked_dois = dois
    else:
        def _coarse_score(doi: str) -> float:
            return float(metrics.og_score.get(doi, 0.0)) + float(
                metrics.forward_influence.get(doi, 0)
            )

        ranked_dois = sorted(dois, key=_coarse_score, reverse=True)

    ranked_dois = ranked_dois[: max(0, int(max_candidates))]

    out: list[BinningCandidate] = []
    for doi in ranked_dois:
        paper = corpus.papers.get(doi)
        abstract = ""
        if paper is not None:
            abstract = (paper.abstract or "").strip()
        if not abstract:
            abstract = "[no abstract]"
        og = float(metrics.og_score.get(doi, 0.0)) if metrics else 0.0
        fwd = int(metrics.forward_influence.get(doi, 0)) if metrics else 0
        det_bucket = (
            metrics.year_buckets.get(doi, "unknown") if metrics else "unknown"
        )
        out.append(
            BinningCandidate(
                doi=doi,
                title=(paper.title if paper else "") or "",
                year=int(paper.year) if paper and paper.year else 0,
                abstract=abstract,
                og_score=og,
                forward_influence=fwd,
                deterministic_bucket=det_bucket,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Public API: prepare / render
# ---------------------------------------------------------------------------


def prepare_binning_task(
    corpus: "Corpus",
    topic: str,
    *,
    max_candidates: int = 200,
    arc_structure: "ArcStructure | None" = None,
) -> BinningTask:
    """Prepare a binning task. Does NOT call any LLM.

    Returns the structured task with prompt + system message + expected
    response schema. The caller (Claude Code session, or any custom
    orchestrator) is responsible for running the LLM step and feeding
    the JSON response into :func:`render_binning_from_response`.

    Args:
        corpus: A built :class:`Corpus`. ``compute_metrics`` should have
            run first so the candidates carry og_score / forward_influence /
            deterministic_bucket hints.
        topic: User-supplied topic (raw, not slugified).
        max_candidates: Token-budget cap. Corpora larger than this get
            ranked by ``og_score + forward_influence`` and the tail keeps
            its deterministic bucket. Default 200.
        arc_structure: Section taxonomy for the binning. ``None`` (default)
            uses the legacy SHORT structure (history / development / sota)
            for back-compat. Pass a longer structure (e.g. STANDARD or
            REVIEW_PAPER) to bin papers into more sections.

    Returns:
        A :class:`BinningTask` ready for the LLM step.
    """
    if arc_structure is None:
        from vaultlab.research.arc_structure import SHORT
        arc_structure = SHORT
    candidates = _build_candidates(corpus, max_candidates=max_candidates)
    prompt = build_binning_prompt(
        topic=topic, candidates=candidates, arc_structure=arc_structure
    )
    section_ids = tuple(s.id for s in arc_structure.sections)
    return BinningTask(
        topic=topic,
        candidates=candidates,
        system=_BINNING_SYSTEM_PROMPT,
        prompt=prompt,
        response_schema=binning_response_schema(section_ids),
        valid_section_ids=section_ids,
    )


def _coverage(
    buckets: dict[str, str],
    valid_section_ids: tuple[str, ...] | None = None,
) -> dict[str, int]:
    """Count occurrences of each bucket across the merged result.

    Args:
        buckets: ``doi -> bucket`` mapping.
        valid_section_ids: Sections to pre-seed in the output (so even
            empty sections show as ``0``). Defaults to the legacy
            history/development/sota set when None.
    """
    if valid_section_ids is None:
        valid_section_ids = tuple(sorted(_LEGACY_VALID_BUCKETS))
    out: dict[str, int] = {sid: 0 for sid in valid_section_ids}
    out["unknown"] = 0
    for b in buckets.values():
        if b in out:
            out[b] += 1
        else:
            out.setdefault(b, 0)
            out[b] += 1
    return out


def render_binning_from_response(
    response_json: dict[str, Any] | None,
    task: BinningTask,
) -> BinningResult:
    """Take the LLM JSON response and produce a populated BinningResult.

    Validation rules:

    * Each LLM assignment must reference a DOI in ``task.candidates`` —
      DOIs the LLM invented are silently dropped (the deterministic
      bucket survives).
    * Each LLM assignment must have ``bucket`` in
      ``{"history", "development", "sota"}`` — anything else falls back
      to the deterministic bucket.
    * Every candidate DOI ends up in ``bucket_by_doi`` exactly once
      (LLM pick wins; missing/invalid -> deterministic).

    Args:
        response_json: Parsed JSON dict matching :func:`binning_response_schema`.
            ``None`` or empty -> all DOIs fall back to deterministic.
        task: The :class:`BinningTask` produced by
            :func:`prepare_binning_task`.

    Returns:
        Populated :class:`BinningResult`.
    """
    valid_dois = {c.doi: c for c in task.candidates}
    bucket_by_doi: dict[str, str] = {}
    rationale_by_doi: dict[str, str] = {}

    raw_assignments: list[Any] = []
    if isinstance(response_json, dict):
        maybe = response_json.get("assignments")
        if isinstance(maybe, list):
            raw_assignments = maybe

    for item in raw_assignments:
        if not isinstance(item, dict):
            continue
        raw_doi = item.get("doi")
        if not isinstance(raw_doi, str):
            continue
        doi = raw_doi.strip().lower()
        if not doi or doi not in valid_dois:
            logger.debug("binning dropped unknown DOI: %r", raw_doi)
            continue
        if doi in bucket_by_doi:
            # First assignment wins — drop duplicates.
            continue
        raw_bucket = item.get("bucket")
        if not isinstance(raw_bucket, str):
            continue
        bucket = raw_bucket.strip().lower()
        # Validate against the task's per-run section IDs (variable-length
        # arc support). Falls back to the legacy 3-bucket set when the
        # task was built before the field existed.
        valid_section_set = (
            set(task.valid_section_ids)
            if task.valid_section_ids
            else _LEGACY_VALID_BUCKETS
        )
        if bucket not in valid_section_set:
            logger.debug("binning dropped invalid bucket %r for %s", raw_bucket, doi)
            continue
        bucket_by_doi[doi] = bucket
        rationale = item.get("rationale", "")
        if isinstance(rationale, str):
            rationale_by_doi[doi] = rationale.strip()

    # Fill the gap with deterministic buckets for any DOI the LLM didn't
    # cover (or covered with an invalid value). This is the safety net
    # that closes Bobby's "history bin empty" complaint without ever
    # producing an UNCLASSIFIED paper.
    for doi, candidate in valid_dois.items():
        if doi not in bucket_by_doi:
            bucket_by_doi[doi] = candidate.deterministic_bucket

    coverage = _coverage(bucket_by_doi, valid_section_ids=task.valid_section_ids)
    return BinningResult(
        bucket_by_doi=bucket_by_doi,
        rationale_by_doi=rationale_by_doi,
        coverage_summary=coverage,
    )


def _deterministic_only_result(corpus: "Corpus") -> BinningResult:
    """Build a BinningResult that just mirrors corpus.metrics.year_buckets.

    Used as the fallback when no callback / SDK is wired and fallback
    is enabled. Every paper keeps its existing year-quartile bucket.
    """
    metrics = corpus.metrics
    bucket_by_doi: dict[str, str] = {}
    if metrics is not None:
        for doi in corpus.papers:
            bucket_by_doi[doi] = metrics.year_buckets.get(doi, "unknown")
    else:
        for doi in corpus.papers:
            bucket_by_doi[doi] = "unknown"
    return BinningResult(
        bucket_by_doi=bucket_by_doi,
        rationale_by_doi={},
        coverage_summary=_coverage(bucket_by_doi),
    )


# ---------------------------------------------------------------------------
# SDK fallback (optional)
# ---------------------------------------------------------------------------


def _call_anthropic_for_binning(
    *,
    task: BinningTask,
    api_key: str,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """Call Anthropic SDK with the prepared binning task.

    Returns the parsed JSON response. Raises whatever the SDK raises on
    auth / rate-limit / network failures — callers who want graceful
    degradation should wrap in try/except.
    """
    import anthropic  # local import keeps tests offline

    # Reuse the JSON-extractor shipped with summarize.py so we tolerate
    # markdown-fenced responses identically.
    from vaultlab.research.summarize import _extract_json

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=task.system,
        messages=[{"role": "user", "content": task.prompt}],
    )
    text_chunks: list[str] = []
    for block in response.content:
        if getattr(block, "type", "") == "text":
            text_chunks.append(block.text)
    full_text = "\n".join(text_chunks).strip()
    return _extract_json(full_text)


# ---------------------------------------------------------------------------
# Public API: orchestration
# ---------------------------------------------------------------------------


def assign_buckets_with_llm(
    corpus: "Corpus",
    topic: str,
    *,
    binner_callback: BinningCallback | None = None,
    sdk_client: Any | None = None,
    max_candidates: int = 200,
    fallback_to_deterministic: bool = True,
    model: str = "claude-sonnet-4-6",
    arc_structure: "ArcStructure | None" = None,
) -> BinningResult:
    """Assign every corpus paper to a lineage bucket via LLM-driven binning.

    Two execution modes:

    * **Callback given** — :func:`prepare_binning_task` builds the prompt,
      ``binner_callback`` runs the LLM step and returns JSON, and
      :func:`render_binning_from_response` produces the final result.
      Used by the ``/lit-arc`` slash command body inside Claude Code,
      where the active session IS the LLM (no Anthropic API key needed).
    * **SDK mode** — when ``sdk_client`` is given (or
      ``binner_callback`` is None and an Anthropic API key is configured
      via :func:`vaultlab.research.summarize.load_anthropic_api_key`),
      this function calls Anthropic directly. ``sdk_client=True`` opts in
      to the SDK lookup; passing ``False`` (or leaving it None) keeps the
      function offline.

    When neither mode is wired and ``fallback_to_deterministic=True``
    (default), the function returns a :class:`BinningResult` mirroring
    ``corpus.metrics.year_buckets``. With ``fallback_to_deterministic=False``,
    it raises :class:`MissingBinningCallback`.

    Args:
        corpus: Built :class:`Corpus` with ``compute_metrics`` already run.
            Empty corpus -> empty result.
        topic: User-supplied topic (raw, not slugified).
        binner_callback: Optional :data:`BinningCallback` that consumes a
            :class:`BinningTask` and returns a JSON dict matching
            :func:`binning_response_schema`. Preferred path inside Claude
            Code sessions.
        sdk_client: When truthy and ``binner_callback`` is None, attempt
            an Anthropic SDK call. Pass ``True`` to use the auto-resolved
            key; pass an explicit ``anthropic.Anthropic`` instance for
            advanced use; pass ``None`` (default) to skip the SDK path.
        max_candidates: Token-budget cap forwarded to
            :func:`prepare_binning_task`.
        fallback_to_deterministic: If True (default), missing callbacks
            and SDK failures fall through to the deterministic buckets.
            Set False to force a hard error if the LLM step can't run.
        model: Anthropic model id used in SDK mode.

    Returns:
        A :class:`BinningResult` covering every DOI in the corpus.

    Raises:
        MissingBinningCallback: When no LLM path is wired and
            ``fallback_to_deterministic=False``.
    """
    # Empty corpus short-circuit (avoids LLM call for nothing).
    if not corpus.papers:
        return BinningResult(
            bucket_by_doi={},
            rationale_by_doi={},
            coverage_summary=_coverage({}),
        )

    if binner_callback is None and not sdk_client:
        if fallback_to_deterministic:
            return _deterministic_only_result(corpus)
        raise MissingBinningCallback(
            "assign_buckets_with_llm requires a binner_callback (or "
            "sdk_client=True) when fallback_to_deterministic=False"
        )

    task = prepare_binning_task(
        corpus,
        topic,
        max_candidates=max_candidates,
        arc_structure=arc_structure,
    )
    if not task.candidates:
        # No candidates -> nothing to ask the LLM. Fall back gracefully.
        return _deterministic_only_result(corpus)

    response: dict[str, Any] | None = None

    if binner_callback is not None:
        try:
            raw = binner_callback(task)
        except Exception as exc:
            logger.warning(
                "binner_callback raised: %s; falling back to deterministic",
                exc,
            )
            if not fallback_to_deterministic:
                raise
            return _deterministic_only_result(corpus)
        if isinstance(raw, dict):
            response = raw
        else:
            logger.warning(
                "binner_callback returned non-dict (%s); falling back",
                type(raw).__name__,
            )
            if not fallback_to_deterministic:
                raise MissingBinningCallback(
                    "binner_callback returned non-dict; cannot bin"
                )
            return _deterministic_only_result(corpus)
    else:
        # SDK mode.
        try:
            from vaultlab.research.summarize import load_anthropic_api_key

            api_key = (
                load_anthropic_api_key()
                if sdk_client is True
                else getattr(sdk_client, "api_key", None) or load_anthropic_api_key()
            )
            response = _call_anthropic_for_binning(
                task=task, api_key=api_key, model=model
            )
        except Exception as exc:
            logger.warning(
                "SDK binning failed: %s; falling back to deterministic", exc
            )
            if not fallback_to_deterministic:
                raise
            return _deterministic_only_result(corpus)

    return render_binning_from_response(response, task)
