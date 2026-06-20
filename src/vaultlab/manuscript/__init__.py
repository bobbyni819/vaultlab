"""vaultlab.manuscript — academic-prose tools.

Submodules:

- :mod:`vaultlab.manuscript.claim_ledger` — claim-to-figure/stat/citation
  ledger and no-untiered-claim gate.
- :mod:`vaultlab.manuscript.citation_gate` — Tier-3 citation gate and
  promotion queue.
- :mod:`vaultlab.manuscript.polish` — 25 prose rules + 12-step workflow +
  British-English vocabulary + sentence/spelling checkers.
- :mod:`vaultlab.manuscript.respond` — reviewer-response letter scaffolding
  (comment taxonomy, action map, parser, renderer).
- :mod:`vaultlab.manuscript.data_availability` — Data Availability
  statement templates, repository registry, FAIR checklist, audit
  helpers.
- :mod:`vaultlab.manuscript.deck_sync` — claim-ledger figure links synced
  against deck figure references.
- :mod:`vaultlab.manuscript.figure_text_consistency` — deterministic
  checks for figure callouts, numeric links, and figure identity labels.
- :mod:`vaultlab.manuscript.preflight` — reviewer-perspective manuscript
  preflight gate combining deterministic checks with prepared role passes.
- :mod:`vaultlab.manuscript.state` — durable manuscript lifecycle state
  derived from preflight and citation gates.
- :mod:`vaultlab.manuscript.verification_ladder` — per-claim and per-figure
  strict verification ladder composed from the manuscript gates.

All three were absorbed from the nature-skills bundle (Yuan Yizhe, SJTU)
at github.com/Yuan1z0825/nature-skills, MIT-licensed; vaultlab credits
this in ``INSPIRATIONS.md`` (when added).
"""

from __future__ import annotations

from vaultlab.manuscript import (
    citation_gate,
    claim_ledger,
    data_availability,
    deck_sync,
    figure_text_consistency,
    polish,
    preflight,
    respond,
    state,
    verification_ladder,
)
from vaultlab.manuscript.citation_gate import (
    CitationGateReport,
    CitationTierStatus,
    PromotionAction,
    run_citation_gate,
)
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
from vaultlab.manuscript.data_availability import (
    CoverageDataSources,
    FigureDataSource,
    data_sources_from_coverage,
    merge_into_das,
)
from vaultlab.manuscript.deck_sync import (
    DeckSyncProblem,
    DeckSyncReport,
    figure_key,
    sync_claims_to_deck,
)
from vaultlab.manuscript.figure_text_consistency import (
    ConsistencyProblem,
    ConsistencyReport,
    FigureCallout,
    check_figure_text_consistency,
)
from vaultlab.manuscript.preflight import (
    FixItem,
    ManuscriptPreflightReport,
    PreparedRolePass,
    run_manuscript_preflight,
)
from vaultlab.manuscript.state import (
    ManuscriptStage,
    ManuscriptState,
    StageGate,
    assess_manuscript,
)
from vaultlab.manuscript.verification_ladder import (
    ClaimRung,
    FigureRung,
    LadderRung,
    VerificationLadderReport,
    assess_verification_ladder,
)

__all__ = [
    "ClaimRung",
    "CitationLink",
    "CitationGateReport",
    "CitationTier",
    "CitationTierStatus",
    "Claim",
    "ClaimLedger",
    "ClaimReadiness",
    "ConsistencyProblem",
    "ConsistencyReport",
    "CoverageDataSources",
    "DeckSyncProblem",
    "DeckSyncReport",
    "FigureRung",
    "FigureCallout",
    "FigureDataSource",
    "FigureLink",
    "FixItem",
    "LadderRung",
    "LedgerAudit",
    "ManuscriptStage",
    "ManuscriptPreflightReport",
    "ManuscriptState",
    "NumericLink",
    "PreparedRolePass",
    "PromotionAction",
    "StageGate",
    "VerificationLadderReport",
    "assess_manuscript",
    "assess_verification_ladder",
    "check_figure_text_consistency",
    "claim_ledger",
    "citation_gate",
    "data_availability",
    "data_sources_from_coverage",
    "deck_sync",
    "figure_text_consistency",
    "figure_key",
    "merge_into_das",
    "polish",
    "preflight",
    "respond",
    "run_citation_gate",
    "run_manuscript_preflight",
    "state",
    "sync_claims_to_deck",
    "verification_ladder",
]
