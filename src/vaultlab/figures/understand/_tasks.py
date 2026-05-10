"""Task dataclasses + prepare/render helpers for figure-understanding callbacks.

Mirrors the prepare-task / render-from-response pattern used in
:mod:`vaultlab.research.lineage` and :mod:`vaultlab.research.picker`:

1. The orchestrator (:func:`vaultlab.figures.understand.understand_figure`)
   builds a task object containing the prompt + system message + JSON
   response schema.
2. The callsite (a slash command body, an SDK-backed wrapper, or a test
   stub) inspects the task, produces a JSON response, and feeds it back
   through a ``render_*_from_response`` helper.
3. The helper parses the response into the shape the orchestrator expects.

Three roles, one task each:

- :class:`DescribeFigureTask` — Step 1 — read the figure visually and
  describe its discrete elements in natural language.
- :class:`MatchElementsTask` — Step 3 — pair LLM-named elements with the
  programmatic regions returned by Step 2.
- :class:`VerifyAnnotationTask` — Step 4 — read the rendered annotated
  image and accept / retry / give up.

This module imports only stdlib + the local :mod:`models` /
:mod:`color_motif` siblings so it stays cheap to import in pure-test
contexts that don't have the Anthropic SDK installed.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vaultlab.figures.understand.color_motif import Region
from vaultlab.figures.understand.models import VerificationIteration

logger = logging.getLogger(__name__)


__all__ = [
    "DESCRIBE_SYSTEM_PROMPT",
    "MATCH_SYSTEM_PROMPT",
    "VERIFY_SYSTEM_PROMPT",
    "DescribeFigureTask",
    "MatchElementsTask",
    "VerifyAnnotationTask",
    "describe_response_schema",
    "match_response_schema",
    "prepare_describe_task",
    "prepare_match_task",
    "prepare_verify_task",
    "render_describe_from_response",
    "render_match_from_response",
    "render_verify_from_response",
    "verify_response_schema",
]


# ---------------------------------------------------------------------------
# System prompts (loaded lazily from roles/figure_reader/prompt.md when
# available, otherwise fall back to the inline default below).
# ---------------------------------------------------------------------------


_INLINE_DESCRIBE_SYSTEM = (
    "You are a Figure Reader for a scientific publication. You are looking at "
    "a single figure from a peer-reviewed paper. Your job is to describe what "
    "is visually in the figure — discrete elements (panels, receptor glyphs, "
    "color-coded regions, arrows, legend swatches, labels) and their spatial "
    "relationships — in plain English. You DO NOT analyze the science; you "
    "describe what a human would point at.\n\n"
    "RULES:\n"
    "- Describe what is actually visible. Do not invent panels or colors that "
    "  are not in the figure.\n"
    "- Be honest: if the figure is unclear, blurred, or its labels are "
    "  illegible, say so. Do not fabricate detail to fill gaps.\n"
    "- Name discrete elements explicitly, e.g. 'a neon-green dimer in panel "
    "  A representing the introduced TCR'. Each named element should be "
    "  recoverable as one bounding box later.\n"
    "- Keep the description grounded in the paper's TL;DR (provided as "
    "  context), but do not paraphrase the TL;DR back at us — describe THIS "
    "  figure.\n\n"
    "Return ONLY a JSON object matching the schema in the user message. No "
    "markdown fencing, no preamble."
)


_INLINE_MATCH_SYSTEM = (
    "You are a Figure Element Matcher. Given a free-text description of a "
    "figure (Step 1 output) and a list of programmatically-extracted pixel "
    "regions (Step 2 output, color-motif bounding boxes), pair each named "
    "element from the description with the region that is most likely to be "
    "that element on the original figure.\n\n"
    "RULES:\n"
    "- Use ONLY the region IDs supplied in the candidate list. Do not invent "
    "  IDs.\n"
    "- A described element with no plausible region match should be omitted "
    "  rather than force-paired with an unrelated region.\n"
    "- Confidence is 0.0–1.0; <0.5 means 'this is a guess', >0.8 means 'I am "
    "  confident'. Be honest.\n"
    "- Keep rationales short (1–2 sentences) but grounded in BOTH the "
    "  description and the region's color/position.\n\n"
    "Return ONLY a JSON object matching the schema in the user message."
)


_INLINE_VERIFY_SYSTEM = (
    "You are a Figure Annotation Verifier. You are given an annotated image "
    "(the original figure with bounding-box overlays + numbered markers) and "
    "the list of element labels that should be on it. Your job is to read the "
    "annotated image and decide whether each marker landed on the right "
    "element.\n\n"
    "RULES:\n"
    "- Look at the actual annotated image — do not trust the labels alone.\n"
    "- If a marker collides with a text label, blocks underlying figure "
    "  content, or sits on the wrong element, list it as an issue.\n"
    "- Be honest: small offsets are acceptable; large mismatches are not.\n"
    "- Decisions:\n"
    "  - ACCEPT: every marker is on or visibly adjacent to its named element.\n"
    "  - RETRY_LOCALIZE: the bounding boxes are wrong — Step 2 should rerun "
    "    with adjusted color motifs.\n"
    "  - RETRY_MATCH: the bounding boxes are right but paired with the wrong "
    "    element name — Step 3 should rerun.\n"
    "  - GIVE_UP: the figure is too unclear to annotate reliably.\n\n"
    "Return ONLY a JSON object matching the schema in the user message."
)


def _load_role_prompt(role_id: str, fallback: str) -> str:
    """Load a role prompt from ``vaultlab/roles/<role_id>/prompt.md``.

    Falls back to ``fallback`` when the loader fails (missing file, missing
    PyYAML dep, etc.) so this module stays importable in lean environments.
    """
    try:
        from vaultlab.roles._loader import load_role  # local import to avoid PyYAML at module load
    except Exception:
        return fallback
    try:
        role = load_role(role_id)
    except Exception:
        return fallback
    text = (role.system_prompt or "").strip()
    return text if text else fallback


# Public, memoized at first access. The sentinel prevents a missing-role
# blow-up at import time; we resolve on first ``__getattr__``-style access
# below. For simplicity, build them eagerly — failures fall back silently.
DESCRIBE_SYSTEM_PROMPT: str = _load_role_prompt("figure_reader", _INLINE_DESCRIBE_SYSTEM)
MATCH_SYSTEM_PROMPT: str = _load_role_prompt("figure_reader", _INLINE_MATCH_SYSTEM)
VERIFY_SYSTEM_PROMPT: str = _load_role_prompt("figure_reader", _INLINE_VERIFY_SYSTEM)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


def describe_response_schema() -> dict[str, Any]:
    """JSON schema for the describe step's response.

    Two top-level keys: ``description`` (the free-text description used
    directly as ``log.step1_description``) and ``elements`` (an explicit
    list of named elements; useful when downstream steps want to enumerate
    them without re-parsing free text).
    """
    return {
        "type": "object",
        "required": ["description", "elements"],
        "properties": {
            "description": {
                "type": "string",
                "description": (
                    "Free-text description of the figure (3–8 sentences). "
                    "Names discrete elements that should later become "
                    "annotation targets."
                ),
            },
            "elements": {
                "type": "array",
                "description": (
                    "Explicit list of named elements visible in the figure. "
                    "Each entry should be a short phrase usable as an "
                    "annotation label (e.g. 'introduced TCR dimer')."
                ),
                "items": {"type": "string"},
            },
        },
    }


def match_response_schema() -> dict[str, Any]:
    """JSON schema for the match step's response."""
    return {
        "type": "object",
        "required": ["matches"],
        "properties": {
            "matches": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "element_name",
                        "matched_region_id",
                        "rationale",
                        "confidence",
                    ],
                    "properties": {
                        "element_name": {"type": "string"},
                        "matched_region_id": {
                            "type": "string",
                            "description": (
                                "MUST be one of the candidate region IDs "
                                "supplied in the user message (e.g. 'r0')."
                            ),
                        },
                        "rationale": {"type": "string"},
                        "confidence": {
                            "type": "number",
                            "description": "0.0–1.0",
                        },
                    },
                },
            }
        },
    }


