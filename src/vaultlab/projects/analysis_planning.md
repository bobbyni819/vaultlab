# Analysis Opportunity Planning

`analysis_planning.py` defines the deterministic opportunity schema for analysis gaps. The JSON schema string is `vaultlab-analysis-opportunity/v1`.

`find_coverage_gaps` consumes a `FigurePlan`, planned subpanels and supplements, and a `DataInventory`. It emits opportunities only for rule-based gaps: missing negative-control support, missing donor-aware support, or a needed dataset absent from inventory. It does not call an LLM and does not inspect files.

Opportunity priority is numeric, with lower values sorted earlier. Missing input data is emitted before missing negative controls, which is emitted before donor-aware support, because downstream planners need to know whether the data exists before assigning analysis work.

Lineage: CONCEPT from the projects package build spec's "machine-readable bridge" framing: planning gaps should be explicit records, not prose TODOs.

