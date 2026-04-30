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
from vaultlab.kb.paths import concept_path, slugify_topic, summary_path

# Step 1-2: parse args, resolve kb_root
topic = "<from args>"
speaker = "<from args or git config>"
kb_root = Path("G:/My Drive/Knowledge/vaultlab")  # or research KB

# Step 3: lit-arc (reuse if already-run today)
result = run_lit_arc(topic, kb_root=kb_root, max_seeds=10)

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

# Step 5: compose
out = build_deck_from_lineage_result(
    result,
    speaker=speaker,
    affiliation="Hickey Lab @ Duke BME",
    project_slug="lit-arc",
    figure_assignments=figure_assignments,
    kb_root=kb_root,
)

# Step 6: print open command
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
