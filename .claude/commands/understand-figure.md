---
name: understand-figure
purpose: Run the 4-step figure-understanding pipeline on a single cached figure. No API key needed.
arguments: <doi> <figure-path>
---

# /understand-figure

Run the hybrid figure-understanding pipeline on ONE cached figure. The
pipeline produces:

- A markdown reasoning log at
  `<kb-root>/Sources/Figures/<doi-slug>/<fig-stem>.understand.md`
- An annotated PNG (figure with bounding-box overlays + numbered markers)

Steps:

1. **Describe (LLM = YOU)** — read the figure visually and describe its
   discrete elements.
2. **Localize (programmatic)** — color-motif connected components.
3. **Match (LLM = YOU)** — pair named elements with extracted regions.
4. **Verify (LLM = YOU)** — read the rendered annotated image, accept
   or retry up to N times.

You (Claude Code) ARE the LLM. The Python pipeline does deterministic
work (color extraction, region merging, PNG rendering); YOU do the
reasoning steps.

## How to execute

### Step 1 — Set up

```python
from pathlib import Path
from vaultlab.context import resolve_kb_root
from vaultlab.figures.understand import (
    ColorMotif,
    DescribeFigureTask,
    MatchElementsTask,
    VerifyAnnotationTask,
    prepare_describe_task,
    prepare_match_task,
    prepare_verify_task,
    render_describe_from_response,
    render_match_from_response,
    render_verify_from_response,
    save_understand_log,
    understand_figure,
)

# Parse $ARGUMENTS — expecting "<doi> <figure-path>"
doi, figure_path_str = "<from $ARGUMENTS split>"
figure_path = Path(figure_path_str)
kb_root = resolve_kb_root()
```

### Step 2 — Define your three callbacks

You implement these by reading the figure with the Read tool and
returning JSON matching each task.response_schema.

```python
def claude_code_describe(image_path: Path) -> str:
    """Step 1 — read the figure, describe what you see."""
    task = prepare_describe_task(
        image_path,
        paper_doi=doi,
        paper_tldr="<paste from Sources/Articles/<doi-slug>.md if available>",
    )
    # YOU now:
    #   1. Read(file_path=str(image_path))  — actually look at the figure
    #   2. Reason about what is in it
    #   3. Return JSON matching task.response_schema
    response = {
        "description": "<3–8 sentences about what is visually in the figure>",
        "elements": ["<element 1>", "<element 2>"],
    }
    description, _elements = render_describe_from_response(response, task)
    return description


def claude_code_match(description, regions):
    """Step 3 — pair named elements with extracted regions."""
    task = prepare_match_task(
        figure_path,
        description=description,
        described_elements=[],   # parsed from your Step 1 response
        regions=regions,
    )
    # YOU now: re-Read the figure if needed, pick best region per element.
    response = {
        "matches": [
            {"element_name": "<name>", "matched_region_id": "r0",
             "rationale": "<1–2 sentences>", "confidence": 0.9},
        ]
    }
    return render_match_from_response(response, task)


def claude_code_verify(annotated_png, annotations, iteration):
    """Step 4 — look at the annotated image and accept/retry."""
    task = prepare_verify_task(
        annotated_png,
        iteration=iteration,
        expected_elements=[a.label for a in annotations],
    )
    # YOU now: Read(file_path=str(annotated_png)) and decide.
    response = {
        "annotated_image_read": "<what you actually see>",
        "issues_found": [],   # empty if accept
        "decision": "ACCEPT",
    }
    return render_verify_from_response(response, task)
```

### Step 3 — Run the pipeline

```python
motifs = [
    ColorMotif("neon-green", (90, 145), 0.40, 0.40, 0.00003),
    ColorMotif("orange",     (15,  40), 0.40, 0.50, 0.00003),
    ColorMotif("magenta",    (290, 340), 0.30, 0.40, 0.00003),
    ColorMotif("blue",       (200, 260), 0.30, 0.40, 0.00003),
]

annotated_png = figure_path.with_suffix(".annotated.png")

annotations, log = understand_figure(
    figure_path,
    motifs,
    doi=doi,
    annotated_png_path=annotated_png,
    describe_fn=claude_code_describe,
    match_fn=claude_code_match,
    verify_fn=claude_code_verify,
)

print(f"Log: {save_understand_log(log, kb_root)}")
print(f"Annotated PNG: {annotated_png}")
```

## SDK-mode alternative

If you have an `ANTHROPIC_API_KEY` in your environment and don't want to
spawn a Claude Code session per figure, use the SDK wrapper:

```python
from vaultlab.figures.understand._sdk import understand_figure_via_sdk

annotations, log = understand_figure_via_sdk(
    figure_path,
    motifs,
    paper_doi=doi,
    paper_tldr="<paper context>",
)
```

That path calls Anthropic directly with the figure encoded as a vision
content block — no Claude Code session required.
