---
name: Add a tool wrapper
about: Propose vaultlab wrap a new Python package
title: "[TOOL] Add wrapper for "
labels: enhancement, good-first-issue
assignees: bobbyni819
---

## Tool to wrap

- **Package name:** (e.g., `harmonypy`)
- **What it does:** (one-line)
- **Modality:** (which `vaultlab.data.<modality>` it fits)
- **Heaviness:** (light Python deps / medium / heavy install)
- **Docs:** (link)

## Why vaultlab should wrap it

(use case; what users would gain)

## Existing alternatives

(other packages in vaultlab that overlap; why this one adds value)

## Proposed integration

- [ ] New module: `src/vaultlab/<modality>/<tool>.py + .md`
- [ ] Tool index entry: `src/vaultlab/kb/tools_index/<tool>.md`
- [ ] Tests: `tests/test_vaultlab_<modality>/test_<tool>.py`
- [ ] Sample fixture
- [ ] Documentation in modality README

## Are you willing to contribute the wrapper?

- [ ] Yes — I'll open a PR with the [`templates/data_modality/`](../../templates/data_modality/) scaffold
- [ ] Yes, but I need help — happy to pair
- [ ] No — just suggesting
