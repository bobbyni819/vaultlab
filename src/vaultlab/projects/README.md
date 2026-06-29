# vaultlab.projects

`vaultlab.projects` is the upstream planning layer that turns project intent into machine-readable contracts before figures are rendered. It does not run analyses or edit figure files. It records what each panel is supposed to be, checks whether sidecars support that claim, and bridges planned subpanels to publication QA artifacts.

## Contracts

1. `figure_plan.py` defines `FigurePlan`, `SubpanelPlan`, and `SupplementPlan`. `SubpanelPlan` is the join object that connects one intended panel to analysis scripts, output figures, coverage manifests, layout sidecars, provenance, panel slots, claims, and supplements.
2. `readiness.py` defines the readiness ladder: `DISPLAY_EXISTS`, `PROVENANCE_VERIFIED`, `GEOMETRY_QA_PASSED`, `DECK_READY`, and `FAILED`. `evaluate_promotion` only promotes monotonically when provenance, coverage, layout, and panel audits support the requested rung.
3. `figure_trace.py` loads the existing figure QA sidecars lazily and computes readiness for one `SubpanelPlan`. Missing files become named trace problems rather than exceptions. Pass a `panel_audit` to let a subpanel reach `DECK_READY`.
4. `compute_plan.py` defines `ComputePlan` and `classify_compute_target`, a deterministic local-vs-remote classifier from RAM/walltime hints (no Slurm/SSH).
5. `data_inventory.py` defines `DataInventory`/`DatasetRecord` with `summarize()` splitting available/staged from needs-collection/restricted.
6. `analysis_planning.py` defines `find_coverage_gaps`, a deterministic gap-finder that flags a missing negative control, a dataset absent from the inventory, and missing donor-aware support, ordered by priority.
7. `lane_log.py` defines `LaneHandoff`/`ReadReceipt` with `validate_handoff` (required-read enforcement is caller-supplied) and `merge_handoffs` into a `LaneStatusReport`.

Every contract is a frozen dataclass with `to_dict`/`from_dict` JSON round-trips, a `validate()`/`audit()` surface, a `pass`/`warn`/`fail` severity grammar, and a versioned `SCHEMA` string. Everything here is deterministic and CI-safe; schema validation never touches the filesystem.

## Key Join

```text
FigurePlan.figure_id -- FigureContract.evidence_chain -- ClaimLedger.FigureLink.figure_id
   subpanel_ids(letter) -- evidence_chain[letter]            FigureLink.panel == letter
SubpanelPlan -- manifest_path -> CoverageManifest (regions/donors/source_data/sha256)
             -- layout_sidecar_path -> FigureLayoutSidecar -> audit_layout_sidecar()
             -- panel_slot_id -> PanelSlot.letter on PanelLayoutContract
             -- claim_id -> ClaimLedger
             -- analysis_script -> ComputePlan.analysis_id
SupplementPlan.parent_subpanel_id -> SubpanelPlan.subpanel_id   (no orphans)
```
