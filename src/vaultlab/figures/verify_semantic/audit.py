"""Figure-audit engine — the command-facing layer above the per-pair verifier.

``/figure-audit`` runs the semantic verifier (:mod:`vaultlab.figures.verify_semantic.verifier`)
over one or more ``(figure, claim)`` pairs and produces a saved audit report + provenance
receipt. This is the discrete, user-invoked path recommended by the benchmark
(``<kb>/<project>/Output/figure-claim-verifier-2026-06-09/measurement-report.md``): measured
binary recall 1.0 on catching problems (no broken claim passed as SUPPORTED) with FABRICATED
detection 1.0/1.0 — at ~0.82 precision, which is acceptable for a reviewer-invoked audit but
NOT for an always-on inline ``/lit-arc`` gate (that path stays gated on a precision fix +
the figure-legibility defect in ``research/figures.py``).

Two execution modes, mirroring ``/understand-figure``:

* **SDK mode** (default; ``ANTHROPIC_API_KEY`` set) — each pair routes through
  :func:`verify_figure_claim` (real ``claude-sonnet-4-6`` vision).
* **Claude-Code-as-LLM mode** — pass ``verdict_fn``; Claude Code reads the figure with its
  own Read tool, applies ``prompt.md``, and returns a verdict dict, which is validated by
  :func:`validate_verdict` exactly as the SDK path is. No API key needed.

Scope: this audits EXPLICIT ``(figure, claim)`` pairs. Automatic extraction of figure-claims
from manuscript prose (claim mining + figure matching) is a separate, unbuilt component and
is intentionally out of scope (META PRINCIPLE #8 — do not ship an unproven step).
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from vaultlab.figures.verify_semantic.verifier import (
    DEFAULT_MODEL,
    VERDICT_VALUES,
    validate_verdict,
    verify_figure_claim,
)

logger = logging.getLogger(__name__)

# Binary collapse (matches the benchmark): PARTIAL counts as "problem flagged".
_FLAGGED_VERDICTS = {"PARTIAL", "UNSUPPORTED", "FABRICATED"}

# Verdict dict returned by Claude-Code-as-LLM mode.
VerdictFn = Callable[[str, str], dict[str, Any]]


@dataclass
class ClaimAudit:
    """One audited (figure, claim) pair."""

    figure: str
    claim: str
    verdict: str
    evidence_anchors: list[str]
    confidence: float
    flagged: bool


@dataclass
class FigureAuditReport:
    """Aggregate result of a figure-audit run."""

    project: str
    model: str
    n_claims: int
    n_flagged: int
    verdict_counts: dict[str, int]
    overall: str  # "clean" | "flags_found"
    audits: list[ClaimAudit] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _audit_one(
    figure_path: str | Path,
    claim: str,
    *,
    verdict_fn: VerdictFn | None,
    model: str,
) -> ClaimAudit:
    if verdict_fn is not None:
        validated = validate_verdict(verdict_fn(claim, str(figure_path)))
    else:
        validated = verify_figure_claim(claim, figure_path, model=model)
    return ClaimAudit(
        figure=Path(figure_path).name,
        claim=claim,
        verdict=validated["verdict"],
        evidence_anchors=validated["evidence_anchors"],
        confidence=validated["confidence"],
        flagged=validated["verdict"] in _FLAGGED_VERDICTS,
    )


def audit_figure_claims(
    pairs: list[tuple[str | Path, str]],
    *,
    project: str = "",
    model: str = DEFAULT_MODEL,
    verdict_fn: VerdictFn | None = None,
) -> FigureAuditReport:
    """Audit a list of ``(figure_path, claim)`` pairs.

    Returns a :class:`FigureAuditReport`. A non-schema-valid verdict (SDK or injected)
    raises :class:`SchemaViolation` — surfaced, never coerced into a default verdict.
    """
    if not pairs:
        raise ValueError("audit_figure_claims requires at least one (figure, claim) pair")

    audits = [_audit_one(f, c, verdict_fn=verdict_fn, model=model) for (f, c) in pairs]
    counts = {v: 0 for v in VERDICT_VALUES}
    for a in audits:
        counts[a.verdict] += 1
    n_flagged = sum(a.flagged for a in audits)
    return FigureAuditReport(
        project=project,
        model="claude-code-as-llm" if verdict_fn is not None else model,
        n_claims=len(audits),
        n_flagged=n_flagged,
        verdict_counts=counts,
        overall="clean" if n_flagged == 0 else "flags_found",
        audits=audits,
    )


def render_report_md(report: FigureAuditReport) -> str:
    """Render a human-readable markdown audit report (critical-first)."""
    lines: list[str] = []
    lines.append(f"# Figure-claim audit — {report.project or '(no project)'}")
    lines.append("")
    lines.append(f"- **Overall:** {report.overall}")
    lines.append(f"- **Claims audited:** {report.n_claims}  |  **Flagged:** {report.n_flagged}")
    lines.append(f"- **Verifier:** {report.model}")
    counts = "  ".join(f"{k}={report.verdict_counts[k]}" for k in VERDICT_VALUES)
    lines.append(f"- **Verdict counts:** {counts}")
    lines.append("")
    lines.append(
        "> A flag (PARTIAL / UNSUPPORTED / FABRICATED) means the figure does not fully "
        "support the claim. The verifier is calibrated to catch problems (high recall); "
        "treat a flag as a prompt to re-check, not a verdict on the science. Read the "
        "evidence anchors and adjudicate."
    )
    lines.append("")

    # Critical first: flagged claims, then clean.
    ordered = sorted(report.audits, key=lambda a: (not a.flagged, a.verdict))
    for a in ordered:
        mark = "⚠️" if a.flagged else "✅"
        lines.append(f"## {mark} {a.verdict} — `{a.figure}` (confidence {a.confidence:.2f})")
        lines.append("")
        lines.append(f"**Claim:** {a.claim}")
        lines.append("")
        lines.append("**Evidence anchors:**")
        for anchor in a.evidence_anchors:
            lines.append(f"- {anchor}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_audit_report(
    report: FigureAuditReport,
    out_dir: str | Path,
    *,
    slug: str,
    date_str: str,
    generated_by: str = "figure-audit",
) -> dict[str, Path]:
    """Write ``<slug>-<date>.json`` + ``.md`` + provenance receipts to ``out_dir``.

    ``date_str`` is supplied by the caller (the command computes today's date) so this
    function stays deterministic for tests. Returns the written paths.
    """
    from vaultlab.provenance import ProvenanceRecord, write_receipts

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"figure-audit-{slug}-{date_str}"

    json_path = out_dir / f"{stem}.json"
    json_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

    md_path = out_dir / f"{stem}.md"
    md_path.write_text(render_report_md(report), encoding="utf-8")

    record = ProvenanceRecord(
        generated_by="vaultlab.figures.verify_semantic.audit.audit_figure_claims",
        kind="figure_claim_audit",
        project=report.project,
        inputs=[a.figure for a in report.audits],
        model=report.model,
        params={
            "n_claims": report.n_claims,
            "n_flagged": report.n_flagged,
            "verdict_counts": report.verdict_counts,
            "overall": report.overall,
            "command": generated_by,
        },
        notes=(
            "Semantic figure-vs-claim audit (vaultlab.figures.verify_semantic). Discrete "
            "/figure-audit path; NOT the inline /lit-arc pass. Verdict ∈ "
            "SUPPORTED|PARTIAL|UNSUPPORTED|FABRICATED with figure-grounded evidence anchors."
        ),
    )
    write_receipts(str(md_path), record)

    return {"json": json_path, "md": md_path}


__all__ = [
    "ClaimAudit",
    "FigureAuditReport",
    "audit_figure_claims",
    "render_report_md",
    "write_audit_report",
]
