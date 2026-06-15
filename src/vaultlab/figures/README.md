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
- `palette_for(n)`, `bar_fill(labels, *, sign=…, palette=…)`, `PaletteRegistry`, `CB_PALETTE` (Paul Tol 9-color), `EXT_PALETTE` (24-color extension), `NEUTRAL_GREY`, `SIG_COLOR_UP/DOWN/NS` — colorblind-safe palettes with Rule-14 neutral-grey discipline (grey by default; opt into color only for sign, cross-panel tracking, or a secondary axis). `PaletteRegistry` keeps a named palette stable across every panel of a multi-figure study.
- `save_legend(...)`, `legend_position_for_density(x, y, ...)` — standalone legend export + pick the emptiest corner from data density.
- `setup_rcparams()`, `style_ax(ax, ...)` — apply the publication-tight rcParams (Arial, embeddable PDF/PS text) and bold/despined per-axis styling.
- `FIG_1COL`, `FIG_1p5COL`, `FIG_2COL`, `FIG_WIDE`, `FIG_TALL`, `FIG_HEATMAP`, `FIG_HEATMAP_WIDE`, `FIG_VOLCANO`, `FIG_UMAP`, `FIG_BARH`, `FIG_TRIPLE` — Nature-column figure-size presets, plus type-size constants (`TITLE_SIZE`, `LABEL_SIZE`, `TICK_SIZE`, `LEGEND_SIZE`, `ANNOT_SIZE`, `SMALL_SIZE`) and line/spine widths (`LINE_WIDTH`, `SPINE_WIDTH`).
- `coverage.py` / `stamp.py` — `parameter_stamp(base="cluster_umap", K=8, ...)` builds a parameter-stamped filename so re-runs with different K don't overwrite each other; `CoverageManifest` records what a figure includes/excludes for a `/figure-audit` footer (placeholder — minimal skeleton today, no JSON I/O yet). Neither is re-exported from the `publication` barrel.

**Understand — locate elements inside a figure (`vaultlab.figures.understand`)**
- `understand_figure(image_path, motifs, *, doi, describe_fn, match_fn, verify_fn, max_iterations=5, ...)` — orchestrate the four-step describe → localize → match → verify pipeline. The describe / match / verify legs are pluggable callbacks (Claude Code itself supplies them via `/understand-figure`); unsupplied legs are recorded as skipped, not fabricated, and the verify loop is bounded (default cap 5, stops early on `ACCEPT` / `GIVE_UP`).
- `ColorMotif`, `Region`, `extract_regions(...)` — the programmatic localizer: declarative HSV color motifs (hue range + min saturation/value/area) → connected-component pixel regions with bboxes and centroids.
- `merge_regions(..., dilation_px=8)` — collapse fragmented same-motif components into single boxes by inflating each region's bbox and merging any that overlap (the union bbox + summed area + area-weighted centroid).
- `render_debug_overlay(...)` — draw motif-colored, labeled bounding boxes onto the image (for tuning motif thresholds). `render.py` additionally ships the production renderers `render_annotated_figure` / `render_annotated_figure_v3` — numbered on-figure markers + right-gutter callouts, the shipping output of the pipeline (imported from `understand.render`, not re-exported on the barrel).
- The describe/match/verify task scaffolding — `DescribeFigureTask` / `MatchElementsTask` / `VerifyAnnotationTask`, `prepare_*_task(...)`, `render_*_from_response(...)`, `*_response_schema` — builds the prompt + JSON schema for each LLM leg and parses the response back. `understand._sdk.understand_figure_via_sdk(...)` (plus `describe_via_sdk` / `match_via_sdk` / `verify_via_sdk`) is the alternative API-key path that calls Anthropic directly with the figure as a vision block, no Claude Code session required.
- `ElementAnnotation`, `VerificationIteration`, `FigureUnderstandLog`, `save_understand_log(...)` — the per-figure reasoning trace (all four step outputs + per-iteration verify decisions) and its KB sidecar at `Sources/Figures/<doi-slug>/<fig-stem>.understand.md`.

**Panel + whitespace geometry (`vaultlab.figures.understand.whitespace`)**
- `detect_panels(image, *, max_depth=3)`, `is_single_plot(image)`, `classify_panel_layout(image)` — recursive XY-cut panel detection over a glyph-aware whitespace mask. A single-plot figure (one volcano / UMAP / bar chart) returns 1 panel; a 2×2 grid returns 4. `classify_panel_layout` distinguishes `single_plot` / `single_plot_with_inset` / `multi_panel`, with `has_corner_inset(image)` flagging an embedded inset axes the layout dispatch should describe but not subdivide. This is what backs `suggest_figure_layout`.
- `whitespace_mask(image)` + `find_marker_offset(image, bbox, ...)` — compute the strict white-background-AND-no-nearby-glyph mask and use it to place an annotation marker in real whitespace near an element (local 8-direction ring search, then a global largest-free-patch fallback) so labels don't land on top of text.

