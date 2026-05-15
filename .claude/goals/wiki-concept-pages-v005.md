# /goal: Wiki/Concepts page authoring for v0.0.5 subsystems

_Created: 2026-05-15_
_Working dir: `G:/My Drive/Knowledge/vaultlab/Wiki/Concepts/`_
_Type: DOCS — persist v0.0.5 subsystems as KB concept articles per the `feedback_doc_persistence_baked_in` memory._

## CONTEXT

v0.0.5 shipped 19 sub-goals. Bobby's `feedback_doc_persistence_baked_in`
memory: pipeline features must persist as KB documentation, not just
one-off artifacts. `Wiki/Concepts/` holds LLM-compiled concept articles
with `[[backlinks]]` that future sessions can read for cold-start
context.

This goal authored 6 new concept pages covering the major v0.0.5
subsystems so future sessions have anchor pages to read when asked
"what was v0.0.5?" / "how does X work?".

## SUCCESS CRITERIA (all met)

1. ✅ Six concept pages exist at `G:/My Drive/Knowledge/vaultlab/Wiki/Concepts/`:
   - `audit-manifest-contract.md` — Red Line #2 enforcement
   - `nature-reader-absorption.md` — `vaultlab.research.full_reader`
   - `html-output-system.md` — `vaultlab.report` LEGO bricks (rewrote
     the v0.0.4 stub)
   - `crosstalk-and-dispatch.md` — SPEC-E + SPEC-F combined
   - `kb-primitives.md` — `vaultlab.kb` surface
   - `v0.0.5-release.md` — release-notes-style anchor
2. ✅ Each page has ≥3 wikilinks to other concept pages; every page
   touches at least 2 of the 5 sibling new pages.
3. ✅ Frontmatter matches the existing wiki-concept convention
   (`type: concept`, `created:`, `status:`, `tags:`, `related:`).
4. ✅ Pages cite real names from the v0.0.5 codebase
   (`vaultlab.provenance.write_receipts`, `ARTIFACT_ENTRYPOINTS`,
   `should_invoke` / `skip_reason`, `TaskSpec`, `classify` /
   `model_for_weight`, `retrieve_by_frontmatter`, `build_indexes`,
   `setup` / `lint`).
5. ✅ Each page is substantive (200-500 lines including frontmatter).
6. ✅ `vaultlab.kb.build_indexes` regenerated `_Index.md`,
   `_Catalog.md`, `_BackLinks.md` at the vaultlab KB root.

## WHAT LANDED

### Pages written

| Page | Lines | Wikilinks |
|---|---|---|
| `audit-manifest-contract.md` | 226 | 4 (v0.0.5 release, nature-skills-absorbed, html-output-system, crosstalk-and-dispatch) |
| `nature-reader-absorption.md` | 207 | 4 (nature-skills-absorbed, audit-manifest-contract, v0.0.5 release, crosstalk-and-dispatch) |
| `html-output-system.md` (rewrite) | 224 | 4 (nature-skills-absorbed, audit-manifest-contract, v0.0.5 release, kb-primitives) |
| `crosstalk-and-dispatch.md` | 232 | 4 (audit-manifest-contract, nature-reader-absorption, html-output-system, v0.0.5 release) |
| `kb-primitives.md` | 232 | 4 (v0.0.5 release, html-output-system, audit-manifest-contract, crosstalk-and-dispatch) |
| `v0.0.5-release.md` | 187 | 6 (all 5 sibling pages + nature-skills-absorbed) |

Total wikilinks across the 6 pages: 26.

### Index regenerated

```python
from pathlib import Path
from vaultlab.kb import build_indexes
result = build_indexes(Path("G:/My Drive/Knowledge/vaultlab"))
# index:     G:\My Drive\Knowledge\vaultlab\_Index.md
# catalog:   G:\My Drive\Knowledge\vaultlab\_Catalog.md
# backlinks: G:\My Drive\Knowledge\vaultlab\_BackLinks.md
```

All three KB indexes regenerated cleanly. The 6 new concept pages
now appear in `_Index.md` (grouped under `type: concept`),
`_Catalog.md` (chronological by `created: 2026-05-15`), and
`_BackLinks.md` (wikilink reference graph).

## EVIDENCE

- Pages on disk at `G:/My Drive/Knowledge/vaultlab/Wiki/Concepts/`
  (6 files, all dated 2026-05-15, all matching the wiki-concept
  frontmatter convention).
- Indexes auto-regenerated via `vaultlab.kb.build_indexes` —
  proves end-to-end use of the SPEC-C primitive shipped in v0.0.5.
- This goal file lives under git at
  `.claude/goals/wiki-concept-pages-v005.md` per the task brief
  (Wiki pages on Drive, goal file in repo).

## RELATED

- Goal docs catalogued in pages: `vaultlab-north-star.md`,
  `vaultlab-north-star-plan.md`, `wire-redline-invariant-tests.md`,
  `audit-manifest-framework-alignment.md`, `absorb-nature-reader.md`,
  `spec-c-kb-retrieval-upgrade.md`, `spec-d-kb-setup-primitive.md`,
  `spec-e-crosstalk-policy.md`, `spec-f-task-weight-dispatch.md`,
  `html-pattern-coverage-audit.md`,
  `html-patterns-top4-implementation.md`.
- Driving memory: `feedback_doc_persistence_baked_in` — pipeline
  features must persist as code/slash-cmd/CLAUDE.md/KB edits, not
  one-off artifacts.
