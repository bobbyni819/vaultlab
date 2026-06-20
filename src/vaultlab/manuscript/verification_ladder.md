---
title: Manuscript verification ladder
type: methodology
---

# Manuscript verification ladder

`vaultlab.manuscript.verification_ladder` turns the manuscript evidence checks
into one strict status per claim and per referenced figure. It composes existing
deterministic gates; it does not reimplement citation verification, claim-ledger
auditing, visual QA, or manuscript preflight.

## Rungs

- `PROPOSED` - the tagged claim or referenced figure exists in the ledger.
- `SOURCE_SEARCHED` - a claim has at least one citation link, or it is tagged
  `kind=novel`.
- `QUOTE_BACKED` - every citation link for the claim is `CitationTier.TIER_3`.
- `RENDERED` - a claim has at least one figure link and every referenced figure
  has either a coverage manifest (`<figure>.coverage.json`) or a rendered
  figure file (`.png`, `.svg`, or `.pdf`). A figure reaches this rung when the
  same rendered-file or coverage-sidecar check passes.
- `PIXEL_AUDITED` - each referenced rendered PNG has a `visual_qa_figure(...)`
  result whose verdict is not `FAIL`. `PASS` and `WARN` both count as audited.
- `REVIEWER_APPROVED` - manuscript preflight has no error fix item touching the
  claim or figure, and any aggregated reviewer verdict that exists is acceptable.

The ladder is strict: an item is assigned the highest rung for which that rung
and all lower rungs hold. `next_blocker` names the first failed advancement.

## Composed checks

The module delegates the source data to:

- `ClaimLedger.from_markdown(...)` for claims and claim-to-citation/figure links.
- `run_citation_gate(...)` for Tier-3 promotion blockers.
- `run_manuscript_preflight(...)` for deterministic reviewer-facing fix items.
- `visual_qa_figure(..., run_vision=False)` for optional pixel audit status.
- Publication coverage sidecars from `figures.publication.coverage` conventions
  for rendered-figure existence.

Missing optional inputs never raise through the public API. A missing coverage
directory, missing figure directory, absent PNG, or failed optional audit simply
caps the affected item at the last rung that can be proven.

## Weakest-claim framing

`VerificationLadderReport.min_claim_rung` is the weakest claim rung. The
markdown dashboard leads with this because a manuscript is only as verified as
its weakest claim; stronger claims and figures remain visible, but they do not
hide the item that still blocks the manuscript.
