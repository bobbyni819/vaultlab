# vaultlab.slides

Turns a research topic, a literature run, or a hand-authored plan into a finished, presentation-ready `.pptx` — with placed figures, tiered speaker notes, and a deterministic quality audit.

Plain-language companion: the **Slide decks** section of `G:/My Drive/Knowledge/vaultlab/Wiki/Concepts/vaultlab-subsystems.md`. Architectural context: the `vaultlab.slides` entry in [`docs/architecture.md`](../../../docs/architecture.md).

## What it is

This is vaultlab's deck-building engine — the flagship presentation subsystem. You give it a structured "deck plan" (or a `/lit-arc` result), and it composes a PowerPoint file the way a careful presenter would: a title slide, section intros, figure slides with the figure placed next to the claim it supports, bullet slides with Vancouver-style citation footers, and a references page that lists only the papers actually cited in the deck. It then reads the rendered file back and audits it — font sizes, overlapping shapes, descriptive titles, bullet density, color contrast, speaker-notes structure, story arc, even an estimated speaking time. That core audit and the time-budget estimate run with no LLM call, so they can run on every render and gate CI (there is a `vaultlab slides review` CLI that exits non-zero on a critical finding); one optional add-on (anticipating audience questions) can be pointed at an LLM when you ask for it.

It exists because building a good research deck is mostly disciplined assembly, not creativity: a known set of slide layouts, a lab-branded template, projector-readable type sizes, and figures lifted from the open-access versions of cited papers. The workflows in `vaultlab.workflows` (and the `/build-deck`, `/journal-club`, `/review-deck` slash commands) drive this package; it is the thing those higher layers call to actually write the `.pptx`.

Two builder paths coexist, sharing one renderer and one audit pass:

- **Typed-DeckPlan path** — strongly-typed `DeckPlan` / `DeckSlide` dataclasses fed to `build_deck`. This is the path `/lit-arc` decks take via `build_deck_from_lineage_result`.
- **Dict-plan path** — a flexible dict plan (twelve slide types) fed to `build_from_plan`, rendered with the richly-styled imperative lab-template layouts. This is the path an LLM-authored or hand-authored plan takes when you want the full Hickey-lab look; it can optionally apply click-build animations, mirror itself to editable Marp markdown, and log the run into a KB.

On top of those, the package ships ready-made deck recipes (investor pitch, lab meeting, conference talk, journal club) and a set of paper-type journal-club narrative arcs, so a caller can emit a sensibly-ordered plan without hand-authoring the slide sequence. It also renders a browser-openable HTML preview of a deck plan for review on a phone, and a slide-by-slide diff between two rendered decks.

## Public surface

Composers (turn a plan into a `.pptx`):

- `build_deck` — compose a multi-slide `.pptx` from a typed `DeckPlan`; dispatches each slide to a text or annotated-figure renderer and themes from the Hickey-lab template. The five composer kinds are `title` / `section_intro` / `figure` / `bullets` / `references`, with bullet slides carrying a Vancouver-style `[N] Author Year` citation footer.
- `build_from_plan` — render a flexible **dict** deck-plan (twelve slide types: title / section_divider / figure / two_figure / multi_figure / quote / text / references / equation / table / comparison_table / acknowledgments_grid) to `.pptx`. Levers: `template="lab"`/`"plain"` (Hickey-lab template vs. plain black/white deck), `theme="dark"`/`"light"`, `write_marp` (also emit an editable Marp `.md` mirror — default on), `with_animations` (auto-apply bullet-reveal + panel-build-up click animations), and `kb_log` (a `KBReader` — appends a `_Log.md` entry and writes a deck-plan report into `<kb>/Output/Reports/`). Returns a dict of the written paths (`pptx`, optional `marp`, optional `report`). Bullets may carry embedded per-click annotations, which the builder normalizes into slide-level annotations automatically.
- `build_deck_from_lineage_result` — take a `/lit-arc` `LineageRunResult` and synthesize a ~7-slide journal-club deck. Three modes: a mechanical fast path (reads on-disk summary frontmatter, buckets papers by year into Background / Development / Synthesis, allocates a capped figure budget across buckets with Tier-A-only figure picking and cross-paper figure substitution), an LLM `plan_callback` path, or an adversarial-crosstalk path. Optionally runs a final `rigor_audit` gate before shipping and writes provenance receipts alongside the `.pptx`.
- `render_pptx` — the low-level renderer: turn a simple `Deck` of `Slide`s into a `.pptx`. The **only** module that talks to `python-pptx` in the typed path. Stashes deck metadata into the file's document properties and writes provenance receipts.
- `RenderError` — raised when rendering fails (python-pptx missing, figure not found, etc.).

