# Figure-Manuscript Verification Pipeline

## Thesis

The figure-to-manuscript pipeline is best understood as a verification and provenance loop, not as a larger pool of agents. Its central claim is that manuscript prose should only advance when the rendered figure, the coverage sidecar, the claim ledger, the citation tier, reviewer-facing preflight, manuscript state, and deck view remain synchronized and replayable. Several steps are deterministic today, while role/vision passes are prepared or optional unless a caller supplies an LLM executor.

## Loop

```text
FigureContract
  -> contract-bound render
  -> publication bundle + CoverageManifest
  -> ClaimLedger
  -> figure-text consistency
  -> read-the-PNG visual QA
  -> Tier-3 citation gate
  -> reviewer preflight
  -> manuscript state machine
  -> verification ladder
  -> data-availability draft
  -> claims-to-deck sync
```

Figure-side helpers plug into this loop rather than replacing it. The lifecycle registry in `vaultlab.figures.index` helps prevent re-deriving an existing claim figure; `StyleProfile` keeps project style choices explicit; `explain_figure()` creates the five-part plain-language explainer; `run_figure_tournament()` ranks alternatives as a prioritization signal; and `recombine()` can create a child artifact from two parents before sending it back through the same checks.

## Stage Map

| Stage | Module | Entrypoint | What it guarantees |
|---|---|---|---|
| Figure contract | [`src/vaultlab/figures/contract.py`](../src/vaultlab/figures/contract.py) | `FigureContract`, `validate_contract()` | A figure has an explicit conclusion, evidence chain, archetype, backend, export contract, and submission-relevant metadata before plotting. |
| Contract-bound render | [`src/vaultlab/figures/publication/bundle.py`](../src/vaultlab/figures/publication/bundle.py) | `render_with_contract()` | Existing recipes can be routed through the publication bundle after contract validation. |
| Publication bundle | [`src/vaultlab/figures/publication/bundle.py`](../src/vaultlab/figures/publication/bundle.py) | `save_publication_figure()` | A matplotlib figure is saved as a fixed bundle: PNG anchor, SVG, PDF, optional coverage JSON, layout audit, provenance, and method sidecar. |
| Coverage sidecar | [`src/vaultlab/figures/publication/coverage.py`](../src/vaultlab/figures/publication/coverage.py) | `CoverageManifest` | Coverage copy comes from a structured manifest with JSON I/O, validation, source data, hashes, params, and footer rendering. |
| Claim ledger | [`src/vaultlab/manuscript/claim_ledger.py`](../src/vaultlab/manuscript/claim_ledger.py) | `ClaimLedger.from_markdown()`, `CitationTier` | Manuscript markdown maps each tagged claim to figure links, numeric source links, and citation tiers. |
| Figure-text consistency | [`src/vaultlab/manuscript/figure_text_consistency.py`](../src/vaultlab/manuscript/figure_text_consistency.py) | `check_figure_text_consistency()` | Deterministic checks flag missing or cut figures, number mismatches, and conservative identity contradictions. |
| Visual QA | [`src/vaultlab/figures/understand/visual_qa.py`](../src/vaultlab/figures/understand/visual_qa.py) | `visual_qa_figure()` | The exported PNG is audited with deterministic layout checks, with optional vision readback when requested. |
| Layout sidecar | [`src/vaultlab/figures/layout_sidecar.py`](../src/vaultlab/figures/layout_sidecar.py) | `build_matplotlib_layout_sidecar()`, `audit_layout_sidecar()` | A matplotlib figure can emit object boxes for axes, labels, legends, annotations, canvas size, and intended display scale before the figure object is closed. |
| PPTX panel contract | [`src/vaultlab/slides/panel_contract.py`](../src/vaultlab/slides/panel_contract.py) | `audit_panel_layout_contract()`, `extract_pptx_slide_geometry()` | Manuscript-style panel slots can be checked for bounds, gutters, overlap, and panel-letter font size; existing slides can be read for native PowerPoint shape geometry. |
| Citation gate | [`src/vaultlab/manuscript/citation_gate.py`](../src/vaultlab/manuscript/citation_gate.py) | `run_citation_gate()` | Claims below the required citation tier are blocked and queued for concrete promotion actions. |
| Reviewer preflight | [`src/vaultlab/manuscript/preflight.py`](../src/vaultlab/manuscript/preflight.py) | `run_manuscript_preflight()` | Ledger, figure-text, visual-QA, and prepared reviewer-role outputs are normalized into one ranked fix queue. |
| Manuscript state | [`src/vaultlab/manuscript/state.py`](../src/vaultlab/manuscript/state.py) | `assess_manuscript()`, `ManuscriptStage` | The manuscript advances through strict lifecycle stages only as evidence, figures, citations, and reviewer gates pass. |
| Verification ladder | [`src/vaultlab/manuscript/verification_ladder.py`](../src/vaultlab/manuscript/verification_ladder.py) | `assess_verification_ladder()`, `LadderRung` | Each claim and figure receives the strongest proven rung; the weakest claim remains visible. |
| Data availability | [`src/vaultlab/manuscript/data_availability.py`](../src/vaultlab/manuscript/data_availability.py) | `data_sources_from_coverage()` | Coverage sidecars can seed an additive DAS draft that lists source data by figure and hash. |
| Deck sync | [`src/vaultlab/manuscript/deck_sync.py`](../src/vaultlab/manuscript/deck_sync.py) | `sync_claims_to_deck()` | Ledger figures and deck figures are compared with deterministic stem-based matching. |
| Figure lifecycle | [`src/vaultlab/figures/index.py`](../src/vaultlab/figures/index.py) | `FigureStage`, `set_figure_stage()`, `find_existing_for_claim()` | Registered figures can move through exploratory/candidate/manuscript/supplementary/archive states and be queried by claim. |
| Style profile | [`src/vaultlab/figures/publication/profile.py`](../src/vaultlab/figures/publication/profile.py) | `StyleProfile`, `default_profile()`, `apply_profile()` | Journal target, font regime, entity palettes, semantic colors, and heatmap conventions are explicit project configuration. |
| Figure explainer | [`src/vaultlab/figures/explain.py`](../src/vaultlab/figures/explain.py) | `explain_figure()` | A deterministic one-breath plus five-part explainer is seeded from contract, coverage, and optional ledger claims. |
| Alternatives | [`src/vaultlab/figures/tournament.py`](../src/vaultlab/figures/tournament.py) | `run_figure_tournament()` | Figure variants are pairwise ranked with retained match rationale; the winner is not treated as proof. |
| Recombination | [`src/vaultlab/recombine.py`](../src/vaultlab/recombine.py) | `recombine()` | Two parent artifacts can produce a child with optional verification and an inspectable accept/reject result. |

