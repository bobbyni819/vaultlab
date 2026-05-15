# Examples

End-to-end workflow demos that compose vaultlab primitives. Each example
is a self-contained subdirectory you can run with `python run.py`.

> **Calling external contributors:** the [CONTRIBUTING.md three-example
> rule][rule] asks for ≥3 concrete use cases before proposing new
> primitives. The examples below are Bobby-authored seeds — adding your
> *own* workflow here (commit author ≠ Bobby) is the canonical way to
> raise the visibility of a new use case. Copy any of the templates,
> swap the inputs, and open a PR.

[rule]: ../CONTRIBUTING.md#the-three-example-rule-for-new-primitives

## Directory convention

Every example follows the same shape so external contributors can copy
it 1:1:

```
examples/<workflow-name>/
├── README.md          # what this does + how to run + how to adapt
├── run.py             # runnable with `python run.py` from the dir
├── inputs/            # bundled small/OA-only sample inputs
└── expected_outputs/  # reference outputs (or SUMMARY.md if > 200 KB)
```

`run.py` rules of the road:

1. **No new dependencies.** Use only what `pip install -e ".[dev]"`
   provides. If you need something new, file an issue first.
2. **LLM-optional.** If your pipeline calls an LLM, fall back to a
   deterministic mock when API config is missing — runnable
   *offline* is a hard requirement.
3. **OA inputs only.** Use PMC OA / arXiv CC-BY or fabricate synthetic
   inputs and document the choice in the example README.
4. **Reference outputs < 200 KB.** Larger reference outputs get
   replaced by a `expected_outputs/README.md` describing what `run.py`
   produces.

## Seed workflows (sub-goal 3.1)

| Example | Composes | Output |
|---|---|---|
| [`journal-club/`](journal-club/) | `vaultlab.research.ResearchClient` + `vaultlab.slides.build_from_plan` | `.pptx` deck + `paper.md` summary |
| [`manuscript-section/`](manuscript-section/) | `vaultlab.manuscript.polish` + `vaultlab.citations.audit_file` | polished `.md` section + polish findings + citation audit JSON |
| [`citation-cleanup/`](citation-cleanup/) | `vaultlab.citations.extract_citations` (no APIs) | Remediation `.md` + JSON dump |

## Flagship demos (scaffolds, full demo lands at v0.1.0)

| Example | Demonstrates | Status |
|---|---|---|
| [`codex_hubmap_tonsil/`](codex_hubmap_tonsil/) | Full wet-lab → manuscript pipeline on public CODEX data | scaffold |
| [`pbmc3k/`](pbmc3k/) | scRNA-seq vignette | scaffold |
| [`visium_brain/`](visium_brain/) | Visium spatial vignette | scaffold |

## HTML-report gallery

| Example | Demonstrates |
|---|---|
| [`html_report_gallery/`](html_report_gallery/) | All 6 `vaultlab.report` HTML consumers + 3 interactive editors on realistic-shaped sample data |
| [`sample_deck/`](sample_deck/) | Minimal `.pptx` reference output |

## Adding a new example

1. Pick a workflow you actually ran. Even a 30-minute pipeline counts.
2. Copy the shape of [`citation-cleanup/`](citation-cleanup/) — it's the
   lightest of the three seeds and a good template.
3. Strip your inputs down to the smallest reproducer. Avoid bundling
   paywalled content; PMC OA, arXiv CC-BY, or synthetic-with-disclaimer
   are the accepted options.
4. Pin no new dependencies. Mock LLM calls.
5. Open a PR with `DCO sign-off` (`git commit -s …`).

Examples are reviewed by the same three-example rule used for new
primitives — see [CONTRIBUTING.md](../CONTRIBUTING.md) for full details.
