# Template: data modality

To add a new data modality wrapper to vaultlab:

1. Copy this directory to `src/vaultlab/data/<modality>/`
2. Fill in: `ingest.py`, `qc.py`, `<core_processing>.py` + sibling `.md` docs
3. Add tests in `tests/test_vaultlab_data/test_<modality>/`
4. Document in `docs/modalities.md`

## Required components per modality

```
<modality>/
  __init__.py
  ingest.py + .md       # load files into a canonical in-memory representation
  qc.py + .md           # auto QC red flags (per AGENTS.md anti-laziness — return concrete warnings)
  <processing>.py + .md # modality-specific processing (clustering, segmentation, etc.)
```

## Conventions per AGENTS.md

- **Wrap, don't build.** Use scanpy / squidpy / scikit-image / cellpose / etc. Don't write your own segmentation algorithm.
- **LLM moments are explicit slash commands or `vaultlab.<modality>.llm.*` functions** with anti-laziness rules
- **Hedged voice** for all interpretations
- **Provenance receipt** auto-written for every analysis output

## Existing modalities

(Filled in once migration commits land):
- `codex` — multiplex IF
- `maldi` — MALDI-IMS
- `scrnaseq` — single-cell RNA-seq
- `spatial` — Visium / Xenium
- `imaging` — H&E / generic
- `flow` — flow cytometry
