"""vaultlab.report — HTML output for vaultlab artifacts.

A deep module: one entrypoint (``render_report``) plus a small set of
composable component primitives. Pure CSS + vanilla JS, no framework, no
external assets. Output is a single self-contained ``.html`` file.

Design rationale: see ``SKILL.md`` in this package and
``G:/My Drive/Knowledge/vaultlab/Output/Plans/html-and-nature-skills-2026-05-12.html``.

Background reading:

- Thariq Shihipar (Anthropic), "The Unreasonable Effectiveness of HTML" —
  https://thariqs.github.io/html-effectiveness
- Andrej Karpathy reply (X, 2026) on the text→markdown→HTML→neural progression.

Public API::

    from vaultlab.report import render_report, write_report
    from vaultlab.report import components as c

    html = render_report(
        title="Deck audit — multi-lung-short.pptx",
        eyebrow="vaultlab · slide audit",
        sections=[
            c.tldr_box(["12 slides", "2 warnings", "0 errors"]),
            c.card_grid([
                c.severity_card("Slide 1", body="OK", severity="good"),
                c.severity_card("Slide 2", body="Title overflow", severity="warn"),
            ]),
        ],
    )
"""

from __future__ import annotations

from vaultlab.report import _components as components
from vaultlab.report import editors
from vaultlab.report.approaches_compare_html import (
    Approach,
    ApproachesCompare,
    build_approaches_compare_html,
    write_approaches_compare_html,
)
from vaultlab.report.dispatch import (
    ArtifactKind,
    UnknownArtifact,
    render_artifact_html,
    write_artifact_html,
)
from vaultlab.report.feature_flag_editor import (
    FeatureFlagConfig,
    FlagGroup,
    build_feature_flag_editor,
    write_feature_flag_editor,
)
from vaultlab.report.flowchart_html import (
    Flowchart,
    FlowStep,
    build_flowchart_html,
    write_flowchart_html,
)
from vaultlab.report.html import Theme, render_report, write_report
from vaultlab.report.incident_timeline_html import (
    IncidentChecklist,
    IncidentReport,
    TimelineEntry,
    build_incident_timeline_html,
    write_incident_timeline_html,
)
from vaultlab.report.pr_writeup_html import (
    CommitEntry,
    FileChange,
    PRWriteup,
    build_pr_writeup_html,
    write_pr_writeup_html,
)
from vaultlab.report.state_dashboard_html import (
    StateDashboard,
    build_state_dashboard_html,
    write_state_dashboard_html,
)
from vaultlab.report.weekly_status_html import (
    WeeklyStatusReport,
    build_weekly_status_html,
    write_weekly_status_html,
)

__all__ = [
    "Approach",
    "ApproachesCompare",
    "ArtifactKind",
    "CommitEntry",
    "FeatureFlagConfig",
    "FileChange",
    "FlagGroup",
    "FlowStep",
    "Flowchart",
    "IncidentChecklist",
    "IncidentReport",
    "PRWriteup",
    "StateDashboard",
    "Theme",
    "TimelineEntry",
    "UnknownArtifact",
    "WeeklyStatusReport",
    "build_approaches_compare_html",
    "build_feature_flag_editor",
    "build_flowchart_html",
    "build_incident_timeline_html",
    "build_pr_writeup_html",
    "build_state_dashboard_html",
    "build_weekly_status_html",
    "components",
    "editors",
    "render_artifact_html",
    "render_report",
    "write_approaches_compare_html",
    "write_artifact_html",
    "write_feature_flag_editor",
    "write_flowchart_html",
    "write_incident_timeline_html",
    "write_pr_writeup_html",
    "write_report",
    "write_state_dashboard_html",
    "write_weekly_status_html",
]
