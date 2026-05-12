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
from vaultlab.report.html import Theme, render_report, write_report

__all__ = ["Theme", "components", "editors", "render_report", "write_report"]
