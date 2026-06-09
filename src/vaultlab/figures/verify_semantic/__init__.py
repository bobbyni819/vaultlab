"""Figure-vs-claim semantic verifier (prototype).

See :mod:`vaultlab.figures.verify_semantic.verifier` and the sibling ``prompt.md``.
Prototype only — NOT wired into ``/lit-arc`` or any ``/figure-audit`` command. The
invocation-path decision is results-gated (see the benchmark report under
``<kb>/<project>/Output/figure-claim-verifier-*``).
"""

from vaultlab.figures.verify_semantic.audit import (
    ClaimAudit,
    FigureAuditReport,
    audit_figure_claims,
    render_report_md,
    write_audit_report,
)
from vaultlab.figures.verify_semantic.verifier import (
    DEFAULT_MODEL,
    VERDICT_SCHEMA,
    VERDICT_VALUES,
    SchemaViolation,
    build_request,
    validate_verdict,
    verify_figure_claim,
)

__all__ = [
    "DEFAULT_MODEL",
    "VERDICT_VALUES",
    "VERDICT_SCHEMA",
    "SchemaViolation",
    "build_request",
    "validate_verdict",
    "verify_figure_claim",
    "ClaimAudit",
    "FigureAuditReport",
    "audit_figure_claims",
    "render_report_md",
    "write_audit_report",
]
