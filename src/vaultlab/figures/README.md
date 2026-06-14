# vaultlab.figures

Builds publication-tight figures **from your own analysis tables** — and, separately, pulls native-resolution figures *out of* published papers via APIs.

Plain-language companion: the "Figures from data" section of `vaultlab-subsystems.md` (KB). Architectural sketch: `docs/architecture.md` → `vaultlab.figures`.

## What it is

This is the package that turns a tidy result table into a figure a reviewer would accept, and that retrieves figure images from the literature when a downstream task (a deck, a journal-club reading, figure understanding) needs the real published picture. The construction side is disciplined on purpose: before any plotting code runs you commit to a **figure contract** — the one-sentence claim the figure exists to defend, the per-panel evidence chain, the archetype, the export targets — so a panel that carries no unique evidence or a figure that overclaims is a reviewable rigor issue, not a style nitpick. Chart layouts come from a **recipe library** copied from real published figures (each recipe cites its anchor papers), not from "Claude guessed it would look good." The acquisition side is deliberately separate: it fetches figures through legal publisher APIs only and never mines images out of PDFs.

It is consumed by the slide builder (figures placed on slides), the analysis pipeline (figures rendered from result tables), the figure-understanding pipeline, and any orchestrator that needs a paper's actual figures.

## Public surface

The slim barrel (`vaultlab.figures`) re-exports only the acquisition layer; the rest is imported from named submodules.

**Acquisition — figures *out of* papers (`vaultlab.figures` / `vaultlab.figures.acquisition`)**
- `acquire_figures(doi, *, cache_dir, ...)` — fetch one paper's figures via the API waterfall (PMC OA tar → Elsevier ScienceDirect → Springer OA); returns `source="unavailable"` instead of raising when no route yields figures.
- `acquire_figures_for_corpus(corpus, cache_dir, ...)` — run the same waterfall across every DOI in a `Corpus`, with a thread pool and progress callback.
- `Figure` — one extracted figure: `figure_id`, `file_path`, `caption`, `label`, detected `panels`.
- `FigureAcquisitionResult` — the outcome of one acquisition: `doi`, `figures`, which `source` tier succeeded (`"pmc-tar" | "elsevier-api" | "springer-api" | "cache" | "unavailable"`), and an `error` string when unavailable.
- `figure_cache_dir(doi, cache_dir)` — the per-paper cache subfolder for a DOI.

**Contract — the discipline before plotting (`vaultlab.figures.contract`)**
- `FigureContract` — the dataclass of commitments (conclusion, evidence chain, archetype, backend, journal-targeting dimensions, export formats, stats/image-integrity notes).
- `FigureArchetype` — the four nature-figure archetypes (quantitative grid, schematic-led composite, image-plate-and-quant, asymmetric mixed-modality).
- `validate_contract(contract)` — raise `ContractViolation` for hard failures (empty conclusion, no panels); return advisory warnings for soft ones.
- `triple_export(fig, stem, ...)` — save a matplotlib figure to SVG + PDF + 600 DPI TIFF (editable-text vector + raster).
- `apply_rcparams(...)` — apply the mandatory publication matplotlib rcParams in place.
- `suggest_figure_layout(image_path, ...)` — pick a slide-layout name for a figure image (single-plot vs multi-panel), routing into `vaultlab.slides.layouts`.
- `NMI_PASTEL`, `SIGNAL_GAIN`, `SIGNAL_LOSS`, `RC_PARAMS` — the low-saturation palette + reserved directional colors + the rcParams dict.

**Recipes — the chart library (`vaultlab.figures.recipes`)**
- Eleven figure archetypes, each a module exposing `render(...) -> Path` plus `RECIPE_VERSION` and an `ANCHOR_PAPERS` tuple: `marker_dot_plot`, `umap_overlay`, `heatmap`, `stat_test_panel`, `multi_panel_composite`, `spatial_map_overlay`, `pseudobulk_volcano`, `stacked_bar`, `cci_heatmap`, `spatial_neighborhood`, `metabolite_pathway_map`. Each `render` saves the image (via `save_with_optional_contract`) and returns its path; it does **not** itself write a provenance receipt — that's the producing caller's job (see `save_fig` below).

**Publication helpers — low-level building blocks (`vaultlab.figures.publication`)**
- `setup_rcparams()`, `style_ax(...)` — publication-tight rcParams + per-axis styling.
- `save_fig(...)` — multi-format save (PNG + PDF by default) returning the written paths. It deliberately does **not** write a provenance sidecar: per AGENTS.md Red Line #2, a pipeline that produces an audited figure follows its `save_fig` with `vaultlab.provenance.write_receipts(path, record)` to attach the `.provenance.json` + `.method.md` receipt (e.g. `vaultlab.analysis.run_pipeline` does this for every figure it emits). The low-level recipes only save the image. (`save.py` also defines `save_with_optional_contract` — the contract-aware wrapper that triple-exports SVG+PDF+TIFF when a `FigureContract` is passed — but that helper is not re-exported from the `publication` barrel.)
- `palette_for(...)`, `bar_fill(...)`, `PaletteRegistry`, `CB_PALETTE`, `NEUTRAL_GREY`, `SIG_COLOR_UP/DOWN/NS` — colorblind-safe palettes with Rule-14 neutral-grey discipline.
- `save_legend(...)`, `legend_position_for_density(...)` — standalone legend export + density-aware placement.
- `FIG_1COL`, `FIG_2COL`, `FIG_VOLCANO`, `FIG_UMAP`, `FIG_HEATMAP`, … — figure-size presets, plus type-size constants (`LABEL_SIZE`, `TICK_SIZE`, …).