def verify_response_schema() -> dict[str, Any]:
    """JSON schema for the verify step's response (one iteration)."""
    return {
        "type": "object",
        "required": ["annotated_image_read", "issues_found", "decision"],
        "properties": {
            "annotated_image_read": {
                "type": "string",
                "description": (
                    "Free-text summary of what the verifier saw on the annotated image."
                ),
            },
            "issues_found": {
                "type": "array",
                "items": {"type": "string"},
                "description": ("Empty list = no issues. Otherwise, one short string per issue."),
            },
            "decision": {
                "type": "string",
                "enum": [
                    "ACCEPT",
                    "RETRY_LOCALIZE",
                    "RETRY_MATCH",
                    "GIVE_UP",
                ],
            },
        },
    }


# ---------------------------------------------------------------------------
# Task dataclasses
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class DescribeFigureTask:
    """Step 1 task — Claude reads the figure image, describes its elements.

    Attributes
    ----------
    figure_path
        Path to the source figure file (PNG/JPG/etc). Callbacks open this.
    paper_doi
        DOI of the source paper (passed verbatim into the prompt for
        provenance).
    paper_tldr
        TL;DR / context for the paper. Helps the LLM recognize unfamiliar
        glyphs (e.g. "this paper introduces CODEX, a multiplexed-imaging
        method"). May be empty.
    system
        System prompt (role guard rails). Defaults to
        :data:`DESCRIBE_SYSTEM_PROMPT`.
    prompt
        User-message prompt (the specific ask, including the schema).
    response_schema
        JSON schema the response MUST match.
    """

    figure_path: Path
    paper_doi: str
    paper_tldr: str
    system: str
    prompt: str
    response_schema: dict[str, Any]


