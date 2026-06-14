# vaultlab.slides

Turns a research topic, a literature run, or a hand-authored plan into a finished, presentation-ready `.pptx` — with placed figures, tiered speaker notes, and a deterministic quality audit.

Plain-language companion: the **Slide decks** section of `G:/My Drive/Knowledge/vaultlab/Wiki/Concepts/vaultlab-subsystems.md`. Architectural context: the `vaultlab.slides` entry in [`docs/architecture.md`](../../../docs/architecture.md).

## What it is

This is vaultlab's deck-building engine — the flagship presentation subsystem. You give it a structured "deck plan" (or a `/lit-arc` result), and it composes a PowerPoint file the way a careful presenter would: a title slide, section intros, figure slides with the figure placed next to the claim it supports, bullet slides with Vancouver-style citation footers, and a references page that lists only the papers actually cited in the deck. It then reads the rendered file back and audits it — font sizes, overlapping shapes, descriptive titles, bullet density, story arc, even an estimated speaking time. That core audit and the time-budget estimate run with no LLM call, so they can run on every render and gate CI; one optional add-on (anticipating audience questions) can be pointed at an LLM when you ask for it.

It exists because building a good research deck is mostly disciplined assembly, not creativity: a known set of slide layouts, a lab-branded template, projector-readable type sizes, and figures lifted from the open-access versions of cited papers. The workflows in `vaultlab.workflows` (and the `/build-deck`, `/journal-club`, `/review-deck` slash commands) drive this package; it is the thing those higher layers call to actually write the `.pptx`.

Two builder paths coexist, sharing one renderer and one audit pass:

- **Typed-DeckPlan path** — strongly-typed `DeckPlan` / `DeckSlide` dataclasses fed to `build_deck`. This is the path `/lit-arc` decks take via `build_deck_from_lineage_result`.
- **Dict-plan path** — a flexible dict plan (eight slide types) fed to `build_from_plan`, rendered with the richly-styled imperative lab-template layouts. This is the path an LLM-authored or hand-authored plan takes when you want the full Hickey-lab look.

## Public surface

Composers (turn a plan into a `.pptx`):

- `build_deck` — compose a multi-slide `.pptx` from a typed `DeckPlan`; dispatches each slide to a text or annotated-figure renderer and themes from the Hickey-lab template.
- `build_from_plan` — render a flexible **dict** deck-plan (title / section_divider / figure / two_figure / multi_figure / quote / text / references) to `.pptx`, optionally with a Marp mirror and click animations.
- `build_deck_from_lineage_result` — take a `/lit-arc` `LineageRunResult` and synthesize a ~7-slide journal-club deck (mechanical fast path, an LLM `plan_callback` path, or an adversarial-crosstalk path), writing provenance receipts alongside.
- `render_pptx` — the low-level renderer: turn a simple `Deck` of `Slide`s into a `.pptx`. The **only** module that talks to `python-pptx` in the typed path.
- `RenderError` — raised when rendering fails (python-pptx missing, figure not found, etc.).

Typed deck data model:

- `Slide` — one layout-agnostic slide (`title` / `content_with_bullets` / `figure_with_caption`); validates its layout on construction.
- `Deck` — an ordered list of `Slide`s plus title, theme, working dir, and free-form provenance metadata.
- `DeckSlide` — one slide spec for the multi-slide composer; a `kind` (`title` / `section_intro` / `figure` / `bullets` / `references`) plus a permissive per-kind `content` dict.
- `DeckPlan` — the full deck structure (title, speaker, sections, slides, theme) consumed by `build_deck`.

Self-review + audits (deterministic by default; one optional LLM add-on):

- `review_deck` — run the composite self-review over a rendered `.pptx`. The core checks are deterministic and LLM-free: layout hard rules (fonts, min sizes, no overlap), descriptive titles, bullet density, figure presence, story arc. Pass `budget_minutes` to fold in the (still LLM-free) time-budget audit. Pass `anticipate_questions=True` to also run the Q&A anticipator; that step stays heuristic unless you *also* hand it a `qa_runner_callback`, in which case the deck's text is sent to that LLM (with heuristic fallback on failure).
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

Speaker notes (dual-format: a mental map for fluent presenters + a word-for-word script):

- `dual_format` — build a notes string from a mental-map dict + a detailed script.
- `format_speaker_notes` / `parse_speaker_notes` — render / re-parse the notes format.
- `attach_to_slide` — attach a notes string to a slide's notes panel.

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

**Consumed by:** the deck-building workflows and the `/build-deck`, `/journal-club`, `/preview-deck`, `/review-deck`, `/slide-review`, and `/reorder-slides` slash commands. Where it sits in the pipeline: literature run → figure assignment → **deck composition (here)** → self-review → the rendered deck the user opens.

## What it does NOT do

- It does **not** search literature, read papers, or generate figures — it consumes summaries and figure images that upstream subsystems (`vaultlab.research`, `vaultlab.figures`) already produced.
- Its self-review core — the `review_deck` layout/title/density/figure-presence/story-arc checks, `audit_time_budget`, and the default heuristic `anticipate_qa` mode — is **deterministic and LLM-free**: it checks the rendered file mechanically and does not judge whether the science is correct. The **only** path that reaches an LLM is opt-in: `anticipate_qa` (or `review_deck(..., anticipate_questions=True, qa_runner_callback=...)`) when you explicitly supply a runner callback.
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
- `layouts/` — the declarative `LayoutSpec` registry plus the imperative lab-template slide primitives.
- `notes.py` — dual-format speaker-notes builder/parser.
- `animations.py` — OOXML click-animation engine.
- `annotate/` — figure-annotation overlay primitives (`add_annotations`).
- `annotated_figure_slide.py` — the annotated-figure-slide builder the composer delegates to.
- `marp.py` — dict deck-plan → Marp markdown mirror.
- `kb_reader.py` — `KBReader` file I/O over the KB layout.
- `preview_html.py` / `audit_html.py` — browser-openable deck preview + audit-report HTML.
- `journal_club_arcs.py`, `templates/` — narrative skeletons per audience (journal club, lab meeting, conference talk, investor pitch).

## See also

- `src/vaultlab/figures/README.md` — where the figures placed on figure slides come from.
- `src/vaultlab/research/README.md` — the literature pipeline that produces the `LineageRunResult` and summaries decks are built from.
- `src/vaultlab/workflows/` — `deck_plan` (plan generation) and `crosstalk` (adversarial planning + rigor audit) that drive this package.
- `src/vaultlab/provenance/` — the receipt format every rendered deck writes.
- `.claude/commands/build-deck.md`, `journal-club.md`, `review-deck.md`, `preview-deck.md` — the user-facing slash commands.
- `docs/architecture.md` — the `vaultlab.slides` architectural sketch.