Typed deck data model:

- `Slide` — one layout-agnostic slide (`title` / `content_with_bullets` / `figure_with_caption`); validates its layout on construction. Carries optional speaker notes.
- `Deck` — an ordered list of `Slide`s plus title, theme, working dir, and free-form provenance metadata. `.add(slide)` appends; `len(deck)` returns the slide count.
- `DeckSlide` — one slide spec for the multi-slide composer; a `kind` (`title` / `section_intro` / `figure` / `bullets` / `references`) plus a permissive per-kind `content` dict.
- `DeckPlan` — the full deck structure (title, speaker, sections, slides, theme) consumed by `build_deck`.

Self-review + audits (deterministic by default; one optional LLM add-on):

- `review_deck` — run the composite self-review over a rendered `.pptx`. The core checks are deterministic and LLM-free, and run per-slide: layout hard rules (Roboto font, heading ≥ 28 / body ≥ 24 / caption ≥ 18 pt floors — sub-18 pt is critical, with citation-footer text exempted; no shape overlap), descriptive titles (≥ 3 words on body slides), bullet density (≤ 7 lines), figure presence (caption mentions a figure but no image embedded), WCAG color-contrast (flags low foreground/background ratios — conservatively, only on concrete RGB; critical below 3.0:1, warning below 4.5:1), and the two-tier speaker-notes structure (empty notes on a body slide is critical; missing mental-map heading or a too-thin/too-long script is a warning). On the deck level it runs a story-arc audit (title slide first, references/acknowledgments last, ≤ 5 section dividers, non-empty deck). Pass `budget_minutes` to fold in the (still LLM-free) time-budget audit. Pass `anticipate_questions=True` to also run the Q&A anticipator; that step stays heuristic unless you *also* hand it a `qa_runner_callback`, in which case the deck's text is sent to that LLM (with heuristic fallback on failure). Nothing is raised on findings — callers read `report.n_critical` / `report.ok()`.
- `ReviewReport` / `SlideReview` — the report record and per-slide finding it returns; `ReviewReport` also carries the optional `time_budget` and `anticipated_questions` outputs.
- `write_review_report` — render a `ReviewReport` to a critical-first HTML file (and drop its provenance receipt).
- `audit_time_budget` — estimate per-slide and total speaking time and flag a deck that won't fit a target budget. Deterministic, no LLM.
- `TimeBudgetReport` / `SlideTimeEstimate` — the time-audit report and per-slide estimate.
- `anticipate_qa` — surface a ranked list of likely audience questions. Heuristic (LLM-free) by default; pass a `runner_callback` to bundle the deck text into one LLM call (falling back to the heuristic floor if the call fails or returns nothing parseable).
- `AnticipatedQuestion` — one anticipated question record.
- `diff_decks` — slide-by-slide diff between two `.pptx` files (title-stable, then body-fingerprint, then position matching).
- `DeckDiff` / `SlideDiff` — the diff report and per-slide change record.

Imperative layout primitives (add one styled slide to an open presentation):

- `add_title_slide`, `add_section_divider`, `add_text_slide`, `add_references_slide`.
- `add_figure_slide`, `add_figure_only_slide`, `add_figure_above_bullets_slide`, `add_two_figure_compare_slide`, `add_multi_figure_slide`, `add_quote_slide`.

Deck recipes + narrative arcs (module-level helpers, not exported from the barrel):