## Lineage

This stack appears to lift Bobby's Metabolism practices into reusable vaultlab modules. The figure-contract discipline maps to `FigureContract` and `validate_contract()`: the figure starts with a conclusion, panel evidence, and export requirements instead of retrofitting rigor after plotting. The two-figure system maps to `FigureStage`, `set_figure_stage()`, and `find_existing_for_claim()`: exploratory, candidate, manuscript, supplementary, archived, and superseded figures can be tracked instead of rediscovered. The five-part explainer practice maps to `explain_figure()`. Tier-3 verbatim citation discipline maps to `CitationTier` and `run_citation_gate()`, although the current gate consumes tier status rather than fetching full text itself. The style-engine practice maps to `StyleProfile`, `apply_profile()`, `resolve_entity_palette()`, and `heatmap_kwargs()`.

The May-2026 Co-Scientist, Robin, and ERA papers are useful here as architectural analogies, not as proof that a given manuscript claim is correct. The improvement plan frames Co-Scientist as evidence for durable candidate state, critique/rank/evolve loops, and tournaments; the local counterpart is the combination of `FigureStage`, `run_figure_tournament()`, and the manuscript state machine. Robin is most relevant to multi-agent verification and external grounding; the local counterpart is `run_manuscript_preflight()`, which always runs deterministic checks and can prepare or execute reviewer roles. ERA is most relevant to executable scoring and recombination; the local counterpart is `save_publication_figure()` plus layout/visual checks, `assess_verification_ladder()`, and `recombine()`. In all three cases, the transferable lesson is hedged: scored, replayable loops are a stronger substrate than one-shot answers.

