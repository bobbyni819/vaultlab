"""Data classes for figure understanding."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ElementAnnotation:
    """A concept paired with its localized region in an image.

    The output of the full describe-find-match pipeline. The renderer in
    :mod:`vaultlab.figures.understand.render` consumes these to draw labeled
    overlays on the original figure.

    Attributes
    ----------
    label
        Short text drawn on the figure (e.g., "Introduced TCR").
    bbox_px
        Pixel-space (x0, y0, x1, y1) bounding box.
    explanation
        Long-form description for speaker notes / hover popups.
    motif_name
        Which :class:`ColorMotif` produced the region (provenance - useful when
        a user disputes the box and wants to know how it was derived).
    confidence
        Coarse 0.0-1.0 confidence; larger regions on rare motifs score higher.
        Currently a placeholder; future: combine area-fraction + motif-rarity
        + LLM verification verdict.
    use_box
        Whether to draw a bounding-box outline around the element. Default True.
        Set False when the element is small/narrow enough that just a numbered
        marker pointing at it is cleaner (e.g., a thin band that a box would
        awkwardly wrap around). Bobby 2026-04-29 flexibility ask.
    marker_offset_px
        Optional (dx, dy) pixel offset for the marker position relative to the
        box's top-left corner. Default None = standard top-left placement.
        Used to avoid marker collisions when multiple annotations are clustered;
        place markers in nearby whitespace instead of all stacking on top.
        Coordinates are SOURCE PIXELS (not inches) to keep the API consistent
        with bbox_px.
    bbox_shape
        Geometry of the box outline. ``"rect"`` (default) = rectangle.
        ``"circle"`` = ellipse fit to the bbox (use when the underlying figure
        element is a circular zoom-in / detail callout). Bobby 2026-04-29 v8:
        rectangular boxes around circular zoom-ins look loose and wrong.
    bbox_padding_px
        Override the global ``layout.bbox_padding_px`` for this annotation.
        Either a scalar (uniform) or a 4-tuple ``(top, right, bottom, left)``
        for asymmetric padding. ``None`` = use the layout default. Bobby
        2026-04-29 v8: some boxes need more padding on one side and less on
        another; uniform is too coarse.
    marker_force_global
        If True, skip the local 8-direction ring search and go straight to the
        global whitespace search (find the nearest large free patch on the
        whole figure). Useful when the element is in a content-dense region
        where local offsets all collide. Bobby 2026-04-29 v8: "you can just
        slot the label somewhere on the figure as long as it's not blocking
        underlying text."
    """

    label: str
    bbox_px: tuple[int, int, int, int]
    explanation: str = ""
    motif_name: str = ""
    confidence: float = 0.0
    use_box: bool = True
    marker_offset_px: tuple[int, int] | None = None
    bbox_shape: Literal["rect", "circle"] = "rect"
    bbox_padding_px: int | tuple[int, int, int, int] | None = None
    marker_force_global: bool = False


# ---------------------------------------------------------------------------
# Reasoning-log dataclasses (Finding 9 from live-audit-notes-evening5)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class VerificationIteration:
    """One iteration of the verify-loop in the figure-understand pipeline.

    Attributes
    ----------
    iteration
        1-indexed iteration number within the verify loop.
    annotated_image_read
        The LLM's free-text description of the *rendered annotated PNG* (i.e.,
        what the verify-step model saw when handed the image with overlays).
    issues_found
        Concrete issues the LLM identified — empty list means accept.
    decision
        One of ``"ACCEPT"`` / ``"RETRY_LOCALIZE"`` / ``"RETRY_MATCH"`` /
        ``"GIVE_UP"``. Drives whether the loop continues and which step is
        revisited on retry.
    """

    iteration: int
    annotated_image_read: str
    issues_found: list[str]
    decision: str


@dataclass(slots=True)
class FigureUnderstandLog:
    """Full reasoning trace for a single figure's understanding pipeline.

    Persisted alongside the annotated PNG output so each LLM step's thinking
    is auditable. See :func:`vaultlab.figures.understand.save_understand_log`
    for the canonical write path.

    The four steps mirror the pipeline described in
    :mod:`vaultlab.figures.understand` (describe / localize / match / verify).
    Each step's output is captured into a dedicated field; the markdown
    rendering is produced by :meth:`to_markdown`.

    Attributes
    ----------
    doi
        DOI of the source paper (used to slug the output directory).
    figure_id
        Source filename (e.g. ``"fig1.png"``).
    generated_at
        ISO timestamp of when the log was finalized.
    final_state
        Pipeline outcome: ``"success"`` / ``"partial"`` / ``"failed"``.
    n_iterations
        Number of verify-loop iterations actually run.
    step1_description
        LLM's free-text description of the original (pre-annotation) figure.
    step2_regions
        Programmatic localization results — one dict per region:
        ``{"id": str, "color_motif": str, "bbox": (x0, y0, x1, y1), "source": str}``.
        ``source`` is e.g. ``"color_motif"`` or ``"whitespace"``.
    step3_matches
        LLM matching output — one dict per element:
        ``{"element_name": str, "matched_region_id": str, "rationale": str,
        "confidence": float}``.
    step4_verifications
        Append-only list of :class:`VerificationIteration` entries; the loop
        appends one per iteration and stops when ``decision == "ACCEPT"`` or
        the iteration cap is hit.
    annotated_png_path
        Where the final annotated PNG landed (string for portability across
        runs / backends).
    """

    doi: str
    figure_id: str
    generated_at: str
    final_state: str
    n_iterations: int

    step1_description: str = ""
    step2_regions: list[dict] = field(default_factory=list)
    step3_matches: list[dict] = field(default_factory=list)
    step4_verifications: list[VerificationIteration] = field(default_factory=list)

    annotated_png_path: str = ""

    # ------------------------------------------------------------------
    # Markdown rendering
    # ------------------------------------------------------------------

    def to_markdown(self) -> str:
        """Render this log as the canonical Obsidian-ready markdown.

        Layout (matches Finding 9 in live-audit-notes-evening5-2026-04-30):

        - YAML frontmatter (``doi``, ``figure_id``, ``generated_at``,
          ``final_state``, ``n_iterations``)
        - ``# Figure understanding — <figure_id>``
        - ``## Step 1 — Description (LLM)`` — blockquoted free text
        - ``## Step 2 — Localization (programmatic)`` — markdown table of
          regions
        - ``## Step 3 — Matching (LLM)`` — markdown table of element→region
        - ``## Step 4 — Verification (LLM, multimodal)`` — one ``### Iteration N``
          subsection per verify pass with bullets for the read + issues +
          decision
        """
        lines: list[str] = []

        # ---- frontmatter -------------------------------------------------
        lines.append("---")
        lines.append(f"doi: {self.doi}")
        lines.append(f"figure_id: {self.figure_id}")
        lines.append(f"generated_at: {self.generated_at}")
        lines.append(f"final_state: {self.final_state}")
        lines.append(f"n_iterations: {self.n_iterations}")
        if self.annotated_png_path:
            lines.append(f"annotated_png_path: {self.annotated_png_path}")
        lines.append("---")
        lines.append("")

        # ---- header ------------------------------------------------------
        lines.append(f"# Figure understanding — {self.figure_id}")
        lines.append("")

        # ---- Step 1 ------------------------------------------------------
        lines.append("## Step 1 — Description (LLM)")
        lines.append("")
        if self.step1_description.strip():
            for raw_line in self.step1_description.strip().splitlines():
                lines.append(f"> {raw_line}")
        else:
            lines.append(
                "_(no description captured — describe step was skipped or returned empty)_"
            )
        lines.append("")

        # ---- Step 2 ------------------------------------------------------
        lines.append("## Step 2 — Localization (programmatic)")
        lines.append("")
        if self.step2_regions:
            lines.append("| Region ID | Color motif | Bounding box | Source |")
            lines.append("|---|---|---|---|")
            for r in self.step2_regions:
                rid = r.get("id", "")
                motif = r.get("color_motif", "")
                bbox = r.get("bbox", "")
                source = r.get("source", "")
                bbox_str = (
                    f"({bbox[0]},{bbox[1]})-({bbox[2]},{bbox[3]})"
                    if isinstance(bbox, (list, tuple)) and len(bbox) == 4
                    else str(bbox)
                )
                lines.append(f"| {rid} | {motif} | {bbox_str} | {source} |")
        else:
            lines.append("_(no regions extracted)_")
        lines.append("")

        # ---- Step 3 ------------------------------------------------------
        lines.append("## Step 3 — Matching (LLM)")
        lines.append("")
        if self.step3_matches:
            lines.append("| Element name | Matched region | Rationale | Confidence |")
            lines.append("|---|---|---|---|")
            for m in self.step3_matches:
                name = m.get("element_name", "")
                rid = m.get("matched_region_id", "")
                rationale = m.get("rationale", "").replace("|", "\\|").replace("\n", " ")
                conf = m.get("confidence", "")
                conf_str = f"{conf:.2f}" if isinstance(conf, (int, float)) else str(conf)
                lines.append(f"| {name} | {rid} | {rationale} | {conf_str} |")
        else:
            lines.append(
                "_(no matches recorded — match step was skipped or no elements were paired)_"
            )
        lines.append("")

        # ---- Step 4 ------------------------------------------------------
        lines.append("## Step 4 — Verification (LLM, multimodal)")
        lines.append("")
        if self.step4_verifications:
            for it in self.step4_verifications:
                lines.append(f"### Iteration {it.iteration}")
                lines.append("")
                lines.append(f"- **Read annotated image:** {it.annotated_image_read}")
                if it.issues_found:
                    lines.append("- **Issues found:**")
                    for issue in it.issues_found:
                        lines.append(f"  - {issue}")
                else:
                    lines.append("- **Issues found:** _(none)_")
                lines.append(f"- **Decision:** `{it.decision}`")
                lines.append("")
        else:
            lines.append("_(no verification iterations recorded — verify step was skipped)_")
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"


__all__ = [
    "ElementAnnotation",
    "FigureUnderstandLog",
    "VerificationIteration",
]