@dataclass(slots=True)
class MatchElementsTask:
    """Step 3 task — Claude pairs named elements with extracted regions.

    Attributes
    ----------
    figure_path
        Source figure (so callbacks can re-look-at the image when matching).
    described_elements
        Explicit element list returned by Step 1. May be empty if Step 1
        produced free text only — in which case the prompt also embeds the
        free-text description.
    description
        Free-text description from Step 1 (used in the prompt body so the
        match step has full context, not just the element list).
    regions
        Programmatically-extracted regions from Step 2 (color-motif
        connected components). Each gets a stable ID ``r<i>`` matching the
        order in this list.
    annotated_preview_path
        Optional pre-rendered preview (regions drawn onto the figure)
        passed to the matcher to give it a visual hint of where each
        region lives. ``None`` if the caller didn't pre-render.
    system
        System prompt. Defaults to :data:`MATCH_SYSTEM_PROMPT`.
    prompt
        User-message prompt.
    response_schema
        JSON schema the response MUST match.
    """

    figure_path: Path
    described_elements: list[str]
    description: str
    regions: list[Region]
    annotated_preview_path: Path | None
    system: str
    prompt: str
    response_schema: dict[str, Any]


@dataclass(slots=True)
class VerifyAnnotationTask:
    """Step 4 task — Claude reads the annotated image and accepts/retries.

    Attributes
    ----------
    annotated_image_path
        Rendered annotated PNG (figure + overlays + numbered markers).
    iteration
        1-indexed verify-loop iteration. The orchestrator caps this.
    expected_elements
        Names of the elements that SHOULD be annotated on the image.
    system
        System prompt. Defaults to :data:`VERIFY_SYSTEM_PROMPT`.
    prompt
        User-message prompt.
    response_schema
        JSON schema the response MUST match.
    """

    annotated_image_path: Path
    iteration: int
    expected_elements: list[str]
    system: str
    prompt: str
    response_schema: dict[str, Any]


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _build_describe_prompt(*, paper_doi: str, paper_tldr: str) -> str:
    tldr_clause = (
        f"PAPER TL;DR (for context only — describe THIS figure, do not "
        f"paraphrase the TL;DR):\n{paper_tldr.strip()}\n\n"
        if paper_tldr.strip()
        else "No TL;DR was supplied for this paper.\n\n"
    )
    return (
        f"PAPER DOI: {paper_doi or '<unknown>'}\n\n"
        f"{tldr_clause}"
        "TASK:\n"
        "Look at the attached figure and describe what is visually in it. "
        "Identify discrete elements that a downstream annotator could draw "
        "bounding boxes around (panels, receptor glyphs, color-coded "
        "regions, arrows, sub-panel insets, prominent labels). For each "
        "element, briefly note its color and approximate location.\n\n"
        "OUTPUT FORMAT:\n"
        'Return ONLY a JSON object: {"description": "<3–8 sentences>", '
        '"elements": ["<element 1>", "<element 2>", ...]}\n'
        "No markdown fencing, no preamble.\n"
    )


