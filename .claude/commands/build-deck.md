---
name: build-deck
type: orchestrated
backed_by: vaultlab.research.lineage.run_lit_arc + vaultlab.figures.acquisition.acquire_figures_for_corpus + vaultlab.slides.build_deck_from_lineage_result
purpose: Compose a journal-club .pptx from a topic by chaining /lit-arc, figure acquisition, and the multi-slide composer.
---

# /build-deck <topic> [--speaker NAME] [--length N] [--theme hickey_lab|default]

End-to-end deck builder. Given a research topic, this runs the literature
arc, attempts to acquire figures from the PMC OA tar packages of the seed
papers, then composes a 7-slide deck via
`vaultlab.slides.build_deck_from_lineage_result()`.

## Arguments

- `<topic>` (required) — the topic / query string. Example: `"CAR-T cell engineering"`
- `--speaker NAME` (default: derived from `git config user.name`) — speaker name on title slide
- `--length N` (default: 7) — currently informational; the lineage composer
  always emits 7 slides (title + 3 section_intros + 1 figure-or-bullets + 1
  bullets + references)
- `--theme hickey_lab|default` (default: `hickey_lab`) — picks which
  template to initialize from. `hickey_lab` requires the bundled template;
  `default` is a vanilla 16:9.

## What it does

1. **Parse the topic + speaker name** from arguments. If `--speaker` is
   absent, fall back to `git config user.name`, then "Researcher".
2. **Look up KB root** via `~/.config/bobby_kb/config.json` (key
   `default_kb_root` or `root`). Default: `G:/My Drive/Knowledge`. If
   the user has a `vaultlab` KB configured, use it; otherwise use the
   default research KB.
3. **Run lit-arc** by calling
   `vaultlab.research.lineage.run_lit_arc(topic, kb_root=...)`. This
   produces a `LineageRunResult` with paths to the per-paper summaries
   and the lineage-arc concept page. If a previous lit-arc run for this
   exact topic on today's date already exists at the canonical
   `Wiki/Concepts/<slug>-lineage-<date>.md` path, **reuse** it
   (synthesize a `LineageRunResult` from the existing files rather than
   re-running the search).
4. **Acquire figures** by calling
   `vaultlab.figures.acquisition.acquire_figures_for_corpus(corpus, cache_dir)`.
   This reaches into PMC OA tar packages for any seeds that are in PMC.
   For each DOI that successfully resolved a figure, build a
   `figure_assignments: dict[str, Path]` mapping.
   - **Graceful fallback:** if `vaultlab.figures.acquisition` is not
     importable (a parallel agent may still be wiring it up), skip this
     phase and pass `figure_assignments={}` to the composer. The composer
     will replace the figure slide with a bullets slide using the
     paper's TL;DR — see `_pick_figure_for_bucket` in `slides/deck.py`.
5. **Compose the deck** by calling
   `vaultlab.slides.build_deck_from_lineage_result(result, speaker=..., affiliation=..., project_slug="lit-arc", figure_assignments=..., kb_root=...)`.
   Output is auto-routed via `vaultlab.kb.paths.deck_path()` to
   `Output/lit-arc/<topic-slug>-deck.pptx`.
6. **Print the open command** so Bobby can open the deck:

   ```
   To open: bobby-kb open <relative-path-from-kb-root>
   ```

## Implementation sketch

