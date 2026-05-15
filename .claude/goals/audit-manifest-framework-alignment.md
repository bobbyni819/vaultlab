# /goal: align audit-manifest contract terminology with existing vaultlab.provenance

_Created: 2026-05-15_
_Completed: 2026-05-15_
_Working dir: `C:/Users/bobby/Downloads/vaultlab`_

## CONTEXT

- **Sub-goal:** 1.2 of the north-star plan — **framework-alignment portion only**. Full sub-goal 1.2 (wire write_receipts into every artifact entrypoint) splits in two:
  - 1.2a (this goal): align spec + tests with reality. The audit-manifest concept already exists as `vaultlab.provenance.write_receipts` writing `.provenance.json` + `.method.md` sidecars.
  - 1.2b (next): wire write_receipts into citations/* + manuscript/* + report/* (the 4 holdouts).
- **Discovery:** `src/vaultlab/provenance/__init__.py` already implements the audit-manifest contract; 6 entrypoints already call it.

## SUCCESS CRITERIA

1. Strategic spec's Red Line #2 includes an implementation note clarifying that audit-manifest ≡ provenance-receipt. ✅
2. Invariant test's `test_every_artifact_entrypoint_writes_manifest` regex accepts both naming conventions (`write_receipts`, `ProvenanceRecord`, `.provenance.json`) plus the original `.audit.json` / `AuditManifest`. ✅
3. Invariant test's xfail reason is sharpened to name the exact 4 holdout module groups (citations, manuscript, report) and the entrypoints that DO already call write_receipts. ✅
4. Tests still green: 6 pass / 2 xfail. ✅

## PROGRESS

- Surveyed `vaultlab.provenance` module: confirmed it implements `<output>.provenance.json` + `<output>.method.md` sidecar contract. ✅
- Surveyed which entrypoints call provenance: found 6 (figures/publication/save, slides/deck, research/lineage, research/report, workflows/_provenance, onboarding/project_init). ✅
- Identified 4 module-group holdouts: citations/*, manuscript/*, report/*. ✅
- Updated strategic spec Red Line #2 with implementation note. ✅
- Updated invariant test regex to accept both vocabularies. ✅
- Re-ran tests: 6 pass / 2 xfail (unchanged headline numbers; the regex change doesn't flip anything yet because the holdouts are still holdouts). ✅

## EVIDENCE

- ✅ Criterion #1: `.claude/goals/vaultlab-north-star.md` Red Line #2 now reads "...The terms 'audit manifest' and 'provenance receipt' are aliases in vaultlab."
- ✅ Criterion #2: `tests/test_vaultlab_invariants/test_red_lines.py:test_every_artifact_entrypoint_writes_manifest` regex now matches `write_receipts|ProvenanceRecord|write_manifest|AuditManifest|\.provenance\.json|\.audit\.json`.
- ✅ Criterion #3: xfail reason now names exact holdouts and entrypoints that already comply, removing the previous handwave.
- ✅ Criterion #4: `6 passed, 2 xfailed in 1.21s`.

### Decisions made

- **Did NOT create a new `vaultlab.audit` module.** Reason: provenance already does the work; duplicating it under a second name creates churn for no value. The audit-manifest concept is alias-only.
- **Did NOT wire write_receipts into citations/manuscript/report.** Reason: that's a substantive code change touching ~10 files; belongs in sub-goal 1.2b as its own /goal run. This goal scope is alignment-only.
- **Kept xfail rather than flipping to passing.** Reason: the 4 holdouts are real gaps; flipping the test would mask them. The xfail with the sharpened reason makes the punch list explicit.

### Known limitations / followups

- **Sub-goal 1.2b (next):** `/goal "wire vaultlab.provenance.write_receipts into citations/*, manuscript/*, and report/* artifact-producing entrypoints so the audit-manifest invariant test passes"`. That's the closing fix.
- Once 1.2b lands, remove the xfail marker on `test_every_artifact_entrypoint_writes_manifest` and let the test pass cleanly.
