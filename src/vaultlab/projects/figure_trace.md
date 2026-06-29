# Figure Trace Bridge

`figure_trace.py` connects a planned subpanel to existing figure QA sidecars.

`trace_subpanel` resolves optional relative paths against `base_dir`, lazily loads `CoverageManifest`, `FigureLayoutSidecar`, and provenance text, runs the existing audits, and calls `evaluate_promotion` to compute readiness. Missing or unreadable files become named `problems`; callers can inspect the trace without catching sidecar exceptions.

Reaching the top `DECK_READY` rung requires slide-placement evidence the figure sidecars cannot supply on their own. Pass `panel_audit=` (the `PanelLayoutAudit` from `audit_panel_layout_contract` for the contract slot this subpanel fills) to let a subpanel be promoted to `DECK_READY`. Without it, a subpanel caps at `GEOMETRY_QA_PASSED` and a `DECK_READY` claim is blocked with `panel_audit_missing` rather than silently accepted — the same anti-trust-by-assertion discipline the rest of the ladder enforces.

`link_panel_slot_to_subpanel` maps each `PanelLayoutContract` slot letter to the matching `SubpanelPlan.panel_slot_id`. Ambiguous or absent matches return `None`.

This module does not modify the layout sidecar implementation. Off-canvas visual QA enhancements remain a later layer; this bridge consumes the current sidecar audit surface.

Lineage: PATTERN from registry-style joins across `CoverageManifest`, `FigureLayoutSidecar`, `PanelLayoutContract`, and `ClaimLedger`.
