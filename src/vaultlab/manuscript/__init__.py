"""vaultlab.manuscript — academic-prose tools.

Submodules:

- :mod:`vaultlab.manuscript.claim_ledger` — claim-to-figure/stat/citation
  ledger and no-untiered-claim gate.
- :mod:`vaultlab.manuscript.polish` — 25 prose rules + 12-step workflow +
  British-English vocabulary + sentence/spelling checkers.
- :mod:`vaultlab.manuscript.respond` — reviewer-response letter scaffolding
  (comment taxonomy, action map, parser, renderer).
- :mod:`vaultlab.manuscript.data_availability` — Data Availability
  statement templates, repository registry, FAIR checklist, audit
  helpers.

All three were absorbed from the nature-skills bundle (Yuan Yizhe, SJTU)
at github.com/Yuan1z0825/nature-skills, MIT-licensed; vaultlab credits
this in ``INSPIRATIONS.md`` (when added).
"""

from __future__ import annotations

from vaultlab.manuscript import claim_ledger, data_availability, polish, respond
from vaultlab.manuscript.claim_ledger import (
    CitationLink,
    CitationTier,
    Claim,
    ClaimLedger,
    ClaimReadiness,
    FigureLink,
    LedgerAudit,
    NumericLink,
)

__all__ = [
    "CitationLink",
    "CitationTier",
    "Claim",
    "ClaimLedger",
    "ClaimReadiness",
    "FigureLink",
    "LedgerAudit",
    "NumericLink",
    "claim_ledger",
    "data_availability",
    "polish",
    "respond",
]
