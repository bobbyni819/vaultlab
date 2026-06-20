---
module: vaultlab.figures.publication.bundle
purpose: Save a fixed publication figure bundle with contract validation, audit, coverage, and provenance
status: active
---

# Publication Bundle

`save_publication_figure()` is the publication-safe save path for matplotlib
figures. It takes an in-memory figure plus a `FigureContract`, validates the
contract, applies the shared figure rcParams, saves a fixed export set, runs
the pixel-layout audit, writes an optional coverage sidecar, and emits
provenance receipts.

For an output stem such as `figures/fig1`, the bundle writes:

- `figures/fig1_main.png` - raster preview and provenance anchor.
- `figures/fig1.svg` - editable vector export.
- `figures/fig1.pdf` - journal/submission vector export.
- `figures/fig1.coverage.json` - optional coverage manifest sidecar.
- `figures/fig1_main.png.provenance.json` - machine-readable receipt.
- `figures/fig1_main.png.method.md` - human-readable methods sidecar.

Warnings returned by `validate_contract()` are recorded in
`PublicationBundleResult.contract_warnings` and in the provenance receipt.
Hard contract failures still raise through the existing contract API.

`render_with_contract()` is a wrapper for existing recipes. Recipes keep their
current render signatures; the wrapper dispatches by recipe id, captures the
figure produced through the recipe's `save_fig` binding, and then routes that
figure through `save_publication_figure()`.

## Coverage Footer Rule

Coverage copy must come from `CoverageManifest.footer_text()`. The bundle
stores the manifest and its validation result so later figure-text checks can
compare captions, source data, and rendered footers against the same manifest
instead of trusting hardcoded prose.
