"""Universal HTML dispatcher for vaultlab artifacts.

Auto-detects the shape of a result dict and routes to the matching HTML
consumer. The companion to the ``/audit-html`` slash command, so the same
logic is usable programmatically:

    from vaultlab.report.dispatch import render_artifact_html, ArtifactKind
    html_str = render_artifact_html(some_dict)
    # or force a specific kind:
    html_str = render_artifact_html(data, kind="reasoning")

Detection rules (first match wins):

  * ``deck-audit`` — has ``slides`` and ``passed`` keys, OR has separate
    ``plan`` and ``audit`` keys.
  * ``litarc`` — has ``narrative`` and ``papers`` keys.
  * ``reasoning`` — has ``rounds`` and ``final_output`` keys.
  * ``citation`` — has ``citations`` and ``by_status`` keys.
  * ``dossier`` — has ``project_slug`` and ``sections`` keys.
  * ``response-letter`` — has ``reviewer`` and ``comments`` keys.
  * ``weekly-status`` — :class:`WeeklyStatusReport` (or a dict with
    ``week_label`` + ``tldr`` keys).
  * ``state-dashboard`` — :class:`StateDashboard` (or a dict with
    ``status_summary`` + ``module_map`` keys).
  * ``feature-flag-editor`` — :class:`FeatureFlagConfig` (or a dict with
    a ``groups`` key whose entries look like FlagGroup tuples).
  * ``approaches-compare`` — :class:`ApproachesCompare` (or a dict with
    ``approaches`` + ``decision_rationale`` keys).
  * ``visual-designs`` — :class:`VisualDesigns` (or a dict with
    ``title`` + ``options`` keys and no ``slides``).
  * ``component-variants`` — :class:`ComponentInventory` (or a dict
    with ``title`` + ``variants`` keys).
  * ``svg-figure-sheet`` — :class:`FigureSheet` (or a dict with
    ``title`` + ``schematics`` keys).

Raises :class:`UnknownArtifact` if no rule matches.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from vaultlab.provenance import ProvenanceRecord, write_receipts

ArtifactKind = Literal[
    "deck-audit",
    "litarc",
    "reasoning",
    "citation",
    "dossier",
    "response-letter",
    "weekly-status",
    "state-dashboard",
    "feature-flag-editor",
    "approaches-compare",
    "visual-designs",
    "component-variants",
    "svg-figure-sheet",
]


class UnknownArtifact(ValueError):
    """Raised when ``render_artifact_html`` can't infer the artifact shape."""


def _detect_kind(data: dict[str, Any] | Any) -> ArtifactKind:
    """Inspect a result dict and guess the artifact kind."""
    # Fast-path: dataclass instances dispatch by type so we don't have to
    # play guess-the-shape games for the v0.0.5 consumers.
    if not isinstance(data, dict):
        # Local imports to avoid circular import at module load.
        from vaultlab.report.approaches_compare_html import ApproachesCompare
        from vaultlab.report.component_variants_html import ComponentInventory
        from vaultlab.report.feature_flag_editor import FeatureFlagConfig
        from vaultlab.report.state_dashboard_html import StateDashboard
        from vaultlab.report.svg_figure_sheet_html import FigureSheet
        from vaultlab.report.visual_designs_html import VisualDesigns
        from vaultlab.report.weekly_status_html import WeeklyStatusReport

        if isinstance(data, WeeklyStatusReport):
            return "weekly-status"
        if isinstance(data, StateDashboard):
            return "state-dashboard"
        if isinstance(data, FeatureFlagConfig):
            return "feature-flag-editor"
        if isinstance(data, ApproachesCompare):
            return "approaches-compare"
        if isinstance(data, VisualDesigns):
            return "visual-designs"
        if isinstance(data, ComponentInventory):
            return "component-variants"
        if isinstance(data, FigureSheet):
            return "svg-figure-sheet"

    # Dataclass support: check attributes too.
    has = lambda k: (k in data) if isinstance(data, dict) else hasattr(data, k)  # noqa: E731

    # Most specific first.
    if has("rounds") and has("final_output"):
        return "reasoning"
    if has("citations") and has("by_status"):
        return "citation"
    if has("narrative") and has("papers"):
        return "litarc"
    if has("project_slug") and has("sections"):
        return "dossier"
    if has("reviewer") and has("comments"):
        return "response-letter"
    # v0.0.5 HTML consumers: keep these BEFORE deck-audit so a state
    # dashboard dict that happens to carry a 'slides' alias doesn't
    # mis-route. Each picks a pair of fields that are unique to its
    # dataclass.
    if has("week_label") and has("tldr"):
        return "weekly-status"
    if has("status_summary") and has("module_map"):
        return "state-dashboard"
    if has("approaches") and has("decision_rationale"):
        return "approaches-compare"
    if has("groups") and has("title") and not has("slides"):
        # Distinguish a FeatureFlagConfig from a deck plan: deck plans
        # always have a 'slides' key, FeatureFlagConfig never does.
        return "feature-flag-editor"
    if has("options") and has("title") and not has("slides"):
        # VisualDesigns: title + options. ApproachesCompare also has
        # 'approaches' but it doesn't use 'options'.
        return "visual-designs"
    if has("variants") and has("title"):
        return "component-variants"
    if has("schematics") and has("title"):
        return "svg-figure-sheet"
    if has("plan") and has("audit"):
        return "deck-audit"
    # Bare deck audit: a plan that has slides + passed at the top level
    # is uncommon (those are separate keys in practice), but handle it.
    if has("slides") and has("passed"):
        return "deck-audit"
    raise UnknownArtifact(
        "Could not infer artifact kind from the input shape. Pass kind= explicitly. "
        f"Got keys: {sorted(data.keys()) if isinstance(data, dict) else type(data).__name__}"
    )


