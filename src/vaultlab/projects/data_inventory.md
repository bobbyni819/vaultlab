# Data Inventory Contract

`data_inventory.py` defines the filesystem-free inventory schema for datasets that a project plan may need. The JSON schema string is `vaultlab-data-inventory/v1`.

`DatasetRecord.location` is an opaque string during validation. The inventory validator checks required metadata, duplicate dataset IDs, and simple numeric consistency without opening paths or contacting storage.

`DataInventory.summarize()` partitions datasets into available-or-staged, needs-collection, and restricted buckets. That summary is intentionally small so deterministic planners can decide whether an opportunity is blocked on collection without reading private data.

Lineage: PATTERN from vaultlab's existing sidecar contracts: typed JSON records, soft validation, and deterministic summaries before any execution layer.

