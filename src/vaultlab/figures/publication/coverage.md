---
module: vaultlab.figures.publication.coverage
purpose: CoverageManifest JSON sidecar, validation, and footer rendering
status: active
---

# Coverage Manifest

`CoverageManifest` records what a publication figure actually covers: figure
identity, script path, panel role, included regions/donors/cell types,
exclusions, source-data paths and hashes, analysis parameters, and the footer
text if a rendered figure already carries one.

The manifest is the source of truth for coverage copy. Captions and in-figure
footers should call `manifest.footer_text()` or `manifest.as_footer_text()`
instead of hardcoding phrases such as "29 regions" or "all donors". This is
the anti-fabrication guard: if the manifest says two regions, the footer says
two regions.

## Sidecar I/O

Use `manifest.to_json(path)` to write `<stem>.coverage.json`. The writer uses a
temporary sibling file and then replaces the target, so interrupted writes do
not leave partial JSON. Use `CoverageManifest.read_json(path)` for a round-trip
back into the dataclass.

`to_dict()` and `from_dict()` expose the same schema for callers that need to
embed coverage metadata in a larger receipt.

## Validation

`validate()` returns a list of problems rather than raising. It checks missing
required identifiers, empty source-data paths, missing source hashes when a
hash map is supplied, negative numeric values in `params` or
`analysis_params`, and mismatch between an explicit `footer` and the footer
derived from manifest fields.

`audit()` wraps this as `CoverageAuditResult(ok, problems)` for bundle and
future `/figure-audit` integrations.