def _build_match_prompt(
    *,
    description: str,
    described_elements: Iterable[str],
    regions: Iterable[Region],
) -> str:
    elements = list(described_elements)
    region_lines: list[str] = []
    for i, r in enumerate(regions):
        x0, y0, x1, y1 = r.bbox_px
        region_lines.append(
            f"  r{i}: motif={r.motif_name!s} bbox=({x0},{y0})-({x1},{y1}) "
            f"area={r.area_px}px centroid={r.centroid_px}"
        )
    elements_block = (
        "\n".join(f"  - {e}" for e in elements)
        if elements
        else "  (none — Step 1 produced free text only; use the description below)"
    )
    return (
        "STEP 1 DESCRIPTION (free text from the Figure Reader):\n"
        f"{description.strip() or '(empty)'}\n\n"
        "STEP 1 NAMED ELEMENTS:\n"
        f"{elements_block}\n\n"
        f"STEP 2 REGIONS ({len(region_lines)} total — pair element names "
        "with one of these IDs):\n"
        + ("\n".join(region_lines) if region_lines else "  (none — Step 2 found no regions)")
        + "\n\n"
        "TASK:\n"
        "For each named element, pick the single region from the list above "
        "that most likely IS that element on the figure. Use the color "
        "motif, bounding-box position, and the description's spatial "
        "language to decide. Skip elements with no plausible match — do "
        "not force-pair.\n\n"
        "OUTPUT FORMAT:\n"
        'Return ONLY a JSON object: {"matches": [{"element_name": "<name>", '
        '"matched_region_id": "<r0/r1/...>", "rationale": "<1–2 sentences>", '
        '"confidence": <0.0–1.0>}, ...]}\n'
        "No markdown fencing, no preamble. Use ONLY the region IDs listed "
        "above.\n"
    )


def _build_verify_prompt(
    *,
    iteration: int,
    expected_elements: Iterable[str],
) -> str:
    elements_block = "\n".join(f"  - {e}" for e in expected_elements) or ("  (none provided)")
    return (
        f"VERIFY ITERATION: {iteration}\n\n"
        "TASK:\n"
        "Look at the attached annotated image (the figure with bounding-box "
        "overlays and numbered markers). The annotations claim to mark these "
        "elements:\n"
        f"{elements_block}\n\n"
        "Decide whether the annotations are correctly placed. If every "
        "marker is on or near its named element AND no marker collides with "
        "underlying text/figure content, return decision=ACCEPT. If the "
        "boxes are wrong (Step 2 problem), return RETRY_LOCALIZE. If the "
        "boxes are right but paired with the wrong element name (Step 3 "
        "problem), return RETRY_MATCH. If the figure is too unclear to "
        "annotate reliably, return GIVE_UP.\n\n"
        "OUTPUT FORMAT:\n"
        'Return ONLY a JSON object: {"annotated_image_read": "<what you '
        'see>", "issues_found": ["<issue 1>", ...], "decision": "ACCEPT"|'
        '"RETRY_LOCALIZE"|"RETRY_MATCH"|"GIVE_UP"}\n'
        "No markdown fencing, no preamble.\n"
    )


# ---------------------------------------------------------------------------
# Public prepare_* helpers
# ---------------------------------------------------------------------------


def prepare_describe_task(
    figure_path: str | Path,
    *,
    paper_doi: str,
    paper_tldr: str = "",
) -> DescribeFigureTask:
    """Build a :class:`DescribeFigureTask` ready for a callback to consume.

    Does not call any LLM. The caller (Claude Code session, SDK wrapper,
    test stub) feeds the task to its callback and gets back a JSON dict
    matching :func:`describe_response_schema`.
    """
    return DescribeFigureTask(
        figure_path=Path(figure_path),
        paper_doi=str(paper_doi),
        paper_tldr=str(paper_tldr or ""),
        system=DESCRIBE_SYSTEM_PROMPT,
        prompt=_build_describe_prompt(paper_doi=paper_doi, paper_tldr=paper_tldr),
        response_schema=describe_response_schema(),
    )


def prepare_match_task(
    figure_path: str | Path,
    *,
    description: str,
    described_elements: Iterable[str],
    regions: Iterable[Region],
    annotated_preview_path: str | Path | None = None,
) -> MatchElementsTask:
    """Build a :class:`MatchElementsTask`. Does not call any LLM."""
    elements_list = list(described_elements)
    region_list = list(regions)
    return MatchElementsTask(
        figure_path=Path(figure_path),
        described_elements=elements_list,
        description=str(description or ""),
        regions=region_list,
        annotated_preview_path=(Path(annotated_preview_path) if annotated_preview_path else None),
        system=MATCH_SYSTEM_PROMPT,
        prompt=_build_match_prompt(
            description=description,
            described_elements=elements_list,
            regions=region_list,
        ),
        response_schema=match_response_schema(),
    )


