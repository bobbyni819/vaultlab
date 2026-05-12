"""HTML citation audit report.

Consumer #4 of ``vaultlab.report``. Renders an ``AuditReport`` (or a dict
shaped like its ``to_dict`` output) as a single-file HTML report with
filterable per-citation cards, status/risk chips, hallucination flags, and a
top-level action-items section.

Background: the citation audit's existing markdown output is a long table
that's hard to scan when there are 50+ citations. HTML adds: filter by
status (verified/unverified/suspect/contradicted) and risk (high/medium/low),
copy-DOI buttons, and an at-a-glance count summary.
"""

from __future__ import annotations

import html as _html
from pathlib import Path
from typing import Any

from vaultlab.report import components as c
from vaultlab.report import render_report

# Status → severity level
_STATUS_LEVEL = {
    "verified_fulltext": "good",
    "verified_abstract": "good",
    "api_confirmed": "warn",
    "unverified": "warn",
    "suspect": "bad",
    "contradicted": "bad",
}
# Risk → severity level
_RISK_LEVEL = {"low": "good", "medium": "warn", "high": "bad"}


def _safe(text: Any) -> str:
    return _html.escape(str(text or ""))


def _as_dict_audit(audit: Any) -> dict[str, Any]:
    """Normalize either an AuditReport dataclass or its dict to a dict."""
    if hasattr(audit, "to_dict"):
        return audit.to_dict()
    return dict(audit)


def _as_dict_citation(cit: Any) -> dict[str, Any]:
    if hasattr(cit, "to_dict"):
        return cit.to_dict()
    return dict(cit)


def _citation_card(cit: dict[str, Any]) -> str:
    status = cit.get("status") or "unverified"
    risk = cit.get("risk") or "medium"
    authors = cit.get("authors") or "(unknown)"
    year = cit.get("year")
    claim = cit.get("claim") or "(no claim text)"
    source = cit.get("source_file") or ""
    line = cit.get("line_number")
    doi = cit.get("doi") or ""
    title = cit.get("title") or ""
    flags = cit.get("hallucination_flags") or []

    badges: list[tuple[str, str]] = [
        (status.replace("_", " "), _STATUS_LEVEL.get(status, "neutral")),
        (f"{risk} risk", _RISK_LEVEL.get(risk, "neutral")),
    ]
    if doi:
        badges.append(("DOI", "neutral"))

    severity = _STATUS_LEVEL.get(status, "neutral")
    # Combined filter key: status + risk so users can filter both axes
    filter_keys = f"{status},risk-{risk}"
    if flags:
        filter_keys += ",has-flags"

    body_parts: list[str] = []
    citation_label = f"{_safe(authors)} ({year})" if year else _safe(authors)
    body_parts.append(
        f'<div style="font-size:12px;color:var(--muted);margin-bottom:6px;">'
        f"{citation_label}{f' — {_safe(title)}' if title else ''}</div>"
    )
    body_parts.append(f'<p style="margin:6px 0;">{_safe(claim)}</p>')
    if source:
        loc = f"{source}:{line}" if line is not None else source
        body_parts.append(
            f'<div style="font-size:11px;color:var(--muted);font-family:ui-monospace,Menlo,monospace;">'
            f"{_safe(loc)}</div>"
        )
    if flags:
        flag_html = "".join(
            f'<span style="display:inline-block;font-size:11px;margin:2px 4px 0 0;'
            f"padding:1px 6px;background:var(--bad-bg);color:var(--bad);"
            f'border:1px solid var(--bad-line);border-radius:3px;">{_safe(f)}</span>'
            for f in flags
        )
        body_parts.append(
            f'<div style="margin-top:8px;"><strong style="font-size:11px;color:var(--muted);">FLAGS:</strong> {flag_html}</div>'
        )

    actions: list[tuple[str, str]] = []
    if doi:
        actions.append(("Copy DOI", doi))
    if cit.get("raw_text"):
        actions.append(("Copy citation", cit["raw_text"]))

    return c.severity_card(
        f"{_safe(authors)} ({year})" if year else _safe(authors),
        body="".join(body_parts),
        severity=severity,
        badges=badges,
        actions=actions,
        filter_key=filter_keys,
    )