**Understand — locate elements inside a figure (`vaultlab.figures.understand`)**
- `understand_figure(image_path, motifs, *, doi, ...)` — orchestrate the four-step describe → localize → match → verify pipeline (LLM steps are pluggable; unsupplied steps are recorded as skipped, not fabricated).
- `ColorMotif`, `Region`, `extract_regions(...)`, `merge_regions(...)` — the programmatic localizer (HSV color motifs → merged pixel regions).
- `render_debug_overlay(...)` — draw labeled bounding boxes onto the image.
- `ElementAnnotation`, `VerificationIteration`, `FigureUnderstandLog`, `save_understand_log(...)` — the per-figure reasoning trace and its KB sidecar.

**Report — figures bundled into a review doc (`vaultlab.figures.report`)**
- `render_report(*, entries, output_path, title, ...)` — write one Obsidian-friendly markdown report bundling figures with captions, results paragraphs, and notes.
- `FigureEntry`, `RenderResult` — one (figure, caption, results) bundle and the render outcome (paths + entry count + an `open_command` string the caller prints so the user opens the report in Obsidian; there is no separate open helper — the command travels on `RenderResult`).

**Index + corpus — cross-figure provenance (`vaultlab.figures.index`, `vaultlab.figures.corpus`)**
- `update_figure_index(...)`, `find_figure_pairs(...)`, `load_figure_index(...)` — a per-project `figure-index.json` that answers "this figure pairs with…" via a dominant-color pixel signature plus same-recipe bonus.
- `build_sources_index()`, `load_sources_index()`, `save_sources_index()` — derive `sources.json` from each recipe's `ANCHOR_PAPERS` so the anchor set is queryable data and guarded against drift.

## How it fits

**Reads from:** your tidy analysis tables (recipe `render` inputs); a built `Corpus` from `vaultlab.research` plus its API-key config (acquisition); rendered figure images on disk (understand, index, `suggest_figure_layout`).

**Writes to:** figure files on disk with provenance sidecars; per-paper figure caches under a `cache_dir`; the project KB (figure reports, understand-log sidecars under `Sources/Figures/<doi-slug>/`, the project `figure-index.json`).

**Consumed by:** `vaultlab.slides` (places constructed/acquired figures, calls `suggest_figure_layout`); the run-analysis pipeline (renders recipe figures from result tables under the contract); figure-understanding and journal-club flows. In the pipeline it sits after analysis produces tidy results and before slide/manuscript assembly.

## What it does NOT do

- It does **not** run upstream analysis — recipes consume tidy result tables; they do not cluster, do differential expression, or process raw data.
- It does **not** mine figures out of PDFs. Acquisition uses publisher APIs only; anything no API can supply comes back `source="unavailable"`, never scraped from a PDF.
- It does **not** invent recipe layouts or skip the contract — every recipe cites ≥3 published anchor papers, and plotting is meant to run only after a `FigureContract` is authored and validated.
- It does **not** break paywalls or log into your institution — the Elsevier tier only fires when an institutional `elsevier_key` is configured, and the Springer OA tier is probe-only (the live API does not advertise figure URLs).

## Files

- `acquisition.py` — the API figure-acquisition waterfall (PMC OA tar / Elsevier / Springer); `Figure`, `FigureAcquisitionResult`, caching + manifests.
- `contract.py` — `FigureContract`, archetypes, `validate_contract`, `triple_export`, `suggest_figure_layout`, the publication palette/rcParams.
- `recipes/` — eleven flat `<recipe>.py` + `<recipe>.md` pairs, each a `render()` + anchor papers; registered in `recipes/__init__.py`.
- `publication/` — low-level helpers: `style.py`, `color.py`, `legend.py`, `save.py`, `coverage.py`, `stamp.py` (each with a sibling `.md`).
- `understand/` — color-motif localization + the four-step understanding pipeline; `color_motif.py`, `merge.py`, `render.py`, `models.py`, `_tasks.py`.
- `report.py` — figure-in-markdown review report generator.
- `index.py` — `figure-index.json` cross-figure pairing via pixel signatures.
- `corpus/` — derives `sources.json` (recipe anchor papers) and guards it against drift.
- `contract.md` — the figure-contract spec and rationale.

## See also

- `src/vaultlab/research/` — corpus building + paper acquisition (the acquisition layer consumes a `Corpus` from here).
- `src/vaultlab/slides/` — the deck builder that places these figures and calls `suggest_figure_layout`.
- `src/vaultlab/analysis/` — the result-analysis pipeline that renders recipe figures under the contract.
- `src/vaultlab/figures/recipes/<recipe>.md` — per-recipe layout spec, variants, and anchor papers.
- `docs/architecture.md` (`vaultlab.figures` section) and `AGENTS.md` (figure invariants, Rule 14 color discipline).
