"""Executable smoke-test + reference for the vaultlab.report HTML system.

Runs all 6 HTML consumers + 3 interactive editors against realistic-shaped
fake data and writes the resulting .html files to ``examples/html_report_gallery/output/``.

Open any of the generated files in a browser to see the system in action.

Usage::

    python examples/html_report_gallery/run_gallery.py
    python examples/html_report_gallery/run_gallery.py --open

The ``--open`` flag opens the index in the default browser when done.
Otherwise, ``bobby-kb open vaultlab/examples/html_report_gallery/output/index.html``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# Allow running this script directly without installing vaultlab (e.g. from a
# fresh clone) by adding the src/ dir to sys.path when needed.
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
if (_REPO_ROOT / "src" / "vaultlab" / "__init__.py").exists():
    sys.path.insert(0, str(_REPO_ROOT / "src"))


def _sample_deck_plan() -> dict:
    return {
        "title": "Multi-lung spatial transcriptomics review",
        "slides": [
            {
                "type": "title",
                "title": "Multi-lung review",
                "subtitle": "Spatial transcriptomics meets host-pathogen biology",
                "section": "Intro",
            },
            {
                "type": "bullets",
                "title": "Why this matters",
                "bullets": [
                    "Lung tissue has 20+ structural cell types",
                    "Pre-spatial methods could not localize them",
                    "Cellular geography drives infection response",
                ],
                "section": "Intro",
            },
            {
                "type": "figure",
                "title": "Visium maps cells in tissue space",
                "bullets": ["55um spot resolution captures structural neighborhoods"],
                "caption": "Adapted from Asp et al. 2020.",
                "citation_source": "Fig. 1 of [1]",
                "section": "Method",
            },
            {
                "type": "figure",
                "title": "Infected niches show distinct neighborhood composition",
                "bullets": ["Infected regions cluster 3 SD apart from healthy"],
                "caption": "Cell types around infection foci differ.",
                "section": "Results",
            },
            {
                "type": "bullets",
                "title": "Discussion + open questions",
                "bullets": [
                    "Spatial signature precedes pathology by 48 hours",
                    "Mechanism remains unclear without intervention data",
                ],
                "section": "Discussion",
                "references": [
                    "Asp 2020 — Nature Biomed Eng",
                    "Park 2023 — Cell",
                    "Lee 2024 — Nat Methods",
                ],
            },
        ],
    }


def _sample_rigor_audit() -> dict:
    return {
        "passed": False,
        "issues": [
            {
                "loc": "Slide 2",
                "severity": "minor",
                "kind": "bullet-length",
                "fix": "Bullet 3 'Cellular geography drives infection response' exceeds 24 words after expansion; consider shortening.",
            },
            {
                "loc": "Slide 4",
                "severity": "major",
                "kind": "overclaim",
                "fix": "Soften 'cluster 3 SD apart' — show the actual distance metric and report n + test.",
            },
            {
                "loc": "Slide 4",
                "severity": "minor",
                "kind": "missing-citation",
                "fix": "Attribute the 'cluster 3 SD apart' analysis to its source paper.",
            },
            {
                "loc": "(global)",
                "severity": "minor",
                "kind": "references-list",
                "fix": "Reference [3] (Lee 2024) is uncited in the body.",
            },
        ],
    }


def _sample_papers() -> list[dict]:
    return [
        {
            "doi": "10.1038/s41587-019-0036-z",
            "title": "Visium: high-resolution spatial transcriptomics method",
            "authors": ["Asp M", "Bergenstrahle J", "Lundeberg J"],
            "year": 2020,
            "journal": "Nature Biomedical Engineering",
            "tier": "A",
            "year_bucket": "foundational",
            "role_in_set": "seed",
            "tldr": "Demonstrates 55um-spot spatial transcriptomics on heart tissue; foundational platform for downstream lung studies.",
            "key_findings": [
                "55um spot resolution captures structural neighborhoods",
                "Cell-type composition recoverable per spot",
                "Method generalizes across tissues",
            ],
            "citation_count": 1245,
        },
        {
            "doi": "10.1016/j.cell.2023.04.001",
            "title": "Multi-modal spatial profiling of lung tissue",
            "authors": ["Park S", "Lee M", "Chen R"],
            "year": 2023,
            "journal": "Cell",
            "tier": "A",
            "year_bucket": "validation",
            "role_in_set": "supporting",
            "tldr": "Integrates Visium + CODEX for protein-RNA co-localization in healthy and infected lung.",
            "key_findings": [
                "Protein-RNA co-localization with 3um resolution",
                "Infected regions show distinct neighborhood signature",
                "Validation across 4 donors",
            ],
            "citation_count": 412,
        },
        {
            "doi": "10.1038/s41592-024-02123-w",
            "title": "Open-source spatial neighborhood analysis",
            "year": 2024,
            "tier": "B",
            "year_bucket": "recent",
            "tldr": "Software paper introducing a fast neighborhood detector.",
            "citation_count": 38,
        },
    ]


def _sample_citations() -> list[dict]:
    return [
        {
            "raw_text": "(Asp 2020)",
            "authors": "Asp M",
            "year": 2020,
            "title": "Visium method paper",
            "claim": "Visium platform was developed for 55um spot resolution.",
            "source_file": "draft.md",
            "line_number": 42,
            "doi": "10.1038/s41587-019-0036-z",
            "status": "verified_fulltext",
            "risk": "low",
            "hallucination_flags": [],
        },
        {
            "raw_text": "(Park 2023)",
            "authors": "Park S",
            "year": 2023,
            "claim": "Park et al. integrated Visium and CODEX in lung tissue.",
            "source_file": "draft.md",
            "line_number": 88,
            "doi": "10.1016/j.cell.2023.04.001",
            "status": "verified_abstract",
            "risk": "medium",
            "hallucination_flags": [],
        },
        {
            "raw_text": "(Lee 2024)",
            "authors": "Lee M",
            "year": 2024,
            "claim": "Lee et al. proposed a novel neighborhood metric.",
            "source_file": "intro.md",
            "line_number": 12,
            "doi": "10.1038/s41592-024-02123-w",
            "status": "api_confirmed",
            "risk": "low",
            "hallucination_flags": [],
        },
        {
            "raw_text": "(Doe 2099)",
            "authors": "Doe J",
            "year": 2099,
            "claim": "Doe et al. demonstrate post-2025 spatial methods.",
            "source_file": "draft.md",
            "line_number": 144,
            "doi": "",
            "status": "suspect",
            "risk": "high",
            "hallucination_flags": ["Year in future", "DOI missing"],
        },
    ]


def _sample_audit_report() -> dict:
    return {
        "total": 4,
        "by_status": {
            "verified_fulltext": 1,
            "verified_abstract": 1,
            "api_confirmed": 1,
            "suspect": 1,
        },
        "high_risk_unverified": 1,
        "audit_date": "2026-05-12",
        "source_files": ["draft.md", "intro.md"],
        "hallucination_flags": ["Year in future", "DOI missing"],
        "action_items": [
            "Replace Doe (2099) with the real reference for the spatial claim",
            "Move 'api_confirmed' citations to 'verified_fulltext' by reading the PDFs",
        ],
        "citations": _sample_citations(),
    }


def _sample_reasoning_result() -> dict:
    return {
        "purpose": "rigor-audit",
        "crosstalk_status": "complete",
        "runtime_seconds": 38.4,
        "rounds": [
            {
                "role_id": "data_analyst",
                "prompt": "Audit the deck plan below for citation and claim rigor.",
                "output": "Found 4 issues: 1 overclaim (slide 4), 2 minor citation issues, 1 unused reference.",
            },
            {
                "role_id": "literature_critic",
                "prompt": "Are the claims supported by the literature corpus?",
                "output": "Slide 4's '3 SD apart' claim is not in the corpus. Asp 2020 does not characterize the metric this way.",
            },
            {
                "role_id": "synthesizer",
                "prompt": "Integrate into final structured fix-list.",
                "output": json.dumps(
                    {
                        "passed": False,
                        "issues": [
                            {"loc": "Slide 4", "severity": "major", "kind": "overclaim"},
                            {"loc": "Slide 4", "severity": "minor", "kind": "missing-citation"},
                            {"loc": "(global)", "severity": "minor", "kind": "references-list"},
                        ],
                    }
                ),
            },
        ],
        "final_output": _sample_rigor_audit(),
    }


def _sample_dossier() -> dict:
    return {
        "project_slug": "spatial-lung-review",
        "kb_root": Path("G:/My Drive/Knowledge/spatial-lung-review"),
        "compiled_at": datetime.now(UTC),
        "sections": [
            {
                "slug": "origin",
                "title": "Why this project exists (the origin)",
                "body": "Started in 2026 to map cellular geography of pulmonary infection.\n\n"
                "- Motivated by **bulk-only** prior literature\n"
                "- Spatial transcriptomics now affordable at scale",
                "sources": [Path("Sources/Notes/origin.md")],
            },
            {
                "slug": "current_state",
                "title": "Where we are (current state, last 2 weeks)",
                "body": "Lit-arc complete (~120 papers Tier A/B). Drafting Discussion section.\n\nCurrent open thread: align with Pentimalli 2025 framework on niche-vs-neighborhood.",
                "sources": [Path("Sources/Notes/state.md")],
            },
            {
                "slug": "frontier",
                "title": "Active frontier",
                "body": "",
                "sources": [],
            },
        ],
    }


def _sample_response_letter() -> dict:
    """Sample ResponseLetter dict (use dict form so dispatch can route via /audit-html)."""
    return {
        "reviewer": 2,
        "opening": "We thank Reviewer 2 for the constructive feedback. Below we address each comment.",
        "comments": [
            {
                "stable_id": "R2-C1",
                "reviewer": 2,
                "quote": "The sample size n=3 per condition is underpowered for the effect size claimed.",
                "kind": "method_critique",
                "action": "ACCEPT_ANALYSIS",
                "evidence_ref": "§Results, p.9 lines 4-12; Supplementary Table 2",
                "response_text": "We agree. A post-hoc power analysis (now in Supp. Table 2) shows that for the observed effect size (Cohen's d=1.6), n=3 yields 78% power at α=0.05. We have softened the claim and added the analysis.",
                "open_question": "",
            },
            {
                "stable_id": "R2-C2",
                "reviewer": 2,
                "quote": "The claim that the mechanism 'causes' tissue remodelling is not supported by observational data.",
                "kind": "overclaim",
                "action": "SOFTEN_CLAIM",
                "evidence_ref": "§Discussion, p.14 lines 8-15",
                "response_text": "We have revised 'causes' to 'is associated with, under the conditions tested'. The new wording aligns with the observational nature of the cohort.",
                "open_question": "",
            },
            {
                "stable_id": "R2-C3",
                "reviewer": 2,
                "quote": "Authors should perform a CRISPR knockout validation experiment.",
                "kind": "missing_experiment",
                "action": "AUTHOR_INPUT_NEEDED",
                "evidence_ref": "",
                "response_text": "",
                "open_question": "Do we have CRISPR-KO line access for the target within the 8-week revision window? If not, can we instead point to an existing KO study in the literature?",
            },
            {
                "stable_id": "R2-C4",
                "reviewer": 2,
                "quote": "The introduction misses the important reference of Park et al. 2023.",
                "kind": "missing_citation",
                "action": "ACCEPT_CITATION",
                "evidence_ref": "§Introduction, p.2 line 8",
                "response_text": "Apologies for the oversight. Park et al. 2023 is now cited at p.2 line 8 as foundational context for the spatial-transcriptomics framing.",
                "open_question": "",
            },
        ],
        "closing": "We hope these revisions address all of Reviewer 2's concerns and improve the manuscript.",
    }


def _sample_litarc_narrative() -> str:
    return """# Lit-arc overview