def render_artifact_html(
    data: dict[str, Any] | Any,
    *,
    kind: ArtifactKind | None = None,
    **extra: Any,
) -> str:
    """Render a vaultlab artifact as a single-file HTML string.

    Dispatches based on ``kind`` (or auto-detected). ``extra`` kwargs are
    forwarded to the underlying consumer (e.g. ``topic="..."`` for litarc).
    """
    resolved_kind = kind or _detect_kind(data)

    if resolved_kind == "deck-audit":
        from vaultlab.slides.audit_html import build_audit_report_html

        # Either {plan, audit} or a flat plan that includes audit
        if isinstance(data, dict) and "plan" in data and "audit" in data:
            return build_audit_report_html(data["plan"], data["audit"], **extra)
        # Flat shape: split out the audit-shaped subset
        return build_audit_report_html(data, data, **extra)

    if resolved_kind == "litarc":
        from vaultlab.research.litarc_html import build_litarc_report_html

        payload = data if isinstance(data, dict) else data.__dict__
        # litarc requires keyword args
        params = {
            "topic": payload.get("topic", "(unknown topic)"),
            "narrative": payload.get("narrative", ""),
            "papers": payload.get("papers", []),
            "scope": payload.get("scope", "standard"),
            "citations": payload.get("citations"),
        }
        params.update(extra)
        return build_litarc_report_html(**params)

    if resolved_kind == "reasoning":
        from vaultlab.workflows.reasoning_html import build_reasoning_report_html

        return build_reasoning_report_html(data, **extra)

    if resolved_kind == "citation":
        from vaultlab.citations.report_html import build_citation_audit_html

        return build_citation_audit_html(data, **extra)

    if resolved_kind == "dossier":
        from vaultlab.kb.dossier_html import build_dossier_report_html

        return build_dossier_report_html(data, **extra)

    if resolved_kind == "response-letter":
        from vaultlab.manuscript.respond_html import build_response_letter_html

        return build_response_letter_html(data, **extra)

    if resolved_kind == "weekly-status":
        from vaultlab.report.weekly_status_html import (
            WeeklyStatusReport,
            build_weekly_status_html,
        )

        report = data if isinstance(data, WeeklyStatusReport) else WeeklyStatusReport(**data)
        # These consumers take their dataclass only; ignore extra kwargs
        # for now (callers can still customize by mutating the input).
        return build_weekly_status_html(report)

    if resolved_kind == "state-dashboard":
        from vaultlab.report.state_dashboard_html import (
            StateDashboard,
            build_state_dashboard_html,
        )

        state = data if isinstance(data, StateDashboard) else StateDashboard(**data)
        return build_state_dashboard_html(state)

    if resolved_kind == "feature-flag-editor":
        from vaultlab.report.feature_flag_editor import (
            FeatureFlagConfig,
            build_feature_flag_editor,
        )

        cfg = data if isinstance(data, FeatureFlagConfig) else FeatureFlagConfig(**data)
        return build_feature_flag_editor(cfg)

    if resolved_kind == "approaches-compare":
        from vaultlab.report.approaches_compare_html import (
            ApproachesCompare,
            build_approaches_compare_html,
        )

        comp = data if isinstance(data, ApproachesCompare) else ApproachesCompare(**data)
        return build_approaches_compare_html(comp)

    if resolved_kind == "visual-designs":
        from vaultlab.report.visual_designs_html import (
            VisualDesigns,
            build_visual_designs_html,
        )

        designs = data if isinstance(data, VisualDesigns) else VisualDesigns(**data)
        return build_visual_designs_html(designs)

    if resolved_kind == "component-variants":
        from vaultlab.report.component_variants_html import (
            ComponentInventory,
            build_component_variants_html,
        )

        inv = data if isinstance(data, ComponentInventory) else ComponentInventory(**data)
        return build_component_variants_html(inv)

    if resolved_kind == "svg-figure-sheet":
        from vaultlab.report.svg_figure_sheet_html import (
            FigureSheet,
            build_svg_figure_sheet_html,
        )

        sheet = data if isinstance(data, FigureSheet) else FigureSheet(**data)
        return build_svg_figure_sheet_html(sheet)

    raise UnknownArtifact(f"No renderer for kind: {resolved_kind!r}")


def write_artifact_html(
    out_path: Path | str,
    data: dict[str, Any] | Any,
    *,
    kind: ArtifactKind | None = None,
    **extra: Any,
) -> Path:
    """Render and write a vaultlab artifact as a single-file HTML."""
    resolved_kind = kind or _detect_kind(data)
    html_str = render_artifact_html(data, kind=resolved_kind, **extra)
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html_str, encoding="utf-8")

    # Audit-manifest contract (red line #2: no silent failures).
    # Every artifact-producing entrypoint writes provenance receipts;
    # see vaultlab/.claude/goals/vaultlab-north-star.md.
    record = ProvenanceRecord(
        generated_by="vaultlab.report.dispatch.write_artifact_html",
        kind="html_report",
        inputs=[],
        params={
            "artifact_kind": resolved_kind,
            "size_chars": len(html_str),
        },
    )
    write_receipts(str(p), record)
    return p


__all__ = [
    "ArtifactKind",
    "UnknownArtifact",
    "render_artifact_html",
    "write_artifact_html",
]
