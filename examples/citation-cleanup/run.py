"""Citation extraction + remediation report.

Pipeline
--------
1. Extract every citation from a draft markdown file
   (``inputs/draft.md``) using :func:`vaultlab.citations.extract_citations`.
2. Without making any API calls, classify each citation by *quality
   signal*:
   - DOI present ↔ no DOI
   - DOI is well-formed ↔ malformed (e.g. wrong prefix, missing ``/``)
   - Year is plausible (1800 ≤ y ≤ current_year+1)
3. Emit a remediation markdown report grouping each citation by its
   suggested next action.

This is the mechanical step that runs before any LLM- or
research-client-driven verification — it's deterministic, fast, and a
good entry point for new contributors who want to extend the
classification heuristics.

Run
---

.. code-block:: bash

    python run.py

Outputs
-------
- ``out/audit_report.md`` — human-readable remediation report
- ``out/audit_report.json`` — same data, machine-readable

Adapt this
----------
Swap ``inputs/draft.md`` for any markdown file with citations. To
extend, add new classifier rules in ``_classify`` below — anything that
returns a ``(severity, action)`` tuple becomes a new column in the
report.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
if (_REPO_ROOT / "src" / "vaultlab" / "__init__.py").exists():
    sys.path.insert(0, str(_REPO_ROOT / "src"))

logger = logging.getLogger("citation-cleanup-example")


_DOI_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)


def _classify(citation, current_year: int) -> tuple[str, str]:
    """Return ``(severity, action)`` for a citation.

    Severity values: ``ok`` / ``review`` / ``critical``.
    """
    # DOI present — check shape
    if citation.doi:
        if _DOI_RE.match(citation.doi):
            return ("ok", "DOI well-formed; verify against CrossRef in real run")
        return ("critical", f"Malformed DOI `{citation.doi}` — fix prefix/slash before verification")

    # No DOI — check year plausibility
    if citation.year and (citation.year < 1800 or citation.year > current_year + 1):
        return ("critical", f"Year {citation.year} is implausible — possible hallucination")

    # No DOI, plausible year, has author
    if citation.authors:
        return ("review", "Add DOI before publication; author-year alone cannot be verified")

    return ("review", "Citation parsed without authors — re-check source markdown")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=_HERE / "out")
    parser.add_argument(
        "--draft",
        type=Path,
        default=_HERE / "inputs" / "draft.md",
        help="path to the draft markdown to audit",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    from vaultlab.citations import extract_citations

    citations = extract_citations(str(args.draft))
    logger.info("Extracted %d citations from %s", len(citations), args.draft.name)

    today = dt.date.today()
    classified = [(_classify(c, today.year), c) for c in citations]

    # Severity buckets
    by_sev = {"ok": [], "review": [], "critical": []}
    for (sev, action), c in classified:
        by_sev[sev].append((c, action))

    # JSON dump
    json_payload = {
        "source": str(args.draft),
        "audit_date": today.isoformat(),
        "total": len(citations),
        "counts": {sev: len(items) for sev, items in by_sev.items()},
        "citations": [
            {
                "raw_text": c.raw_text,
                "authors": c.authors,
                "year": c.year,
                "doi": c.doi,
                "pmid": c.pmid,
                "line_number": c.line_number,
                "severity": sev,
                "action": action,
            }
            for (sev, action), c in classified
        ],
    }
    json_path = out_dir / "audit_report.json"
    json_path.write_text(json.dumps(json_payload, indent=2), encoding="utf-8")

    # Markdown report
    lines: list[str] = [
        "# Citation cleanup report",
        "",
        f"**Source:** `{args.draft.name}`  ",
        f"**Audit date:** {today.isoformat()}  ",
        f"**Total citations:** {len(citations)}",
        "",
        "## Summary",
        "",
        f"- Critical (must fix before publication): **{len(by_sev['critical'])}**",
        f"- Review (verify before publication): **{len(by_sev['review'])}**",
        f"- OK (well-formed; pending API verification): **{len(by_sev['ok'])}**",
        "",
    ]
    for sev_label, sev_key in (
        ("Critical", "critical"),
        ("Review", "review"),
        ("OK", "ok"),
    ):
        items = by_sev[sev_key]
        lines.append(f"## {sev_label} — {len(items)} citation(s)")
        lines.append("")
        if not items:
            lines.append("_None._")
            lines.append("")
            continue
        for c, action in items:
            ident = c.doi or c.pmid or f"{c.authors} ({c.year})"
            lines.append(
                f"- **{c.raw_text}** (line {c.line_number}) — `{ident}`"
                f"\n  - {action}"
            )
        lines.append("")

    # Per-line summary table
    lines.append("## Per-citation classification")
    lines.append("")
    lines.append("| line | citation | severity | action |")
    lines.append("|---|---|---|---|")
    for (sev, action), c in classified:
        cite_short = c.raw_text.replace("|", "\\|")
        action_short = action.replace("|", "\\|")
        lines.append(f"| {c.line_number} | `{cite_short}` | {sev} | {action_short} |")
    lines.append("")

    # Remediation pointers
    lines.append("## Next steps")
    lines.append("")
    lines.append(
        "Run a verifying audit with full API access by wiring a research client:"
    )
    lines.append("")
    lines.append("```python")
    lines.append("from vaultlab.research import ResearchClient")
    lines.append("from vaultlab.citations import audit_file")
    lines.append("")
    lines.append("report = audit_file(")
    lines.append(f"    '{args.draft.name}',")
    lines.append("    research_client=ResearchClient(),")
    lines.append("    kb_dir='G:/My Drive/Knowledge/<kb-name>',")
    lines.append(")")
    lines.append("print(report.action_items)")
    lines.append("```")
    lines.append("")
    counts = Counter(sev for (sev, _), _ in classified)
    lines.append(f"_Bucket counts: {dict(counts)}_")
    lines.append("")

    md_path = out_dir / "audit_report.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    logger.info("")
    logger.info("Done. Outputs:")
    logger.info("  - %s  (%d critical, %d review, %d ok)",
                md_path, len(by_sev["critical"]), len(by_sev["review"]), len(by_sev["ok"]))
    logger.info("  - %s", json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
