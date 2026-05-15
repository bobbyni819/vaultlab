"""End-to-end manuscript-section drafting workflow.

Pipeline
--------
1. Read a bullet outline (``inputs/outline.md``) and a set of figure images
   (``inputs/figures/*.png``).
2. Compose a draft Results section by assembling the outline + figure
   callouts. The LLM-driven polish step is replaced with a deterministic
   mock that applies a subset of :mod:`vaultlab.manuscript.polish` rules —
   examples must not block on missing API keys.
3. Run :func:`vaultlab.citations.audit_file` over the draft and dump the
   :class:`AuditReport` as JSON for inspection.

Run
---

.. code-block:: bash

    python run.py

Outputs
-------
- ``out/section.md``         — the assembled + lightly-polished section
- ``out/section.audit.json`` — citation audit of the section
- ``out/polish_findings.md`` — long-sentence + US-spelling findings

Adapt this
----------
Replace ``inputs/outline.md`` and ``inputs/figures/`` with your own.
Required outline format: markdown with `[FIG:<id>]` placeholders that map
to figure filenames under ``inputs/figures/``.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
if (_REPO_ROOT / "src" / "vaultlab" / "__init__.py").exists():
    sys.path.insert(0, str(_REPO_ROOT / "src"))

logger = logging.getLogger("manuscript-section-example")


def _load_outline() -> str:
    return (_HERE / "inputs" / "outline.md").read_text(encoding="utf-8")


def _figure_files() -> list[Path]:
    fig_dir = _HERE / "inputs" / "figures"
    return sorted(fig_dir.glob("*.png"))


def _expand_fig_callouts(outline: str, figures: list[Path]) -> str:
    """Replace ``[FIG:<id>]`` tokens with full callouts.

    The mapping is positional: ``[FIG:1]`` → first file, ``[FIG:2]`` → second.
    """
    by_idx = {str(i + 1): p for i, p in enumerate(figures)}

    def replace(m: re.Match[str]) -> str:
        idx = m.group(1)
        path = by_idx.get(idx)
        if path is None:
            return f"[FIG:{idx} — file missing]"
        return f"(Figure {idx}; see `{path.name}`)"

    return re.sub(r"\[FIG:(\d+)\]", replace, outline)


def _mock_polish(text: str) -> str:
    """Stand-in for an LLM polishing pass.

    Applies two deterministic transforms:

    - tighten common over-hedged phrasing
    - normalize a few US-spellings to British English (the polish module
      ships a much larger table; this is a representative slice).
    """
    out = text
    # Tighten classic over-hedging
    out = re.sub(r"\bit is important to note that\b", "Notably,", out, flags=re.IGNORECASE)
    out = re.sub(r"\bin order to\b", "to", out, flags=re.IGNORECASE)
    out = re.sub(r"\bdue to the fact that\b", "because", out, flags=re.IGNORECASE)
    out = re.sub(r"\bvery significant\b", "significant", out, flags=re.IGNORECASE)
    # A taste of British English (the manuscript.polish module has 60+ pairs)
    for us, uk in (
        ("color", "colour"),
        ("colors", "colours"),
        ("analyze", "analyse"),
        ("analyzed", "analysed"),
        ("characterize", "characterise"),
        ("characterized", "characterised"),
    ):
        out = re.sub(rf"\b{us}\b", uk, out, flags=re.IGNORECASE)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=_HERE / "out")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Assemble outline + figure callouts
    outline = _load_outline()
    figures = _figure_files()
    if not figures:
        logger.warning("No figures found in inputs/figures/ — running outline-only")
    assembled = _expand_fig_callouts(outline, figures)
    logger.info("Assembled outline (%d chars, %d figures)", len(assembled), len(figures))

    # 2. Polish pass (mocked — no LLM dependency)
    polished = _mock_polish(assembled)

    section_path = out_dir / "section.md"
    section_path.write_text(polished, encoding="utf-8")
    logger.info("Wrote %s", section_path)

    # 3. Polish findings — surface long sentences + remaining US spellings
    from vaultlab.manuscript.polish import check_sentence_length, check_us_spelling

    long_sents = check_sentence_length(polished, max_words=30)
    us_words = check_us_spelling(polished)

    findings_path = out_dir / "polish_findings.md"
    lines = ["# Polish findings", "", f"**Source:** `{section_path.name}`", ""]
    lines.append(f"## Long sentences (>30 words): {len(long_sents)}")
    lines.append("")
    for idx, n_words, sent in long_sents:
        lines.append(f"- Sentence {idx} ({n_words} words): `{sent[:120]}...`")
    lines.append("")
    lines.append(f"## Residual US spellings: {len(us_words)}")
    lines.append("")
    for us, uk in us_words:
        lines.append(f"- `{us}` → `{uk}`")
    findings_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote %s", findings_path)

    # 4. Citation audit (no research_client → extracts but does not verify)
    from vaultlab.citations import audit_file

    audit = audit_file(str(section_path))
    audit_path = out_dir / "section.audit.json"
    audit_path.write_text(json.dumps(audit.to_dict(), indent=2), encoding="utf-8")
    logger.info(
        "Wrote %s (%d citations, %d action items)",
        audit_path,
        audit.total,
        len(audit.action_items),
    )

    logger.info("")
    logger.info("Done. Outputs:")
    logger.info("  - %s", section_path)
    logger.info("  - %s", findings_path)
    logger.info("  - %s", audit_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
