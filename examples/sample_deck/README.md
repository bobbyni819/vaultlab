# Example: minimal deck

A 5-slide deck showcasing four of vaultlab's slide layouts. Runnable on
any machine (no KB / no literature corpus needed).

## What's here

- `build_sample_deck.py` — Python script that builds the deck via
  `vaultlab.slides.deck.build_from_plan()`.
- `placeholder_figure.png` — auto-generated bar chart used as the
  example figure (~1200×700, aspect 1.71 → routes to
  `figure_top_caption_br` layout).
- `expected_outputs/sample.pptx` — the rendered deck. Open in
  PowerPoint / Keynote. (Path is `expected_outputs/` to satisfy the
  repo-wide `*.pptx` gitignore — see `.gitignore`.)

## Run it

```bash
python examples/sample_deck/build_sample_deck.py
```

Outputs `sample.pptx` next to this README. If `placeholder_figure.png`
doesn't exist, the script generates one for you. Replace it with any
PNG/JPG to see how the layout adapts to different aspect ratios.

## What this demonstrates

| Slide | Layout | Why |
|---|---|---|
| 1 | `title` | Title + subtitle + author |
| 2 | `text` | Outline / table-of-contents pattern |
| 3 | `figure` | Auto-dispatched layout — wide-flat aspect → top-caption-bottom-right |
| 4 | `quote` | Big centered quote, useful for transitions |
| 5 | `references` | Auto-switches to 2-column when refs > 7 |

## Where to learn more

- `vaultlab/slides/deck.py:build_from_plan` — the dict-plan renderer.
- `vaultlab/slides/layouts/` — all the layout primitives.
- The hard rules (Roboto, min sizes 28pt heading / 24pt body / 18pt
  caption) are documented in `bobby_slides._template.min_sizes()`.

## Editing the plan

Open `build_sample_deck.py` and modify the `plan()` function. Each
slide is a dict with `type` (`title` / `text` / `figure` / `quote` /
`references`) plus per-type fields (`bullets`, `image_path`,
`citation_source`, etc.). Speaker notes are a per-slide dict with
`hook` / `key_claim` / `transition` / optional `script`.

Run the script again to regenerate `sample.pptx`.
