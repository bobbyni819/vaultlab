---
name: figure-contract
description: Establish a figure contract BEFORE writing plotting code. Forces the 5 commitments (conclusion, evidence chain, archetype, backend, export contract) and validates them. Plotting begins only after the contract is authored and audited.
arguments: <conclusion> [--archetype quantitative_grid|schematic_led_composite|image_plate_and_quant|asymmetric_mixed_modality] [--width-mm 89|183|custom] [--backend python|r] [--out <path>]
---

# /figure-contract "<conclusion>"

> *"The first move is the contract, not the plot."*

Drives `vaultlab.figures.contract`. Before any matplotlib / ggplot2 call,
the contract forces the 5 commitments that audit time will check:

1. **Core conclusion** — one-sentence claim the figure must defend.
2. **Evidence chain** — per-panel: what unique evidence does this panel carry? Panels that don't pull their weight are dropped.
3. **Archetype** — `quantitative_grid` / `schematic_led_composite` / `image_plate_and_quant` / `asymmetric_mixed_modality`.
4. **Backend** — `python` (matplotlib/seaborn) or `r` (ggplot2/patchwork). Once selected: no cross-rendering.
5. **Export contract** — SVG + PDF + 600 DPI TIFF by default. Width capped at 183mm (Nature double-column).

Failing the contract is a rigor-audit issue, not a stylistic preference.
Soft warnings (>183mm, <300 DPI TIFF, missing image_integrity_notes for
image plate) come back as advisory.

## Pre-flight

1. Resolve `<conclusion>` — must be a non-empty one-sentence statement
2. Resolve `--archetype` (default `quantitative_grid`)
3. Resolve `--width-mm` (default `183`; Nature single column = 89mm)
4. Resolve `--backend` (default `python`)
5. Resolve `--out` (default current dir, name based on conclusion-slug)

## Execution

### Step 1 — Interview Bobby for the evidence chain

Walk through the planned panels one at a time. For each panel, ask:

> "What unique piece of evidence does this panel carry? If two panels
>  would answer the same scientific question, one must be cut."

Collect the panel → evidence mapping. Aim for 3-6 panels for a main
figure; 1-2 for a supplementary.

### Step 2 — Construct + validate

```python
from vaultlab.figures.contract import (
    FigureContract, FigureArchetype, validate_contract,
)

contract = FigureContract(
    conclusion="<conclusion>",
    evidence_chain={
        "a": "<evidence-a>",
        "b": "<evidence-b>",
        # ...
    },
    archetype=FigureArchetype["<archetype>".upper()],
    backend="<backend>",
    width_mm=<width_mm>,
    height_mm=<inferred_or_passed>,
)
warnings = validate_contract(contract)
```

- Hard failures raise `ContractViolation` — fix before proceeding.
- Soft warnings are advisory — report them, let Bobby decide.

### Step 3 — Write the contract to disk

Persist the contract as YAML at the chosen `--out` path. Future
plotting code reads from this YAML; rigor_audit will diff actual
exported figures against the contract.

```yaml
# fig2-spatial-tx-recovery.contract.yaml
conclusion: Method X recovers ground-truth cell types in 5/6 tissues.
evidence_chain:
  a: UMAP of 60k cells coloured by ground truth
  b: UMAP coloured by method X cluster id
  c: ARI vs ground truth across tissues, bar plot
  d: Per-cell-type sensitivity in worst-performing tissue
archetype: quantitative_grid
backend: python
width_mm: 183
height_mm: 120
export_formats: [svg, pdf, tiff]
dpi: 600
stats_block: ARI on held-out 20%; n=5000 per tissue
color_policy: NMI_PASTEL; reserved green for gains, red for drops
```

### Step 4 — Generate the scaffold script (optional)

If Bobby wants, emit a starter Python script with the rcParams already
applied + the panel skeleton:

```python
from vaultlab.figures.contract import apply_rcparams, triple_export
import matplotlib.pyplot as plt

apply_rcparams()
fig, axs = plt.subplots(2, 2, figsize=(7.2, 4.7))

# Panel a — UMAP of 60k cells coloured by ground truth
ax = axs[0, 0]
# TODO: implement panel a
ax.text(0.5, 0.5, "panel a", ha="center", va="center")

# Panel b — UMAP coloured by method X cluster id
ax = axs[0, 1]
# TODO: implement panel b
# ... etc

triple_export(fig, "<out-stem>", contract=contract)
```

## Output package

- `<stem>.contract.yaml` — the persisted contract
- `<stem>.scaffold.py` — Python starter (when `--scaffold` flag given)
- `<stem>.audit.md` — soft-warning + validation report

## Rules of engagement

- **Author the contract BEFORE the plot.** This is the whole point.
  Don't reverse-engineer a contract from existing plotting code.
- **Stricter archetype = stricter discipline.** Asymmetric mixed-modality
  is only justified if one panel genuinely dominates the visual weight.
  Quantitative grid is the safer default.
- **One language only.** Python OR R — never both for the same figure.
- **No fake stats blocks.** Leave `stats_block` empty if you don't yet
  have n / test choice / multiple-testing correction; don't fabricate.

## Related

- `vaultlab.figures.contract` — underlying primitive
- `vaultlab.figures.recipes` — 11 chart recipes that implement these rules
- `vaultlab.figures.publication` — color / legend / save helpers
- nature-figure skill at `nature-skills/skills/nature-figure/` — upstream