```python
from pathlib import Path
from vaultlab.research.lineage import run_lit_arc, LineageRunResult
from vaultlab.slides import build_deck_from_lineage_result
from vaultlab.workflows import DeckPlanTask
from vaultlab.kb.paths import concept_path, slugify_topic, summary_path

# Step 1-2: parse args, resolve kb_root
topic = "<from args>"
speaker = "<from args or git config>"
kb_root = Path("G:/My Drive/Knowledge/vaultlab")  # or research KB

# F-1 onboarding handoff: when /onboard-project ran earlier in this
# project folder (or a parent), pick up slug + kb_root + topic from the
# .vaultlab-project.json instead of re-asking. Threading explicitly is
# still recommended; the orchestrators (run_lit_arc, run_lit_report,
# build_deck_from_lineage_result) ALSO fall back to
# load_project_config_from_cwd() internally when project_slug is None
# (G-2 fix from conceptual-flow audit 2026-04-30), so a forgetful caller
# no longer silently spawns a parallel Wiki/Projects/<topic-slug>/.
# Explicit kwargs still win when the values disagree.
from vaultlab.onboarding import load_project_config_from_cwd
project_cfg = load_project_config_from_cwd()
project_slug = "lit-arc"  # default — overridden by onboarding cfg below
if project_cfg is not None:
    if project_cfg.slug:
        project_slug = project_cfg.slug
    if project_cfg.kb_root:
        kb_root = Path(project_cfg.kb_root)
    if not topic and project_cfg.topic:
        topic = project_cfg.topic

# Step 3: lit-arc (reuse if already-run today)
result = run_lit_arc(topic, kb_root=kb_root, project_slug=project_slug, max_seeds=10)

# Step 4: figure acquisition (graceful)
figure_assignments: dict[str, Path] = {}
try:
    from vaultlab.figures.acquisition import acquire_figures_for_corpus
    cache_dir = kb_root / "Output" / "lit-arc" / "figures_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    # acquire_figures_for_corpus(corpus, cache_dir) returns
    # dict[doi -> FigureAcquisitionResult]; pick first .figures[0].path
    # for each successful result.
except ImportError:
    pass  # falls back to bullets

# Step 5: define the content-aware plan generator (YOU read summaries)
# When given a plan_callback, build_deck_from_lineage_result routes through
# vaultlab.workflows.deck_plan.generate_deck_plan instead of the mechanical
# synthesizer. The LLM (Claude Code itself) reads ALL Tier-A summaries +
# corpus metrics + figure assignments and produces a typed slide plan.

def claude_code_plan_generator(task: DeckPlanTask) -> dict:
    """LLM-driven story-arc reasoning. YOU implement at runtime by:
      1. Reading task.corpus_summaries (Tier-A papers' TL;DR + key_findings)
      2. Reading task.corpus_metrics (OG-score, year_buckets, top co-citations)
      3. Reading task.figure_assignments (doi -> figure path)
      4. Deciding 3-5 story beats (history -> dev -> SOTA OR another arc shape)
      5. Picking which figures illustrate which claims (substitution OK —
         claim_paper_doi can differ from figure_paper_doi)
      6. Returning JSON matching task.response_schema:

    {
      "story_arc_summary": "<one sentence>",
      "slides": [
        {"type": "title", "title": "...", ...},
        {"type": "section_divider", "title": "..."},
        {"type": "figure", "image_path": "...",
         "claim_paper_doi": "10.1126/...",
         "figure_paper_doi": "10.1126/...",  # may differ
         "caption": "...", "bullets": [...], "speaker_notes": {...}},
        {"type": "text", "title": "...", "bullets": [...], "speaker_notes": {...}},
        ...
      ]
    }

    The references slide is auto-appended by the renderer from cited DOIs.
    Do NOT include it in your response.

    Pick exactly task.target_slide_count slides (default 7).
    """
    # YOU read summaries + return JSON. No SDK; Claude Code IS the LLM.
    ...

# Step 6: compose with content-aware plan generation + crosstalk + audit
out = build_deck_from_lineage_result(
    result,
    speaker=speaker,
    affiliation="Hickey Lab @ Duke BME",
    project_slug=project_slug,        # F-1: from .vaultlab-project.json
                                      # (defaults to "lit-arc" if no
                                      # onboarding cfg was found)
    figure_assignments=figure_assignments,
    kb_root=kb_root,
    plan_callback=claude_code_plan_generator,  # LLM-driven plan
    audience="journal-club",                   # shapes the prompt
    target_slide_count=7,
    
    # Crosstalk integration (tiered default ON per Bobby's decision)
    plan_mode="adversarial",          # "fast" | "adversarial"
                                       # adversarial: narrator+figure_lead+
                                       # methods_critic+synthesizer ADVERSARIAL
                                       # meeting on the plan; fast: single-shot
    crosstalk_runner=claude_code_runner,  # see lit-arc.md for runner shape
    final_audit=True,                  # rigor_auditor reviews the deck before
                                        # ship; flags claims without evidence,
                                        # missing wikilinks, etc.
    audit_strict=False,                # False: prepends warning slide listing
                                        # issues; True: refuses to write .pptx
                                        # if rigor issues found
)

# Pass plan_callback=None + plan_mode="fast" to fall back to mechanical
# synthesis (faster, but doesn't reason about story arc — used to be the
# only path).

# Step 7: print open command
rel = out.relative_to(kb_root)
print(f"To open: bobby-kb open {rel.as_posix()}")
```

## Notes

- **Reuse policy:** if `Wiki/Concepts/<topic-slug>-lineage-<today>.md`
  already exists, do NOT re-run `run_lit_arc` — synthesize the
  `LineageRunResult` from the on-disk files. This makes the slash
  command idempotent within a day.
- **No LLM call for slide content:** slide text comes entirely from the
  lineage result + the per-paper summaries. If those have placeholders
  (e.g. "narrative skipped" because no `ANTHROPIC_API_KEY`), the deck
  will reflect that — fix the lineage, not the deck.
- **Theme requires the bundled template:** the Hickey Lab template
  ships with the `vaultlab` package at
  `src/vaultlab/slides/themes/_assets/hickey_lab_template.pptx`. If
  it's missing, `build_deck` falls back to a vanilla theme and logs a
  warning.

## Related

- `/lit-arc <topic>` — phase 1 alone (search → corpus → summaries → arc)
- `/paper-to-slides <doi>` — single-paper journal-club deck (to be built)
- `vaultlab.slides.deck.build_deck` — the composer (programmatic API)