def prepare_verify_task(
    annotated_image_path: str | Path,
    *,
    iteration: int,
    expected_elements: Iterable[str],
) -> VerifyAnnotationTask:
    """Build a :class:`VerifyAnnotationTask`. Does not call any LLM."""
    expected = list(expected_elements)
    return VerifyAnnotationTask(
        annotated_image_path=Path(annotated_image_path),
        iteration=int(iteration),
        expected_elements=expected,
        system=VERIFY_SYSTEM_PROMPT,
        prompt=_build_verify_prompt(iteration=int(iteration), expected_elements=expected),
        response_schema=verify_response_schema(),
    )


# ---------------------------------------------------------------------------
# Public render_*_from_response helpers
# ---------------------------------------------------------------------------


def _coerce_dict(response: Any) -> dict[str, Any] | None:
    """Tolerate JSON strings as well as already-parsed dicts."""
    if response is None:
        return None
    if isinstance(response, dict):
        return response
    if isinstance(response, str):
        text = response.strip()
        if not text:
            return None
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("render: response was a non-JSON string; ignoring")
            return None
        return data if isinstance(data, dict) else None
    return None


def render_describe_from_response(
    response: dict[str, Any] | str | None,
    task: DescribeFigureTask,
) -> tuple[str, list[str]]:
    """Parse a describe-callback response into ``(description, elements)``.

    Returns ``("", [])`` on missing / malformed responses (the orchestrator
    tolerates an empty description; logs as skipped).
    """
    del task  # accepted for API symmetry; not currently used
    data = _coerce_dict(response)
    if data is None:
        return "", []
    desc = data.get("description")
    description = str(desc).strip() if isinstance(desc, str) else ""
    raw_elements = data.get("elements") or []
    elements: list[str] = []
    if isinstance(raw_elements, list):
        for item in raw_elements:
            if isinstance(item, str) and item.strip():
                elements.append(item.strip())
    return description, elements


def render_match_from_response(
    response: dict[str, Any] | str | None,
    task: MatchElementsTask,
) -> list[dict[str, Any]]:
    """Parse a match-callback response into the orchestrator's match list.

    Filters matches to region IDs that are actually present in
    ``task.regions`` (drops fabricated IDs). Drops entries missing required
    fields.
    """
    data = _coerce_dict(response)
    if data is None:
        return []
    raw = data.get("matches") or []
    if not isinstance(raw, list):
        return []
    valid_ids = {f"r{i}" for i in range(len(task.regions))}
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        rid = item.get("matched_region_id")
        if not isinstance(rid, str) or rid not in valid_ids:
            logger.debug("render_match: dropping invalid region id %r", rid)
            continue
        name = item.get("element_name")
        rationale = item.get("rationale", "")
        confidence = item.get("confidence", 0.0)
        try:
            conf_f = float(confidence)
        except (TypeError, ValueError):
            conf_f = 0.0
        out.append(
            {
                "element_name": str(name) if isinstance(name, str) else "",
                "matched_region_id": rid,
                "rationale": str(rationale) if isinstance(rationale, str) else "",
                "confidence": conf_f,
            }
        )
    return out


_ALLOWED_DECISIONS = ("ACCEPT", "RETRY_LOCALIZE", "RETRY_MATCH", "GIVE_UP")


def render_verify_from_response(
    response: dict[str, Any] | str | None,
    task: VerifyAnnotationTask,
) -> VerificationIteration:
    """Parse a verify-callback response into a :class:`VerificationIteration`.

    On a missing / malformed response, returns a ``GIVE_UP`` iteration so
    the orchestrator stops retrying instead of looping on garbage.
    """
    data = _coerce_dict(response)
    if data is None:
        return VerificationIteration(
            iteration=task.iteration,
            annotated_image_read="[verify response was missing or non-JSON]",
            issues_found=["malformed response"],
            decision="GIVE_UP",
        )
    read = data.get("annotated_image_read", "")
    issues_raw = data.get("issues_found") or []
    decision = data.get("decision", "")
    issues: list[str] = []
    if isinstance(issues_raw, list):
        for item in issues_raw:
            if isinstance(item, str) and item.strip():
                issues.append(item.strip())
    if not isinstance(decision, str) or decision not in _ALLOWED_DECISIONS:
        logger.warning("render_verify: invalid decision %r; coercing to GIVE_UP", decision)
        decision = "GIVE_UP"
    return VerificationIteration(
        iteration=task.iteration,
        annotated_image_read=str(read) if isinstance(read, str) else "",
        issues_found=issues,
        decision=decision,
    )
