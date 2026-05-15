# `vaultlab demo`

**One-line:** produce a real audit-clean artifact from bundled sample data in <5 min, fully offline.

## Why

North-star Criterion #4: a new user runs `pip install vaultlab` cold and produces a non-trivial audit-clean artifact in ≤30 min. `vaultlab demo` is the load-bearing enabler — a single command that ships sample data, runs the pipeline, and writes audit-clean output. No KB, no API key, no Claude Code session required to confirm the install works.

## What it does

1. Resolves the output directory (default `./vaultlab-demo-out`).
2. Copies bundled sample paper metadata (`paper.json`) + synthetic figures (2 PNGs) into `<out>/inputs/`.
3. Composes a deterministic ~7-slide `DeckPlan` (title / context / figure / findings / figure / discussion / references) from the metadata — **no LLM call**.
4. Renders `<out>/deck.pptx` via `vaultlab.slides.deck.build_deck`.
5. Writes the standard vaultlab provenance receipts (`.provenance.json` + `.method.md`) next to the deck.

Total runtime ~1-2s on a typical laptop. Zero network calls (covered by a `socket.socket`-blocking test).

## Sample paper

Bobby ships bibliographic metadata for one real PMC-OA paper (Bhate et al. 2022, Cell Systems, "Tissue schematics map the specialization of immune tissue motifs and their appropriation by tumors", PMC9509566). Only factual citation data is bundled. **No source-paper figures are reproduced** — the demo's two PNGs are synthetic illustrations produced by `vaultlab.data.demo._generate_demo_figures` and committed for offline first-run.

## Usage

```bash
# Default location
vaultlab demo

# Custom output dir
vaultlab demo --out-dir ~/scratch/vl-demo

# Programmatic (e.g. from a script or test)
python -c "from vaultlab.cli.demo import run_demo; print(run_demo('/tmp/x'))"
```

## Customizing

The demo seed is `<out>/inputs/paper.json` — copied from the bundled file on first run. Edit the copy (key claims, discussion questions, title) and re-run; the demo reads the local copy, not the bundled one. To refresh the synthetic figures, edit `src/vaultlab/data/demo/_generate_demo_figures.py` and run `python -m vaultlab.data.demo._generate_demo_figures`.

## Tests

`tests/test_vaultlab_cli/test_demo.py` pins the contract:

- Bundled metadata + figures ship in the package
- Each bundled PNG is <200 KB
- `run_demo` writes a non-trivial `.pptx`
- `.provenance.json` + `.method.md` sidecars land next to the deck
- Synthetic-data unit-test runtime <30s (real user bar is <5 min end-to-end)
- Re-running into the same dir is idempotent
- A `socket.socket` sentinel confirms no network calls

## Sub-goal

Implements sub-goal 1.4 of the north-star plan; sub-goal 1.5 (scripted clean-VM onboarding test) builds on top.