## Quickstart

This illustrative snippet mirrors the happy path in [`tests/test_vaultlab_pipeline_e2e.py`](../tests/test_vaultlab_pipeline_e2e.py). It renders a toy figure, writes the publication bundle, builds the claim ledger, then reads manuscript state and ladder status.

```python
from pathlib import Path
import shutil
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from vaultlab.figures.contract import FigureContract
from vaultlab.figures.layout_sidecar import build_matplotlib_layout_sidecar, write_layout_sidecar
from vaultlab.figures.publication.bundle import save_publication_figure
from vaultlab.figures.publication.coverage import CoverageManifest
from vaultlab.figures.understand.visual_qa import visual_qa_figure
from vaultlab.manuscript.citation_gate import run_citation_gate
from vaultlab.manuscript.claim_ledger import ClaimLedger
from vaultlab.manuscript.data_availability import data_sources_from_coverage
from vaultlab.manuscript.figure_text_consistency import check_figure_text_consistency
from vaultlab.manuscript.preflight import run_manuscript_preflight
from vaultlab.manuscript.state import assess_manuscript
from vaultlab.manuscript.verification_ladder import assess_verification_ladder

root = Path(tempfile.mkdtemp(prefix="vaultlab-pipeline-"))
source_data = root / "source-data" / "fig1-values.csv"
source_data.parent.mkdir()
source_data.write_text("group,value\nbaseline,0.12\ntreated,0.82\n", encoding="utf-8")

coverage = CoverageManifest(
    figure_id="1",
    script_path="quickstart.py",
    timestamp="2026-06-20T12:00:00Z",
    panel_role="main",
    regions_included=["synthetic-region"],
    donors_included=["d1", "d2", "d3"],
    cell_types_included=["synthetic-cell"],
    source_data=[str(source_data)],
    source_data_sha256={str(source_data): "0" * 64},
    params={"caption": "rho=0.82; synthetic-region"},
)
contract = FigureContract(
    conclusion="The synthetic treatment condition has the expected higher value.",
    evidence_chain={"A": "Panel A reports the synthetic treatment statistic."},
    width_mm=89.0,
    height_mm=70.0,
    dpi=300,
    source_data_path=source_data,
    stats_block="Spearman rho=0.82 from deterministic synthetic data.",
)

fig, ax = plt.subplots(figsize=(3.2, 2.4), constrained_layout=True)
ax.bar(["baseline", "treated"], [0.12, 0.82], color=["#4C78A8", "#59A14F"])
ax.set_ylim(0, 1)
ax.set_ylabel("association")
ax.set_title("Synthetic association")

bundle_dir = root / "bundle"
bundle = save_publication_figure(
    fig,
    bundle_dir / "1",
    contract=contract,
    coverage=coverage,
    recipe_id="pipeline-quickstart",
)

figures_dir = root / "figures"
coverage_dir = root / "coverage"
figures_dir.mkdir()
coverage_dir.mkdir()
shutil.copyfile(bundle.png, figures_dir / "1.png")
shutil.copyfile(bundle.coverage_json, coverage_dir / "1.coverage.json")
layout_sidecar = build_matplotlib_layout_sidecar(
    fig,
    figure_path=figures_dir / "1.png",
    target_width_in=3.2,
)
write_layout_sidecar(layout_sidecar)

manuscript_md = f"""
# Synthetic manuscript

[CLAIM:c1 kind=quantitative section=Results] The synthetic treatment association was
rho=0.82 in Figure 1, consistent with the source table.
[FIG:1] [STAT:rho=0.82 src="{source_data}" method=spearman]
[CITE:smith2026 tier=3 status=verified_fulltext]

Figure 1 reports the deterministic synthetic association.
"""

ledger = ClaimLedger.from_markdown(manuscript_md)
consistency = check_figure_text_consistency(
    manuscript_md,
    ledger=ledger,
    figures_dir=figures_dir,
    coverage_dir=coverage_dir,
)
visual_qa = visual_qa_figure(
    figures_dir / "1.png",
    layout_sidecar=layout_sidecar,
    run_vision=False,
    write_sidecar=False,
)
citation_gate = run_citation_gate(ledger=ledger)
preflight = run_manuscript_preflight(
    manuscript_md,
    ledger=ledger,
    figures_dir=figures_dir,
    coverage_dir=coverage_dir,
    roles=[],
    run_visual_qa=True,
)
state = assess_manuscript(
    manuscript_md,
    ledger=ledger,
    figures_dir=figures_dir,
    coverage_dir=coverage_dir,
    roles=[],
    run_visual_qa=True,
)
ladder = assess_verification_ladder(
    manuscript_md,
    ledger=ledger,
    figures_dir=figures_dir,
    coverage_dir=coverage_dir,
    run_visual_qa=False,
)
sources = data_sources_from_coverage(coverage_dir)

print("consistency:", consistency.ok)
print("visual QA:", visual_qa.verdict)
print("citation gate:", citation_gate.ok)
print("preflight:", preflight.ok)
print("stage:", state.current_stage.name)
print("weakest claim rung:", ladder.min_claim_rung.name if ladder.min_claim_rung else None)
print(sources.to_das_draft())
```