**Layout audit — pixel-level figure QC (`vaultlab.figures.understand.layout_checks`)**
- `run_layout_audit(figure_path, *, recipe_metadata=None) -> AuditResult` — run nine deterministic checks on a rendered figure file: title cutoff, axis-label cutoff, legend overlap, colorbar overlap, palette accessibility (ΔE in CIELAB via optional `colorspacious`), aspect-ratio match, DPI ≥ 300, empty/no-data panel, and recipe-conformance (XY-cut panel count vs the recipe's declared count). Returns severity-ranked `AuditCheck`s (`pass` / `warn` / `fail`) aggregated into an `AuditResult.to_json_dict()` ready to fold into a figure's provenance receipt. Legend/colorbar overlap are honest about being heuristic-only post-save.

**Report — figures bundled into a review doc (`vaultlab.figures.report`)**
- `render_report(*, entries, output_path, title, ...)` — write one Obsidian-friendly markdown report bundling figures with captions, results paragraphs, and notes.
- `FigureEntry`, `RenderResult` — one (figure, caption, results) bundle and the render outcome (paths + entry count + an `open_command` string the caller prints so the user opens the report in Obsidian; there is no separate open helper — the command travels on `RenderResult`).

**Index + corpus — cross-figure provenance (`vaultlab.figures.index`, `vaultlab.figures.corpus`)**
- `update_figure_index(...)`, `find_figure_pairs(...)`, `load_figure_index(...)` — a per-project `figure-index.json` that answers "this figure pairs with…" via a dominant-color pixel signature plus same-recipe bonus.
- `build_sources_index()`, `load_sources_index()`, `save_sources_index()` — derive `sources.json` from each recipe's `ANCHOR_PAPERS` so the anchor set is queryable data and guarded against drift.

## How it fits

**Reads from:** your tidy analysis tables (recipe `render` inputs); a built `Corpus` from `vaultlab.research` plus its API-key config (acquisition); rendered figure images on disk (understand, panel/whitespace geometry, layout audit, index, `suggest_figure_layout`).

**Writes to:** figure files on disk (PNG/PDF, or the SVG+PDF+TIFF triple under a contract), with provenance sidecars attached separately by the producing caller; per-paper figure caches under a `cache_dir`; annotated/debug overlay PNGs; the project KB (figure reports, understand-log sidecars under `Sources/Figures/<doi-slug>/`, the project `figure-index.json`).

**Consumed by:** `vaultlab.slides` (places constructed/acquired figures, calls `suggest_figure_layout`); the run-analysis pipeline (renders recipe figures from result tables under the contract, then audits + receipts them); figure-understanding and journal-club flows. **Driven by slash commands:** `/figure-contract` (contract authoring), `/understand-figure` (the 4-step pipeline, with Claude Code itself as the LLM legs), and the publication-guideline / figure-audit checks (`run_layout_audit`). In the pipeline it sits after analysis produces tidy results and before slide/manuscript assembly.

## What it does NOT do

- It does **not** run upstream analysis — recipes consume tidy result tables; they do not cluster, do differential expression, or process raw data.
- It does **not** mine figures out of PDFs. Acquisition uses publisher APIs only; anything no API can supply comes back `source="unavailable"`, never scraped from a PDF.
- It does **not** invent recipe layouts or skip the contract — every recipe cites ≥3 published anchor papers, and plotting is meant to run only after a `FigureContract` is authored and validated.
- It does **not** break paywalls or log into your institution — the Elsevier tier only fires when an institutional `elsevier_key` is configured, and the Springer OA tier is probe-only (the live API does not advertise figure URLs).
- The layout audit and understanding pipeline work on the **rendered image file**, not a live matplotlib `Figure` — so legend/colorbar-overlap checks are honest heuristics (false negatives possible), and the LLM legs of `understand_figure` (describe/match/verify) only run when the caller wires real callbacks; with none supplied the pipeline still localizes programmatically and records the rest as skipped.

## Files

- `acquisition.py` — the API figure-acquisition waterfall (PMC OA tar / Elsevier / Springer); `Figure`, `FigureAcquisitionResult`, caching + manifests.
- `contract.py` — `FigureContract`, archetypes, `validate_contract`, `apply_rcparams`, `triple_export`, `suggest_figure_layout` (the single-plot-vs-multi-panel layout dispatch), the publication palette (`NMI_PASTEL` + reserved directional colors) and `RC_PARAMS`.
- `recipes/` — eleven flat `<recipe>.py` + `<recipe>.md` pairs, each a `render()` + `RECIPE_VERSION` + `ANCHOR_PAPERS`; registered in `recipes/__init__.py`.
- `publication/` — low-level helpers: `style.py` (rcParams + size presets + `style_ax`), `color.py` (palettes + Rule-14 grey), `legend.py`, `save.py` (`save_fig` + `save_with_optional_contract`), `coverage.py` (`CoverageManifest`), `stamp.py` (`parameter_stamp`) — each with a sibling `.md`.
- `understand/` — color-motif localization + the four-step understanding pipeline + figure QC; `color_motif.py`, `merge.py`, `render.py`, `models.py`, `_tasks.py`, `_sdk.py` (API-key path), `whitespace.py` (XY-cut panel detection + whitespace/marker placement), `layout_checks.py` (`run_layout_audit`'s 9 pixel checks).
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