- `vaultlab.slides.templates` — four `build_*` recipes that return a `build_from_plan`-ready dict: `build_investor_pitch`, `build_lab_meeting`, `build_conference_talk`, `build_journal_club`. Each fills the right slide sequence for that audience while honoring the hard rules.
- `vaultlab.slides.journal_club_arcs` — `JOURNAL_CLUB_ARCS` registry of seven paper-type narrative skeletons (discovery / methods / dataset / clinical / materials / review / generic), `classify_paper_type` (heuristic classifier from title / abstract / journal), `get_arc` (English or simplified-Chinese titles), and `arc_to_slide_plan` (arc → plan dict). The arc fixes slide *order and role*; content is filled by the plan generator.

Browser preview + audit HTML (module-level helpers):

- `vaultlab.slides.preview_html.build_deck_preview_html` / `write_deck_preview` — render a deck-plan dict as a single-file, arrow-key-navigable HTML slideshow with figures inlined as base64 (works offline / on a phone).
- `vaultlab.slides.audit_html.build_audit_report_html` — render a deck plan + `rigor_audit` result as an interactive per-slide HTML report (the same look-and-feel the self-review HTML reuses).

Speaker notes (dual-format: a mental map for fluent presenters + a word-for-word script):

- `dual_format` — build a notes string from a mental-map dict (`hook` / `key_claim` / `evidence` / `key_terms` / `click` / `transition`) + a detailed script, joined by a `--- DETAILED SCRIPT ---` divider.
- `format_speaker_notes` / `parse_speaker_notes` — render / re-parse the notes format (the older `bobby_slides` mental-map-only surface; `format_speaker_notes` also routes an optional `script` key through the divider).
- `parse_dual_format` — split a dual-format string back into its mental-map dict + script (inverse of `dual_format`). (In `notes.py`; not on the `vaultlab.slides` barrel — `from vaultlab.slides.notes import parse_dual_format`.)
- `required_mental_map_keys` — the ordered mental-map key contract, for LLMs generating notes. (Also `notes.py`-only, not barrel-exported.)
- `attach_to_slide` — attach a notes dict to a slide's notes panel.

Animations (OOXML click builds — python-pptx has no native support):

- `appear_on_click`, `fade_on_click`, `bullet_reveal`, `panel_buildup`, `appear_together_on_click`.

Annotations, Marp, template + theme, KB I/O:

- `add_annotations` — overlay annotation callouts on a figure slide.
- `deck_plan_to_marp` / `write_marp` — mirror a dict deck-plan to editable Marp markdown.
- `load_template`, `load_plain_presentation`, `lab_template_path` — start a presentation from the bundled Hickey-lab template or a plain 16:9 deck.
- `theme_colors`, `theme_colors_hex`, `default_font`, `min_sizes` — the Hickey-lab palette, default font (`Roboto`), and projector-readable minimum sizes (heading 28 / body 24 / caption 18 pt).
- `KBReader` — pure file I/O over the standard KB layout (read concepts, summaries, articles, assets).
- `KBNotFoundError` — raised when a KB root or expected subdirectory is missing.

## How it fits

**Reads from:** a `DeckPlan` / dict plan (usually authored by `vaultlab.workflows.deck_plan`), a `LineageRunResult` from a `/lit-arc` run, per-paper summary frontmatter in `<kb>/Wiki/Summaries/`, figure images (figure assignments from open-access paper packages or `vaultlab.figures`), and the bundled Hickey-lab template under `themes/_assets/`. KB paths are resolved via `vaultlab.kb.paths` and `vaultlab.context.locations`.

**Writes to:** a `.pptx` routed through `vaultlab.kb.paths.deck_path` into `<kb_root>/Output/<project>/<topic>-deck.pptx`, plus per-output provenance receipts (`.provenance.json` + `.method.md`) via `vaultlab.provenance`. The optional self-review HTML and Marp mirror land beside it.

**Consumed by:** the deck-building workflows; the `/build-deck`, `/journal-club`, `/preview-deck`, `/review-deck`, and `/reorder-slides` slash commands (plus the `/build-slides` and `/slide-review` skills); and the `vaultlab slides review <pptx> [--html <out>]` CLI subcommand (prints the self-review summary, optionally writes the HTML report, and exits `2` when a critical issue is found — usable as a CI gate). Where it sits in the pipeline: literature run → figure assignment → **deck composition (here)** → self-review → the rendered deck the user opens.

## What it does NOT do