Relevant local command surfaces exist for adjacent pieces, but there is not yet a single dedicated CLI command for the whole figure-manuscript pipeline. Existing slash commands include `/figure-contract`, `/understand-figure`, `/publication-guideline-audit`, `/das-audit`, `/triage-citations`, and `/build-deck`. The installed `vaultlab` CLI currently exposes general commands such as `vaultlab demo`, `vaultlab init`, `vaultlab claude-setup`, and `vaultlab slides review <pptx> [--html <out>]`; it does not expose `assess_manuscript()` or `run_manuscript_preflight()` as first-class CLI subcommands.

## Deterministic vs LLM Status

Deterministic or CI-safe by default: `CoverageManifest.validate()`, `CoverageManifest.audit()`, `ClaimLedger.from_markdown()`, `ClaimLedger.audit()`, `check_figure_text_consistency()`, `build_matplotlib_layout_sidecar()`, `audit_layout_sidecar()`, `visual_qa_figure(..., run_vision=False)`, `audit_panel_layout_contract()`, `extract_pptx_slide_geometry()`, `run_citation_gate()`, `run_manuscript_preflight()` without an executor, `assess_manuscript()`, `assess_verification_ladder()`, `data_sources_from_coverage()`, `sync_claims_to_deck()`, `explain_figure()` without `refine_fn`, and the default `run_figure_tournament()` scorer.

LLM-dependent or executor-dependent: `visual_qa_figure(..., run_vision=True)` requires a vision verifier or SDK path; `run_manuscript_preflight(..., executor=...)` can execute prepared reviewer-role passes; `assess_manuscript()` and `assess_verification_ladder()` inherit that executor-dependent reviewer status. Without an executor, role passes are prepared but not executed, and reviewer-audited readiness should remain blocked or advisory rather than silently accepted.

Citation grounding is tier-aware today, but the current manuscript gate consumes `CitationTier` / `VerificationStatus` values and promotion queues. Page-image citation grounding with exact page-image evidence remains planned rather than implemented in this pipeline; until that lands, Tier-3 claims should be treated as only as strong as the upstream citation verifier and evidence store that supplied `verified_fulltext`.