The field starts with **Asp et al. 2020** establishing Visium as the foundational platform.

## Validation phase

A series of validation studies extended the method:

- Park et al. integrated Visium with CODEX
- Lee et al. proposed a fast neighborhood metric

## Open questions

The unresolved tension between [[10.1016/j.cell.2023.04.001]] and earlier bulk work is the *core* of the discussion section.
"""


# ---------------------------------------------------------------------------
# Driver


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--open", action="store_true", help="open the index in the default browser")
    parser.add_argument(
        "--out",
        type=Path,
        default=_HERE / "output",
        help="output directory (default: examples/html_report_gallery/output)",
    )
    args = parser.parse_args(argv)
    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    from vaultlab.citations.report_html import write_citation_audit_html
    from vaultlab.kb.dossier_html import write_dossier_report
    from vaultlab.manuscript.respond_html import write_response_letter_html
    from vaultlab.report import _components as c
    from vaultlab.report import editors, render_report, write_artifact_html
    from vaultlab.research.litarc_html import write_litarc_report
    from vaultlab.slides.audit_html import write_audit_report
    from vaultlab.slides.preview_html import write_deck_preview
    from vaultlab.workflows.reasoning_html import write_reasoning_report

    deck_plan = _sample_deck_plan()
    audit = _sample_rigor_audit()
    papers = _sample_papers()
    narrative = _sample_litarc_narrative()
    cit_audit = _sample_audit_report()
    reasoning = _sample_reasoning_result()
    dossier = _sample_dossier()
    citations = _sample_citations()
    response_letter = _sample_response_letter()

    written: list[tuple[str, Path]] = []

    # Consumers
    written.append(
        (
            "Deck audit",
            write_audit_report(out_dir / "deck-audit.html", deck_plan, audit),
        )
    )
    written.append(
        (
            "Lit-arc narrative",
            write_litarc_report(
                out_dir / "litarc.html",
                topic="spatial transcriptomics in lung",
                narrative=narrative,
                papers=papers,
                citations=[
                    ("10.1016/j.cell.2023.04.001", "10.1038/s41587-019-0036-z"),
                    ("10.1038/s41592-024-02123-w", "10.1038/s41587-019-0036-z"),
                    ("10.1038/s41592-024-02123-w", "10.1016/j.cell.2023.04.001"),
                ],
                scope="standard",
            ),
        )
    )
    written.append(
        (
            "Reasoning chain",
            write_reasoning_report(
                out_dir / "reasoning.html",
                reasoning,
                topic="rigor audit on multi-lung deck",
            ),
        )
    )
    written.append(
        (
            "Citation audit",
            write_citation_audit_html(out_dir / "citation-audit.html", cit_audit),
        )
    )
    written.append(
        (
            "Project dossier",
            write_dossier_report(out_dir / "dossier.html", dossier),
        )
    )
    written.append(
        (
            "Keynav deck preview",
            write_deck_preview(out_dir / "deck-preview.html", deck_plan),
        )
    )
    written.append(
        (
            "Reviewer response letter",
            write_response_letter_html(out_dir / "response-letter.html", response_letter),
        )
    )
    # Demonstrate the universal dispatcher: same data, routed by shape.
    written.append(
        (
            "Dispatched (auto-detect)",
            write_artifact_html(out_dir / "dispatched-reasoning.html", reasoning),
        )
    )

    # Editors
    written.append(
        (
            "Slide reorder editor",
            editors.write_slide_reorder_editor(out_dir / "slide-reorder.html", deck_plan),
        )
    )
    written.append(
        (
            "Citation triage editor",
            editors.write_citation_triage_editor(out_dir / "citation-triage.html", citations),
        )
    )
    written.append(
        (
            "Deck-plan tuner",
            editors.write_deckplan_tuner(
                out_dir / "deckplan-tuner.html",
                template="Slide {{slide_idx}}: {{title}}\n\n- {{bullet_1}}\n- {{bullet_2}}",
                samples=[
                    {
                        "slide_idx": "3",
                        "title": "Visium overview",
                        "bullet_1": "55um spots",
                        "bullet_2": "55,000 spots per 6.5mm chip",
                    },
                    {
                        "slide_idx": "5",
                        "title": "Lung application",
                        "bullet_1": "4 donors",
                        "bullet_2": "Healthy + infected pairs",
                    },
                ],
                sample_descriptions=["Asp 2020 — Visium overview", "Park 2023 — lung application"],
            ),
        )
    )

    # Index page linking to all of the above
    index_cards = [
        c.severity_card(
            label,
            body=f"<code>{path.name}</code> · open in browser to inspect",
            actions=[("Copy path", str(path))],
        )
        for label, path in written
    ]
    index_html = render_report(
        title="vaultlab.report — HTML gallery",
        eyebrow="vaultlab · gallery · smoke test",
        subtitle="All 6 consumers + 3 editors running on realistic-shaped sample data.",
        meta=f"Generated {datetime.now():%Y-%m-%d %H:%M} · output dir: <code>{out_dir}</code>",
        sections=[
            c.section(
                None,
                c.tldr_box(
                    [
                        f"{len(written)} HTML outputs generated.",
                        "Open each file in a browser to inspect. They're self-contained — "
                        "share, archive, or open offline.",
                        "Use this script as a reference when wiring vaultlab.report into a "
                        "new consumer or testing locally after edits.",
                    ]
                ),
            ),
            c.section("Outputs", c.card_grid(index_cards)),
        ],
    )
    index_path = out_dir / "index.html"
    index_path.write_text(index_html, encoding="utf-8")
    written.append(("Index", index_path))

    print()
    print(f"  Wrote {len(written)} files to {out_dir}:")
    for label, path in written:
        print(f"   - {label:<30} {path.relative_to(out_dir.parent)}")
    print()
    print(f"  Open the index:  bobby-kb open {index_path}")
    print()

    if args.open:
        import webbrowser

        webbrowser.open(index_path.as_uri())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
