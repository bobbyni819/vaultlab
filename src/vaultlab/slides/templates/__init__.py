"""vaultlab.slides.templates — deck composition recipes.

Each module exposes a single ``build_*`` function that returns a deck-plan
dict ready for :func:`vaultlab.slides.build_from_plan`. The plan dict is
the same shape ``build_from_plan`` documents — these builders just fill in
the right sequence of slide specs for a specific use case.

Templates available
-------------------

- :func:`build_investor_pitch` — 10-12 slide VC / seed pitch deck.
- :func:`build_lab_meeting` — 7-10 slide weekly lab update.
- :func:`build_conference_talk` — 12-15 slide 12+3 min conference talk.
- :func:`build_journal_club` — 10-12 slide paper-discussion deck.

All templates respect the hard slide rules (Roboto, 28/24/18 min sizes,
sentence-style titles, no shape overlap) by delegating layout to the
existing primitives in :mod:`vaultlab.slides.layouts`.

Distinct from :mod:`vaultlab.slides.journal_club_arcs`, which is an arc
*registry* (paper-type → slide-skeleton); the journal-club template here
is a full deck *builder* with Bobby's structured JC inputs.
"""

from __future__ import annotations

from vaultlab.slides.templates.conference_talk import build_conference_talk
from vaultlab.slides.templates.investor_pitch import build_investor_pitch
from vaultlab.slides.templates.journal_club import (
    READ_FIRST_PATH,
    build_journal_club,
    format_label_bullet,
)
from vaultlab.slides.templates.lab_meeting import build_lab_meeting

__all__ = [
    "READ_FIRST_PATH",
    "build_conference_talk",
    "build_investor_pitch",
    "build_journal_club",
    "build_lab_meeting",
    "format_label_bullet",
]
