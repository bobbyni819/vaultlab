# Lane Log Contract

`lane_log.py` defines read receipts and lane-to-lane handoffs for project planning. The JSON schema string is `vaultlab-lane-log/v1`.

`ReadReceipt` records what context a role read before acting. `LaneHandoff` records the source lane, target lane, artifacts, verification evidence, downstream request, open decisions, and receipts. Validation is deterministic and path-opaque: required reads are matched by exact string only.

`validate_handoff` flags two high-cost coordination failures: a required read path with no matching receipt, and a non-draft handoff with empty verification. `merge_handoffs` aggregates records by `(source, target)` into a `LaneStatusReport` for lane dashboards without rewriting the source handoff records.

Lineage: PATTERN from vaultlab's KB-mediated async workflow: handoffs should carry read receipts and verification evidence rather than relying on chat memory.

