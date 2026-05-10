"""vaultlab.figures.understand - hybrid figure-element extraction.

Phase 8b of the master-plan figures build. Bobby's 2026-04-29 insight:
LLM-only coordinate guessing is unreliable; pair the LLM's *semantic*
identification with *programmatic* pixel analysis to get precise locations.

Pipeline (master plan §3.5 + design rationale entry #8):

1. **Describe (LLM)** - read the figure visually; identify discrete elements
   in natural language ("there is a neon-green dimer in panel a representing
   the introduced TCR").
2. **Localize (programmatic)** - find pixel regions matching color motifs
   (or text labels via OCR; planned). Returns precise bounding boxes per
   region.
3. **Match (LLM)** - pair each named element with the best-fitting region.
4. **Verify (LLM, multimodal)** - render the annotated image; read it back;
   confirm each box landed on the intended element. Iterate if not.

This module owns step 2 (color motif extraction + region merging) and the
orchestrator :func:`understand_figure` that wires LLM-driven steps 1, 3, 4
into the localizer plus a per-figure reasoning log
(:class:`FigureUnderstandLog`). The LLM step callables are pluggable so
this module stays testable without an SDK installed; production callers
pass real Anthropic-backed callbacks.

Reasoning logs
--------------

Per Finding 9 of ``live-audit-notes-evening5-2026-04-30.md``, every
pipeline run that goes through :func:`understand_figure` (and any caller
who builds a :class:`FigureUnderstandLog` manually) can persist a markdown
sidecar at::

    <kb_root>/Sources/Figures/<doi-slug>/<fig-id>.understand.md

via :func:`save_understand_log`. The sidecar contains all four step
outputs plus per-iteration verify decisions so the LLM's thinking is
auditable, not just the final annotated PNG.

Public API
----------

- :class:`ColorMotif` - declarative color filter (HSV ranges + min area)
- :class:`Region` - extracted pixel region (bbox, area, centroid, motif)
- :class:`ElementAnnotation` - concept-to-region pairing for downstream use
- :class:`VerificationIteration` - one verify-loop pass (read / issues /
  decision)
- :class:`FigureUnderstandLog` - full per-figure reasoning trace
- :func:`extract_regions` - apply color motifs to an image; return regions
- :func:`merge_regions` - merge overlapping / adjacent regions of same motif
- :func:`render_debug_overlay` - draw colored bboxes onto the image with
  labels
- :func:`understand_figure` - orchestrate the 4-step pipeline + log capture
- :func:`save_understand_log` - write a log to its canonical KB path

Examples
--------

>>> from vaultlab.figures.understand import (
...     ColorMotif, extract_regions, merge_regions, render_debug_overlay
... )
>>> motifs = [
...     ColorMotif("introduced-tcr-green", (80, 140), 0.40, 0.40, 0.00003),
...     ColorMotif("endogenous-tcr-blue", (195, 240), 0.30, 0.35, 0.00003),
... ]
>>> regions = extract_regions("figure.png", motifs)  # doctest: +SKIP
>>> merged = merge_regions(regions, dilation_px=8)  # doctest: +SKIP
>>> render_debug_overlay("figure.png", merged, "debug.png")  # doctest: +SKIP
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from vaultlab.figures.understand._tasks import (
    DescribeFigureTask,
    MatchElementsTask,
    VerifyAnnotationTask,
    describe_response_schema,
    match_response_schema,
    prepare_describe_task,
    prepare_match_task,
    prepare_verify_task,
    render_describe_from_response,
    render_match_from_response,
    render_verify_from_response,
    verify_response_schema,
)
from vaultlab.figures.understand.color_motif import (
    ColorMotif,
    Region,
    extract_regions,
)
from vaultlab.figures.understand.merge import merge_regions
from vaultlab.figures.understand.models import (
    ElementAnnotation,
    FigureUnderstandLog,
    VerificationIteration,
)
from vaultlab.figures.understand.render import render_debug_overlay
from vaultlab.kb.paths import slugify_doi

__all__ = [
    "ColorMotif",
    "DescribeFigureTask",
    "ElementAnnotation",
    "FigureUnderstandLog",
    "MatchElementsTask",
    "Region",
    "VerificationIteration",
    "VerifyAnnotationTask",
    "describe_response_schema",
    "extract_regions",
    "match_response_schema",
    "merge_regions",
    "prepare_describe_task",
    "prepare_match_task",
    "prepare_verify_task",
    "render_debug_overlay",
    "render_describe_from_response",
    "render_match_from_response",
    "render_verify_from_response",
    "save_understand_log",
    "understand_figure",
    "verify_response_schema",
]


# ---------------------------------------------------------------------------
# Reasoning-log persistence
# ---------------------------------------------------------------------------


def save_understand_log(log: FigureUnderstandLog, kb_root: Path) -> Path:
    """Write a per-figure reasoning log to its canonical KB sidecar path.

    The path is::

        <kb_root>/Sources/Figures/<slugify_doi(log.doi)>/<fig-stem>.understand.md

    where ``<fig-stem>`` is :attr:`FigureUnderstandLog.figure_id` with any
    extension stripped (e.g. ``"fig1.png"`` -> ``"fig1"``).

    Idempotent: if the file already exists it is overwritten. Per the
    additive-rule discussion these logs are per-run reasoning traces, not
    user-edited documents, so overwriting on re-analysis is fine.

    Parameters
    ----------
    log
        The reasoning log to persist.
    kb_root
        Root of the KB (e.g. ``G:/My Drive/Knowledge/vaultlab``). Parent
        directories are created on demand.

    Returns
    -------
    Path
        Absolute path to the written markdown file.
    """
    kb_root = Path(kb_root)
    slug = slugify_doi(log.doi)
    stem = Path(log.figure_id).stem or log.figure_id
    out_dir = kb_root / "Sources" / "Figures" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{stem}.understand.md"
    out_path.write_text(log.to_markdown(), encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------


# Type aliases for the pluggable LLM callbacks. Production callers wire these
# to Anthropic SDK calls; tests stub them with deterministic Python lambdas.
DescribeFn = Callable[[Path], str]
"""``describe(image_path) -> free_text_description``."""

MatchFn = Callable[[str, list[Region]], list[dict[str, Any]]]
"""``match(description, regions) -> [{element_name, matched_region_id, rationale,
confidence}, ...]``."""

VerifyFn = Callable[[Path, list[ElementAnnotation], int], VerificationIteration]
"""``verify(annotated_png, annotations, iteration) -> VerificationIteration``.

