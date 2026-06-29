# Figure Plan Contract

`figure_plan.py` defines the machine-readable plan bundle for one publication figure. The JSON schema string is `vaultlab-figure-plan/v1`.

The contract is intentionally path-opaque during validation. `manifest_path`, `layout_sidecar_path`, `visual_qa_path`, `provenance_path`, scripts, and outputs are strings that later bridge to sidecars; `validate_figure_plan` never opens them.

The main invariant is that `SubpanelPlan` is the join object:

- It points downstream to `CoverageManifest`, `FigureLayoutSidecar`, `PanelSlot.letter`, and `ClaimLedger.FigureLink`.
- It points upstream to analysis and plotting scripts.
- It owns supplement links so planned controls and archive figures cannot silently orphan.

Lineage: PATTERN from vaultlab's existing sidecar contracts (`CoverageManifest`, `ClaimLedger`) and the planning-contract pattern described in the projects package build spec.
