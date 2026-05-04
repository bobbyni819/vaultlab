"""Use-case-specific deck templates.

Each module provides a canonical slide-structure outline + section
helpers for a specific presentation context:

- :mod:`prelim_qual` — PhD prelim / qualifying exam (30-45 min + Q&A)
- :mod:`investor_pitch` — 10-12 slide investor pitch (10-15 min)
- :mod:`lab_meeting` — internal weekly update (30-60 min)
- :mod:`conference_talk` — 15-20 min external conference talk
- :mod:`journal_club` — paper-walk + critique (20-30 min)
- :mod:`thesis_defense` — extended prelim format (45-60 min)

Usage::

    from vaultlab.slides.templates import prelim_qual

    plan = prelim_qual.build_outline(
        title="Multiscale tissue simulation for lung infection",
        speaker="Bobby Y.X. Ni",
        advisor="John Hickey",
        committee=["A", "B", "C", "D"],
        aims=[...],
    )
    build_from_plan(plan, "prelim.pptx")
"""

from __future__ import annotations

__all__: list[str] = []  # subpackages export their own