def build_citation_audit_html(
    audit: dict[str, Any] | Any,
    *,
    title: str | None = None,
) -> str:
    """Render a citation AuditReport as a single-file HTML string."""
    data = _as_dict_audit(audit)
    citations = data.get("citations", []) or []
    by_status = data.get("by_status", {}) or {}
    total = data.get("total", len(citations))
    high_risk = data.get("high_risk_unverified", 0)
    flags = data.get("hallucination_flags", []) or []
    actions = data.get("action_items", []) or []
    source_files = data.get("source_files", []) or []
    audit_date = data.get("audit_date", "")

    cits = [_as_dict_citation(c) for c in citations]

    # Header chips
    summary_chips = [c.status_chip(f"{total} citations", "neutral")]
    for status, count in by_status.items():
        if count:
            level = _STATUS_LEVEL.get(status, "neutral")
            summary_chips.append(c.status_chip(f"{status.replace('_', ' ')}: {count}", level))
    if high_risk:
        summary_chips.append(c.status_chip(f"{high_risk} high-risk unverified", "bad"))

    tldr_items = [
        f"Audited {total} citation{'s' if total != 1 else ''} across "
        f"{len(source_files)} source file{'s' if len(source_files) != 1 else ''}.",
    ]
    if high_risk:
        tldr_items.append(
            f"{high_risk} citation{'s' if high_risk != 1 else ''} are HIGH RISK and "
            "UNVERIFIED — review before publication."
        )
    if flags:
        tldr_items.append(
            f"{len(flags)} hallucination flag pattern{'s' if len(flags) != 1 else ''} detected."
        )

    # Filter bar buckets
    filter_buckets: list[tuple[str, str]] = [("All", "all")]
    for status in by_status:
        if by_status.get(status):
            label = status.replace("_", " ").title()
            filter_buckets.append((label, status))
    filter_buckets.append(("Has flags", "has-flags"))
    filter_buckets.append(("High risk", "risk-high"))

    citation_cards = [_citation_card(cit) for cit in cits]

    sections = [
        c.section(
            None,
            c.tldr_box(tldr_items),
            f'<div style="margin:14px 0;">{"".join(summary_chips)}</div>',
        ),
    ]

    if actions:
        action_rows = [[_safe(item)] for item in actions]
        sections.append(
            c.section(
                "Action items",
                c.matrix_table(["Recommended next step"], action_rows),
            )
        )

    sections.append(
        c.section(
            "Citations",
            c.filter_bar(
                filter_buckets,
                target_selector=".vl-cards .vl-card",
            ),
            c.card_grid(citation_cards) if citation_cards else "<p>No citations audited.</p>",
        ),
    )

    if flags:
        flag_rows = [[_safe(f)] for f in flags]
        sections.append(
            c.section(
                "Hallucination flag patterns",
                c.matrix_table(["Pattern"], flag_rows),
            )
        )

    return render_report(
        title=title or "Citation audit",
        eyebrow="vaultlab · citation audit",
        subtitle=(", ".join(source_files[:3]) + (" …" if len(source_files) > 3 else "")) or None,
        meta=f"{total} citations · audited {audit_date}" if audit_date else None,
        sections=sections,
    )


def write_citation_audit_html(
    out_path: Path | str,
    audit: dict[str, Any] | Any,
    **kwargs: Any,
) -> Path:
    """Render and write the citation-audit HTML report."""
    html_str = build_citation_audit_html(audit, **kwargs)
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html_str, encoding="utf-8")
    return p


__all__ = ["build_citation_audit_html", "write_citation_audit_html"]
