---
title: Claim ledger
type: manuscript-method
---

# Claim Ledger

The claim ledger is the manuscript backbone: each manuscript claim maps to the
figure that shows it, the exact statistic and source file that support it, and
the citation verification tier that lets the claim ship.

Format:

`claim -> figure(s) -> exact stat + source file -> citation status`

This mirrors the proven Metabolism workflow:

- claim: the manuscript sentence or sentence-level assertion
- figure(s): one or more figure IDs, optionally with panels
- stat(source): exact reported value, source file, and optional method
- citation(tier): citation key plus verification status/tier

## Inline Tag Grammar

Tags are parsed deterministically from manuscript markdown. A link tag attaches
to the most recently declared claim in the same paragraph. Unknown tags are
ignored; malformed known tags produce parse warnings.

Declare a claim:

```markdown
[CLAIM:c1 kind=quantitative section=Results] Metabolism increases with hypoxia.
```

Link a figure:

```markdown
[FIG:figR5 panel=c]
```

Link an exact statistic and source:

```markdown
[STAT:rho=0.31 src=results/fig5.csv method=spearman]
```

Link a citation tier:

```markdown
[CITE:smith2020 tier=3 status=verified_fulltext]
```

Supported claim attributes are `kind`, `section`, `status`, and `risk`.
Supported citation statuses reuse `vaultlab.citations.models.VerificationStatus`.
Citation tier may be written as `1`, `2`, `3`, `tier_1`, `tier_2`, or `tier_3`.
When a citation status is present but no tier is given, status maps to tier:

- `VERIFIED_FULLTEXT` -> `TIER_3`
- `VERIFIED_ABSTRACT` -> `TIER_2`
- `API_CONFIRMED` -> `TIER_1`
- `UNVERIFIED`, `SUSPECT`, and `CONTRADICTED` -> untiered/default Tier 1 queue

## No-Untiered-Claim Gate

`ClaimLedger.audit()` flags:

- quantitative claims without a figure link
- quantitative claims without a numeric link
- non-`novel` claims without a citation link
- citation links below Tier 3
- missing numeric source files when `base_dir` is provided
- missing figure coverage manifests when `coverage_dir` is provided

`kind="novel"` means novel-no-cite-needed: the claim still needs figure and
numeric support if it is quantitative, but it does not fail the missing-citation
gate.

`ClaimLedger.needs_tier3()` returns the promotion queue: every citation link
that has not reached full-text Tier 3 verification.

## Pairing With Existing VaultLab Objects

Figure links reference `CoverageManifest.figure_id` from
`vaultlab.figures.publication.coverage`. When a coverage directory is supplied,
the audit checks for matching figure manifest JSON sidecars.

Citation links reuse `vaultlab.citations.models.VerificationStatus`; the ledger
does not redefine citation verifier statuses. The tier enum is only the
manuscript-readiness layer that turns citation verifier output into the shipping
gate.