The callable is responsible for re-rendering / reading whatever it needs;
the iteration counter is supplied so the implementation can vary behavior
(e.g., be stricter on the first pass, lenient on later passes)."""


_VERIFY_ITERATION_CAP = 5


def understand_figure(
    image_path: str | Path,
    motifs: Sequence[ColorMotif],
    *,
    doi: str,
    figure_id: str | None = None,
    annotated_png_path: str | Path | None = None,
    describe_fn: DescribeFn | None = None,
    match_fn: MatchFn | None = None,
    verify_fn: VerifyFn | None = None,
    dilation_px: int = 8,
    max_iterations: int = _VERIFY_ITERATION_CAP,
) -> tuple[list[ElementAnnotation], FigureUnderstandLog]:
    """Run the 4-step figure-understanding pipeline + capture a reasoning log.

    Steps that aren't supplied (no ``describe_fn`` / ``match_fn`` /
    ``verify_fn``) are recorded as skipped in the log rather than fabricated.
    This keeps the log honest when the orchestrator is invoked with only
    programmatic localization wired up — a real situation today, since the
    LLM legs of the pipeline are still being assembled.

    Parameters
    ----------
    image_path
        Source figure file.
    motifs
        Color motifs to scan for in the localize step.
    doi
        DOI of the source paper. Used to slug the reasoning-log directory.
    figure_id
        Override the default figure id (``image_path.name``). Useful when a
        figure is renamed downstream of the cache.
    annotated_png_path
        Where the rendered annotated PNG landed; recorded into the log.
    describe_fn / match_fn / verify_fn
        LLM callbacks for steps 1, 3, 4. ``None`` = step skipped (recorded as
        such in the log).
    dilation_px
        Forwarded to :func:`merge_regions`.
    max_iterations
        Cap on verify-loop iterations. Defaults to 5; loop stops earlier on
        ``ACCEPT`` or ``GIVE_UP``.

    Returns
    -------
    (annotations, log)
        ``annotations`` is the final list of :class:`ElementAnnotation`
        objects (one per accepted match); ``log`` is the populated
        :class:`FigureUnderstandLog` ready to be passed to
        :func:`save_understand_log`.
    """
    image_path = Path(image_path)
    fid = figure_id or image_path.name

    log = FigureUnderstandLog(
        doi=doi,
        figure_id=fid,
        generated_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        final_state="partial",
        n_iterations=0,
        annotated_png_path=str(annotated_png_path) if annotated_png_path else "",
    )

    # ---- Step 1: Describe (LLM) -----------------------------------------
    description = ""
    if describe_fn is not None:
        try:
            description = describe_fn(image_path) or ""
        except Exception as e:
            description = f"[describe_fn raised: {e!r}]"
    log.step1_description = description

    # ---- Step 2: Localize (programmatic) --------------------------------
    raw_regions = extract_regions(image_path, list(motifs))
    merged_regions = merge_regions(raw_regions, dilation_px=dilation_px)
    log.step2_regions = [
        {
            "id": f"r{i}",
            "color_motif": r.motif_name,
            "bbox": list(r.bbox_px),
            "source": "color_motif",
        }
        for i, r in enumerate(merged_regions)
    ]

    # ---- Step 3: Match (LLM) --------------------------------------------
    matches: list[dict[str, Any]] = []
    if match_fn is not None and merged_regions:
        try:
            matches = list(match_fn(description, list(merged_regions)) or [])
        except Exception as e:
            matches = [
                {
                    "element_name": "<error>",
                    "matched_region_id": "",
                    "rationale": f"match_fn raised: {e!r}",
                    "confidence": 0.0,
                }
            ]
    log.step3_matches = matches

    # Build initial annotations from the matches (region id -> Region).
    region_by_id = {f"r{i}": r for i, r in enumerate(merged_regions)}
    annotations: list[ElementAnnotation] = []
    for m in matches:
        rid = m.get("matched_region_id", "")
        region = region_by_id.get(rid)
        if region is None:
            continue
        annotations.append(
            ElementAnnotation(
                label=str(m.get("element_name", "")),
                bbox_px=region.bbox_px,
                explanation=str(m.get("rationale", "")),
                motif_name=region.motif_name,
                confidence=float(m.get("confidence", 0.0) or 0.0),
            )
        )

    # ---- Step 4: Verify (LLM, multimodal) -------------------------------
    if verify_fn is not None and annotations:
        png_arg = Path(annotated_png_path) if annotated_png_path else image_path
        for i in range(1, max_iterations + 1):
            try:
                vit = verify_fn(png_arg, annotations, i)
            except Exception as e:
                vit = VerificationIteration(
                    iteration=i,
                    annotated_image_read=f"[verify_fn raised: {e!r}]",
                    issues_found=[str(e)],
                    decision="GIVE_UP",
                )
            log.step4_verifications.append(vit)
            log.n_iterations = i
            if vit.decision in ("ACCEPT", "GIVE_UP"):
                break

    # ---- Final state ----------------------------------------------------
    if log.step4_verifications:
        last = log.step4_verifications[-1]
        if last.decision == "ACCEPT":
            log.final_state = "success"
        elif last.decision == "GIVE_UP":
            log.final_state = "failed"
        else:
            log.final_state = "partial"
    elif annotations:
        # Pipeline produced annotations but verify wasn't wired — partial.
        log.final_state = "partial"
    elif merged_regions:
        # Localized but didn't match — partial.
        log.final_state = "partial"
    else:
        log.final_state = "failed"

    return annotations, log
