---
title: Citation tier gate
type: manuscript-rule
---

# Citation tier gate

The citation gate enforces the manuscript rule: no claim ships with an
untiered or under-tiered citation. The default gate requires Tier-3 evidence,
meaning a full-text-verifiable citation with a verbatim quote and section
label.

## Tier ladder

- Tier-1: `VerificationStatus.API_CONFIRMED`; the DOI or PMID exists.
- Tier-2: `VerificationStatus.VERIFIED_ABSTRACT`; the abstract supports the
  manuscript claim.
- Tier-3: `VerificationStatus.VERIFIED_FULLTEXT`; full text supports the claim
  with a verbatim quote and section label.

`run_citation_gate` reuses `CitationTier.from_verification_status` from the
claim ledger. It does not redefine the tier mapping.

## Promotion queue

The gate is deterministic and advisory. It reports what must be promoted, but
it does not fetch papers, query APIs, call an LLM, or write evidence records.
Actual fetching and verification remain the job of the citations and research
pipelines.

Promotion actions are concrete:

- Untiered with DOI/PMID: verify the identifier, then fetch the abstract.
- Untiered without DOI/PMID: find the identifier before tiering.
- Tier-1: fetch the abstract and confirm claim support.
- Tier-2: fetch full text and extract a verbatim quote with section label.
- Suspect or contradicted: resolve the citation before citing it.

## Composition

The gate accepts one source at a time:

- a list of `vaultlab.citations.Citation` objects;
- raw manuscript markdown, parsed with `extract_citations_from_text`;
- a `ClaimLedger`, using existing `CitationLink.tier` values.

The output is a `CitationGateReport` with per-citation statuses, the blocked
set, and the promotion queue. Markdown output is for review; dict output is for
automation.
