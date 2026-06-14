# vaultlab.data

Where vaultlab keeps two kinds of "data": the **bundled reference assets** other packages read (journal figure rules, demo seed) and the **planned wet-lab modality wrappers** that will eventually live alongside them.

Plain-language subsystem note: `G:\My Drive\Knowledge\vaultlab\Wiki\Concepts\vaultlab-subsystems.md`. Architectural sketch: [`docs/architecture.md`](../../../docs/architecture.md) (search `vaultlab.data.<modality>`).

## What it is

Most of vaultlab's packages *do* something. This one mostly *holds* things. Two parts share the folder, and it helps to keep them straight.

The first part is **shipped reference data** — files that travel inside the wheel so the rest of vaultlab works offline on first install. Today that's `journal_guidelines/` (the enforceable figure / stats rules for Nature, Cell, eLife, bioRxiv, plus a cross-journal `_common.yaml`) and `demo/` (one real open-access paper's metadata plus two synthetic figures, the seed for `vaultlab demo`). These are flat data assets — YAML, JSON, PNG — read by *other* packages, not an API you import.

The second part is the **per-modality wet-lab wrappers** the architecture calls for: `codex`, `maldi`, `scrnaseq`, `spatial`, `imaging`, `flow`. The intent (per `docs/architecture.md`) is thin glue over mature tools — scanpy/anndata for single-cell, squidpy for spatial, Cellpose/StarDist for multiplex IF — adding vaultlab's provenance, KB note-writing, and hedged interpretation rather than reimplementing the science. **As of now these are empty placeholders** (`"""Placeholder. Will be populated by migration commits."""`); nothing in them is callable yet.

## Public surface

There is **no importable Python API** at `vaultlab.data` today — the top-level and all six modality `__init__.py` files are placeholders. The package's live surface is data files (consumed by other packages) plus one bundled helper script:

- `journal_guidelines/*.yaml` — per-journal enforceable figure, font, color, and statistical-reporting rules (`nature`, `cell`, `elife`, `biorxiv`) plus `_common.yaml` (shared colorblind-safe palettes, accessibility thresholds, writing conventions). Loaded by `vaultlab.roles._invoke.load_journal_guideline_yaml` (and its `_common` sibling), which folds the parsed rules into the `AuditPrompt` bundle for the SPEC-B audit roles.
- `demo/paper.json` — bibliographic metadata, abstract, key claims, and discussion questions for one real open-access paper (Bhate et al., *Cell Systems* 2022); the deterministic seed for the `vaultlab demo` journal-club deck.
- `demo/figures/*.png` — two committed synthetic figures (cellular-neighborhood scatter, motif-frequency bars) so the demo renders without matplotlib at first run.
- `demo._generate_demo_figures.figure_1_cell_neighborhoods()` — regenerates the synthetic neighborhood-map PNG (seeded, deterministic).
- `demo._generate_demo_figures.figure_2_motif_frequencies()` — regenerates the synthetic motif-frequency bar chart PNG (seeded, deterministic).
- `demo._generate_demo_figures.main()` — regenerates both demo PNGs and prints their sizes; run via `python -m vaultlab.data.demo._generate_demo_figures` after editing the synthesis logic.

## How it fits

This package is a **leaf that other packages read from**, not an orchestrator:

- `vaultlab.roles._invoke` loads `journal_guidelines/<journal>.yaml` (+ `_common.yaml`) via `load_journal_guideline_yaml` and folds them into the `AuditPrompt` bundle (`journal_yaml` / `common_yaml` fields) handed to the four SPEC-B audit roles in `META_AGENT_ROLES` — most directly `publication_guideline_compliance`, whose prompt enforces those rules against a rendered figure. A project's `target_journal` is mapped to a YAML basename there via `JOURNAL_TARGET_DEFAULTS` (Cell-family targets all resolve to `cell.yaml`, Nature-family to `nature.yaml`). The figure **recipes** are *not* in this path: nothing in `_invoke.py` imports `vaultlab.figures`, and the recipe `.py` files load no YAML — their `.md` docs merely cite the same `_common.yaml`/`cell.yaml` rules as an authoring convention.
- `vaultlab.cli.demo` loads `demo/paper.json` and `demo/figures/` via `importlib.resources` and composes a five-slide journal-club deck with no LLM call and no network — so the deck is byte-stable across runs.
- The planned modality wrappers, once populated, would sit downstream of raw wet-lab inputs and upstream of `vaultlab.analysis` / `vaultlab.figures` (per the architecture diagram: `Workflows --> vaultlab.data.<modality>`).

## What it does NOT do

- It does **not** expose a Python API at `vaultlab.data` yet — the modality submodules are placeholders, so don't `from vaultlab.data.scrnaseq import ...` expecting anything.
- It does **not** ingest, QC, or process raw wet-lab data (FASTQ, BAM, imzML, .h5ad, OME-TIFF) today — that capability is described in the architecture but not yet implemented here.
- The bundled `demo/figures/*.png` are **synthetic**, not reproduced from the source paper; `paper.json` carries bibliographic metadata under fair use only.
- It does **not** fetch journal rules live — `journal_guidelines/*.yaml` are point-in-time snapshots (`last_fetched` stamped in each file), refreshed by editing the file, not by a network call.

## Files

- `__init__.py` — placeholder (no public symbols yet).
- `codex/`, `maldi/`, `scrnaseq/`, `spatial/`, `imaging/`, `flow/` — placeholder modality packages; each `__init__.py` is a stub awaiting migration.
- `journal_guidelines/_common.yaml` — cross-journal palettes, accessibility thresholds, statistical-reporting + writing conventions.
- `journal_guidelines/{nature,cell,elife,biorxiv}.yaml` — per-journal enforceable figure / font / color / stats rules.
- `demo/__init__.py` — docstring describing the bundled demo contents.
- `demo/paper.json` — the demo's journal-club seed paper (metadata + claims + discussion questions).
- `demo/figures/{fig1_neighborhoods,fig2_motif_frequencies}.png` — committed synthetic demo figures.
- `demo/_generate_demo_figures.py` — regenerates those PNGs (seeded; run once and commit the outputs).

## See also

- `vaultlab.cli.demo` (`cli/demo.py` + `cli/demo.md`) — the consumer of the `demo/` assets.
- `vaultlab.roles.publication_guideline_compliance` (`roles/publication_guideline_compliance/prompt.md`) — the consumer of `journal_guidelines/`.
- `vaultlab.figures.recipes` — the recipe **docs** (`spatial_neighborhood.md`, `stacked_bar.md`, `cci_heatmap.md`, `pseudobulk_volcano.md`, `metabolite_pathway_map.md`) cite `_common.yaml` / `cell.yaml` rules as an authoring reference. This is a documentation pointer only — the recipe `.py` files hardcode their own colorblind-safe palette defaults and do not load the YAML at runtime.
- [`docs/architecture.md`](../../../docs/architecture.md) — the `vaultlab.data.<modality>` design intent for the not-yet-built wrappers.
