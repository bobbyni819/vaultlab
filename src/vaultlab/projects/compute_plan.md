# Compute Plan Contract

`compute_plan.py` defines the deterministic compute-target contract for one planned analysis. The JSON schema string is `vaultlab-compute-plan/v1`.

`ResourceHints` carries only arithmetic inputs: row counts, unit counts, input size, per-row byte estimates, and optional prior observed peak RAM or runtime. `classify_compute_target` never talks to Slurm, SSH, cloud APIs, or the filesystem. It prefers `prior_peak_ram_gb` when present; otherwise it falls back to row-count times per-row bytes, then input bytes.

`ComputePlan.validate()` keeps project policy separate from classification. A remote-cluster plan is flagged when it lacks a smoke-run command or checkpoint strategy, but the classifier itself does not fabricate those commands.

Lineage: PATTERN from the planning-contract layer in the projects package build spec: deterministic schema first, orchestration later.

