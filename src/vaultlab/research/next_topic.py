"""Propose the next-best lineage topic from prior decisions log.

Pattern lifted from AI-Scientist's ``generate_ideas.generate_next_idea``
(``generate_ideas.py:178-279``): when a researcher has been using the
system for a while, the system itself accumulates a record of what's
been done — past topics, open questions, citation gaps — and can
propose what to work on next instead of asking the user to invent a
topic each time.

For vaultlab, the inputs are:

* The project's ``Wiki/Projects/<slug>/decisions-log.md`` — every
  ``/lit-arc`` and ``/build-deck`` run got an entry there with the
  topic + outcome stats
* The arcs themselves at ``Wiki/Concepts/<topic-slug>-lineage-<date>.md``
  — each one has wikilinks identifying the corpus, and (for STANDARD
  or REVIEW_PAPER scopes) explicit "Open questions" /
  "Limitations & future directions" sections
* The papers manifest ``Wiki/Projects/<slug>/papers.md`` — surfaces
  what's already in the corpus (and by extension what topical gaps
  the existing corpus has)

The output is a ranked list of 3-5 candidate next-best topics, each
with rationale grounded in the existing KB state. The user picks one
and runs ``/lit-arc <chosen-topic>``.

Pipeline shape (mirrors picker / binner / claim_verification):

1. :func:`read_prior_topics` / :func:`read_open_questions` — pure
   filesystem reads, no LLM.
2. :func:`prepare_next_topic_task` — builds prompt + schema.
3. :func:`render_topics_from_response` — parses LLM response into
   structured candidates.
4. :func:`propose_next_topics` — high-level helper: prepare → call
   callback → render. Returns empty proposal list when no callback.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


__all__ = [
    "NextTopicCallback",
    "NextTopicProposal",
    "NextTopicTask",
    "PriorTopicRecord",
    "next_topic_response_schema",
    "prepare_next_topic_task",
    "propose_next_topics",
    "read_open_questions",
    "read_prior_topics",
    "render_topics_from_response",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PriorTopicRecord:
    """One prior ``/lit-arc`` run extracted from a decisions-log entry.

    Attributes:
        timestamp: ISO timestamp from the log header (e.g.
            ``"2026-04-30T19:02:59"``).
        topic: The topic string (raw, not slugified).
        corpus_size: Number of papers in the corpus, when parseable;
            0 when missing.
        tier_a_picks: Number of Tier-A picks; 0 when missing.
        run_id: Optional run-ID for cross-referencing the run dir.
    """

    timestamp: str
    topic: str
    corpus_size: int = 0
    tier_a_picks: int = 0
    run_id: str = ""


@dataclass(frozen=True)
class NextTopicTask:
    """A prepared next-topic-proposal task ready for an LLM callback.

    Attributes:
        kb_root: The KB root path (for context).
        project_slug: Optional project slug being queried.
        prior_topics: List of :class:`PriorTopicRecord` from past runs.
        open_questions: Free-text snippets pulled from arc bodies'
            "Open questions" / "Limitations & future directions" sections.
        target_n: How many candidate topics to propose (default 5).
        system: System-message guard rails.
        prompt: User-message prompt the LLM should respond to.
        response_schema: JSON schema describing the expected response.
    """

    kb_root: Path
    project_slug: str
    prior_topics: list[PriorTopicRecord]
    open_questions: list[str]
    target_n: int
    system: str
    prompt: str
    response_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NextTopicProposal:
    """One proposed next-best topic.

    Attributes:
        topic: The proposed topic string (passable directly to ``/lit-arc``).
        rationale: 1-3 sentences explaining why this topic is a good
            next-best step given prior runs and open questions.
        builds_on: List of prior topic strings (or wikilinks) this
            proposal would build on.
        addresses_question: When the proposal directly answers an
            open-question entry, the matching question text. Empty
            when the proposal opens new ground rather than closing a gap.
        priority_rank: 1-indexed rank from the LLM (1 = strongest pick).
    """

    topic: str
    rationale: str = ""
    builds_on: list[str] = field(default_factory=list)
    addresses_question: str = ""
    priority_rank: int = 0


NextTopicCallback = Callable[[NextTopicTask], dict[str, Any]]


# ---------------------------------------------------------------------------
# Filesystem reads — no LLM
# ---------------------------------------------------------------------------


_LIT_ARC_HEADER_RE = re.compile(
    r"^##\s*(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\s*[—-]\s*lit-arc run\s*$",
    flags=re.MULTILINE,
)


def _decisions_log_path(kb_root: Path, project_slug: str) -> Path:
    return Path(kb_root) / "Wiki" / "Projects" / project_slug / "decisions-log.md"


def read_prior_topics(
    kb_root: Path,
    project_slug: str,
) -> list[PriorTopicRecord]:
    """Parse the project's decisions-log for prior ``/lit-arc`` runs.

    Returns one :class:`PriorTopicRecord` per ``## YYYY-MM-DDTHH:MM:SS — lit-arc run``
    block found, oldest first. Missing or malformed log → empty list.
    """
    path = _decisions_log_path(kb_root, project_slug)
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    out: list[PriorTopicRecord] = []
    # Split the file into sections at the lit-arc-run header
    indices: list[tuple[int, str]] = []
    for m in _LIT_ARC_HEADER_RE.finditer(text):
        indices.append((m.end(), m.group("ts")))

    for i, (start_idx, ts) in enumerate(indices):
        end_idx = indices[i + 1][0] if i + 1 < len(indices) else len(text)
        block = text[start_idx:end_idx]

        topic = _extract_field(block, "Topic")
        corpus_size = _extract_int(block, "Corpus size")
        tier_a_picks = _extract_int(block, "Tier-A picks")
        run_id = _extract_field(block, "Run ID")
        if not topic:
            continue
        out.append(
            PriorTopicRecord(
                timestamp=ts,
                topic=topic,
                corpus_size=corpus_size,
                tier_a_picks=tier_a_picks,
                run_id=run_id,
            )
        )
    return out


_FIELD_RE_TEMPLATE = r"^-\s+\*\*{label}:\*\*\s+(?P<v>.+?)$"


def _extract_field(block: str, label: str) -> str:
    """Pull a ``- **<label>:** value`` line value out of a block."""
    pat = re.compile(_FIELD_RE_TEMPLATE.format(label=re.escape(label)), re.MULTILINE)
    m = pat.search(block)
    return m.group("v").strip() if m else ""


def _extract_int(block: str, label: str) -> int:
    """Extract a leading integer from a ``- **<label>:** N (...)`` line."""
    raw = _extract_field(block, label)
    if not raw:
        return 0
    m = re.match(r"^\s*(\d+)", raw)
    return int(m.group(1)) if m else 0


_OPEN_QUESTIONS_HEADERS: tuple[str, ...] = (
    "Open questions",
    "Limitations & future directions",
    "Limitations and future directions",
    "Future directions",
)


def read_open_questions(
    kb_root: Path,
    project_slug: str,
) -> list[str]:
    """Scan project arcs for 'Open questions' / 'Future directions' content.

    Walks ``Wiki/Concepts/<topic-slug>-lineage-*.md`` files associated
    with the project (via the project's papers.md or lineage links)
    and returns the body text from any section whose heading matches one
    of :data:`_OPEN_QUESTIONS_HEADERS`. Each returned string is one
    section's content; multiple per arc OK.

    Returns empty list when no project arcs found, or no arcs have
    open-question sections (default SHORT structure has none).
    """
    concepts_dir = Path(kb_root) / "Wiki" / "Concepts"
    if not concepts_dir.exists():
        return []
    out: list[str] = []
    # Match any *lineage*.md as a candidate; tighter scoping by project
    # slug would require parsing the arc frontmatter, which is fine
    # for v0.1 to skip — we just collect from every lineage arc.
    for arc_path in concepts_dir.glob("*lineage*.md"):
        try:
            body = arc_path.read_text(encoding="utf-8")
        except OSError:
            continue
        for heading in _OPEN_QUESTIONS_HEADERS:
            section = _extract_section(body, heading)
            if section:
                out.append(section.strip())
    return out


def _extract_section(text: str, heading: str) -> str:
    """Return the body of a ``## <heading>`` (or ``### <heading>``) section.

    The body runs from after the heading line to the next heading or
    end-of-file. Returns empty string when the section isn't present.
    """
    # Allow optional ## / ### / #### prefix
    pat = re.compile(
        rf"^#{{2,4}}\s+{re.escape(heading)}\s*$\n(.*?)(?=^#{{1,4}}\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pat.search(text)
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------------------
# Prompt + schema
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = (
    "You are a research direction advisor. Given a researcher's prior "
    "lineage-arc runs and the open questions / limitations those arcs "
    "surfaced, propose the next-best topics to work on. Each proposal "
    "must build on what's already in the KB — either closing an open "
    "question, extending a prior arc into adjacent territory, or "
    "synthesizing across multiple prior topics into a higher-level "
    "lineage. Do NOT propose topics that just rehash a prior run with "
    "minor reframing. Output ONLY a JSON object matching the schema in "
    "the user message — no prose preamble, no markdown fencing."
)


def next_topic_response_schema(target_n: int) -> dict[str, Any]:
    """JSON schema for the next-topic proposal response."""
    return {
        "type": "object",
        "required": ["proposals"],
        "properties": {
            "proposals": {
                "type": "array",
                "minItems": 1,
                "maxItems": max(1, int(target_n)),
                "items": {
                    "type": "object",
                    "required": ["topic", "rationale"],
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": (
                                "Proposed topic — must be passable to /lit-arc as a topic argument."
                            ),
                        },
                        "rationale": {
                            "type": "string",
                            "description": (
                                "1-3 sentences grounded in the prior topics or open questions."
                            ),
                        },
                        "builds_on": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Prior topic strings this proposal "
                                "extends. May be empty if proposal "
                                "opens new ground."
                            ),
                        },
                        "addresses_question": {
                            "type": "string",
                            "description": (
                                "When the proposal directly answers an "
                                "open question, the matching question "
                                "text. Empty otherwise."
                            ),
                        },
                    },
                },
            }
        },
    }


def _build_next_topic_prompt(
    *,
    project_slug: str,
    prior_topics: list[PriorTopicRecord],
    open_questions: list[str],
    target_n: int,
) -> str:
    lines: list[str] = [
        f"PROJECT: {project_slug or '(unspecified)'}",
        "",
        f"Propose up to {target_n} next-best lineage-arc topics to run.",
        "",
    ]
    if prior_topics:
        lines.append("PRIOR LIT-ARC RUNS (oldest first):")
        for r in prior_topics:
            stats = ""
            if r.corpus_size:
                stats = f" [corpus={r.corpus_size}, tier-A={r.tier_a_picks}]"
            lines.append(f"  {r.timestamp} — {r.topic}{stats}")
        lines.append("")
    else:
        lines.append("PRIOR RUNS: (none — this would be the project's first lit-arc)")
        lines.append("")

    if open_questions:
        lines.append("OPEN QUESTIONS / LIMITATIONS surfaced by prior arcs:")
        for q in open_questions:
            # Cap each open-question block to keep prompt size sane
            snippet = q if len(q) <= 600 else q[:600].rstrip() + " […]"
            lines.append("  ---")
            for ln in snippet.splitlines():
                lines.append(f"  {ln}")
        lines.append("")
    else:
        lines.append("OPEN QUESTIONS: (none recorded — propose based on prior topics alone)")
        lines.append("")

    lines.extend(
        [
            "OUTPUT FORMAT:",
            "Return ONLY a JSON object:",
            "",
            "{",
            '  "proposals": [',
            (
                '    {"topic": "<topic string>", "rationale": "<grounded reason>",'
                ' "builds_on": ["<prior topic>", ...], "addresses_question": "<text or empty>"},'
            ),
            "    ...",
            "  ]",
            "}",
            "",
            "Rank proposals by priority — strongest pick first. Do NOT "
            "propose duplicates of prior topics or trivial reframings.",
        ]
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API: prepare / render / orchestrate
# ---------------------------------------------------------------------------


def prepare_next_topic_task(
    *,
    kb_root: Path,
    project_slug: str,
    target_n: int = 5,
) -> NextTopicTask:
    """Build a :class:`NextTopicTask`. Does NOT call any LLM."""
    prior_topics = read_prior_topics(kb_root, project_slug)
    open_questions = read_open_questions(kb_root, project_slug)
    prompt = _build_next_topic_prompt(
        project_slug=project_slug,
        prior_topics=prior_topics,
        open_questions=open_questions,
        target_n=target_n,
    )
    return NextTopicTask(
        kb_root=Path(kb_root),
        project_slug=project_slug,
        prior_topics=prior_topics,
        open_questions=open_questions,
        target_n=int(target_n),
        system=_SYSTEM_PROMPT,
        prompt=prompt,
        response_schema=next_topic_response_schema(target_n),
    )


def render_topics_from_response(
    response_json: dict[str, Any] | None,
    task: NextTopicTask,
) -> list[NextTopicProposal]:
    """Parse the callback's response into a list of proposals.

    Validation: each proposal must have non-empty ``topic`` and
    non-empty ``rationale``. Malformed or duplicate topics are dropped
    silently (no crash).
    """
    if not isinstance(response_json, dict):
        return []
    raw_list = response_json.get("proposals")
    if not isinstance(raw_list, list):
        return []

    seen_topics: set[str] = set()
    out: list[NextTopicProposal] = []
    for i, item in enumerate(raw_list, start=1):
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic") or "").strip()
        rationale = str(item.get("rationale") or "").strip()
        if not topic or not rationale:
            continue
        topic_key = topic.lower()
        if topic_key in seen_topics:
            continue
        seen_topics.add(topic_key)
        builds_on_raw = item.get("builds_on") or []
        builds_on = (
            [str(x).strip() for x in builds_on_raw if str(x).strip()]
            if isinstance(builds_on_raw, list)
            else []
        )
        addresses = str(item.get("addresses_question") or "").strip()
        out.append(
            NextTopicProposal(
                topic=topic,
                rationale=rationale,
                builds_on=builds_on,
                addresses_question=addresses,
                priority_rank=i,
            )
        )
        if len(out) >= max(1, task.target_n):
            break
    return out


def propose_next_topics(
    *,
    kb_root: Path,
    project_slug: str,
    target_n: int = 5,
    callback: NextTopicCallback | None = None,
) -> list[NextTopicProposal]:
    """High-level helper: prepare → call callback → render.

    When no callback is given, returns an empty list (no proposals).
    Callers can use this to print "no callback wired — pass a verifier"
    rather than crashing.
    """
    task = prepare_next_topic_task(
        kb_root=kb_root,
        project_slug=project_slug,
        target_n=target_n,
    )
    if callback is None:
        return []
    try:
        response = callback(task)
    except Exception as exc:
        logger.warning("next-topic callback raised: %s", exc)
        return []
    return render_topics_from_response(response, task)