- It does **not** search literature, read papers, or generate figures — it consumes summaries and figure images that upstream subsystems (`vaultlab.research`, `vaultlab.figures`) already produced.
- Its self-review core — the `review_deck` layout/title/density/figure-presence/color-contrast/speaker-notes/story-arc checks, `audit_time_budget`, and the default heuristic `anticipate_qa` mode — is **deterministic and LLM-free**: it checks the rendered file mechanically and does not judge whether the science is correct. The **only** path that reaches an LLM is opt-in: `anticipate_qa` (or `review_deck(..., anticipate_questions=True, qa_runner_callback=...)`) when you explicitly supply a runner callback.
- It does **not** rasterize LaTeX / TeX — the `equation` slide renders the equation as large plain text; callers needing pixel-perfect math should render their own image and use `add_figure_only_slide`.
- It does **not** render to PDF or images itself, and `render_pptx` does **not** verify a figure looks good — that visual judgment is a separate step (the `/slide-review` primitive views the rendered pixels).
- It does **not** invent content on the fast path — `build_deck_from_lineage_result` with no callback composes mechanically from on-disk summaries; richer plans require an explicit LLM `plan_callback` or crosstalk runner.

## Files

- `deck.py` — the typed `Slide` / `Deck` / `DeckSlide` / `DeckPlan` data model, the `build_deck` composer, `build_deck_from_lineage_result`, and the dict-plan `build_from_plan` renderer.
- `render.py` — the low-level `render_pptx` renderer; the only typed-path module that depends on `python-pptx`.
- `self_review.py` — the composite `review_deck` audit + `ReviewReport` and its HTML rendering.
- `time_budget.py` — `audit_time_budget` speaking-time estimator.
- `qa_anticipator.py` — `anticipate_qa` likely-audience-question surfacer.
- `version_diff.py` — `diff_decks` slide-by-slide deck comparison.
- `template.py` — Hickey-lab + plain-theme presentation loaders, palette, fonts, min sizes.
- `themes/` — theme definitions (`default`, `hickey_lab`) and the bundled `_assets/` template.
- `layouts/` — the declarative `LayoutSpec` registry (`title` / `content_with_bullets` / `figure_with_caption`) plus the imperative lab-template slide primitives (title, section divider, text, references, figure family, multi-figure, quote, equation, table, comparison table, acknowledgments grid).
- `notes.py` — dual-format speaker-notes builder/parser.
- `animations.py` — OOXML click-animation engine (appear / fade / bullet-reveal / panel-build-up).
- `annotate/` — figure-annotation overlay primitives (`add_annotations`); the spec-*generating* figure-understanding pipeline lives in `vaultlab.figures.understand`, not here.
- `annotated_figure_slide.py` — the annotated-figure-slide builder the composer delegates to (each annotation becomes a native, animatable PowerPoint shape, not a baked-in pixel).
- `marp.py` — dict deck-plan → Marp markdown mirror.
- `kb_reader.py` — `KBReader` file I/O over the KB layout (+ `_Log.md` append / report write).
- `preview_html.py` / `audit_html.py` — browser-openable deck preview + audit-report HTML.
- `journal_club_arcs.py` — seven paper-type narrative arcs (EN + zh-CN) + paper-type classifier.
- `templates/` — full deck recipes per audience (journal club, lab meeting, conference talk, investor pitch).
- `understand/` — placeholder package (no behaviour yet).

## See also

- `src/vaultlab/figures/README.md` — where the figures placed on figure slides come from.
- `src/vaultlab/research/README.md` — the literature pipeline that produces the `LineageRunResult` and summaries decks are built from.
- `src/vaultlab/workflows/` — `deck_plan` (plan generation) and `crosstalk` (adversarial planning + rigor audit) that drive this package.
- `src/vaultlab/provenance/` — the receipt format every rendered deck writes.
- `.claude/commands/build-deck.md`, `journal-club.md`, `review-deck.md`, `preview-deck.md`, `reorder-slides.md` — the user-facing slash commands (plus the `/build-slides` and `/slide-review` skills).
- `src/vaultlab/cli/` — the `vaultlab slides review` CLI subcommand wired to `review_deck`.
- `docs/architecture.md` — the `vaultlab.slides` architectural sketch.
