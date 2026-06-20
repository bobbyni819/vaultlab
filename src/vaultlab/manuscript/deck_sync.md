---
title: Deck Sync
type: manuscript-method
---

# Deck Sync

`vaultlab.manuscript.deck_sync` enforces the manuscript-to-deck figure rule:
every claim-ledger figure should appear in the collaborative slide deck, and
every deck figure should be linked from at least one manuscript claim.

The check reuses the existing `ClaimLedger.figure_links` records and the
existing slide-deck data models:

- `Deck.slides[*].figure_path` for low-level decks.
- `DeckPlan.slides[*].content["figure_path"]` for planned figure slides.
- `extra_deck_figures` for manually supplied deck figure paths.

## Matching Rule

Figure matching is deterministic and stem-based. `figure_key(...)` converts a
reference to its path stem, lowercases it, and strips a leading `figure` or
`fig` prefix when a non-empty key remains. This means a ledger figure ID such
as `figR5` matches a deck path such as `out/figR5.png`; both normalize to
`r5`.

This is a heuristic, not semantic figure understanding. It does not infer that
`R5_summary.png` and `figR5.png` are the same figure, and it does not compare
image content. Rename figure files or pass explicit `extra_deck_figures` when
the deck uses a different naming convention.

## Report

`sync_claims_to_deck(...)` returns a `DeckSyncReport` with:

- `claim_figures`: normalized unique figure keys from the claim ledger.
- `deck_figures`: normalized unique figure keys from the deck.
- `matched`: the intersection.
- `problems`: missing claim figures and orphan deck figures.

Unexpected deck shapes are treated as empty decks rather than errors, so the
sync check can run safely inside manuscript preflight or deck-review workflows.
