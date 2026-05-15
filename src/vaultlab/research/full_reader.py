"""Bilingual, figure-aware, source-grounded full-paper Markdown reader.

Sub-goal 2.1 of the north-star plan absorbs the ``nature-reader`` skill
(``C:/Users/bobby/Downloads/nature-skills/skills/nature-reader/SKILL.md``)
into vaultlab. The goal: given a paper (PDF / DOI / arXiv ID / URL / pasted
text), produce a complete ``paper.md`` reading artifact that:

* Keeps the **full prose** with section structure intact (not a summary).
* Pairs **original text with a same-language translation** paragraph-by-
  paragraph (default target = ``zh-CN``; any ISO code accepted).
* Places **figures and tables near the discussion that introduces them**.
* Emits **stable anchor IDs** on every substantive block so downstream tools
  can cite by location:

  * ``S001``, ``S002``, … — body paragraphs
  * ``C001``, ``C002``, … — captions (abstract is C001)
  * ``F001``, ``F002``, … — figures
  * ``T001``, ``T002``, … — tables

* Writes the provenance receipts mandated by Red Line #2 (every artifact
  carries a manifest):

  * ``paper.md.provenance.json``
  * ``paper.md.method.md``

When to use this vs. neighbors
------------------------------

* :mod:`vaultlab.research.abstract_recall` — when you only need the abstract.
* :mod:`vaultlab.research.summarize` / batched reader — when you want a
  short structured summary (TL;DR, findings list).
* :mod:`vaultlab.research.full_reader` (this module) — when you want a
  **complete bilingual reading file** with section-grounded anchors and
  figures inline.

Architecture
------------

Two replaceable seams:

1. ``_extract_paper_content(source, paperclip_id=None) -> PaperContent``
   pulls structured blocks (abstract / body paragraphs / figures / tables)
   from the source. Real implementations would route through
   :mod:`vaultlab.research.read_paper`, paperclip, or
   :mod:`vaultlab.figures.acquisition`. Tests monkeypatch this for
   determinism — the framework is the deliverable here, not the real
   PDF parsing.

2. ``_translate_blocks(blocks, target_lang) -> list[str]`` is the LLM seam.
   The default implementation is an **identity passthrough** so the module
   degrades gracefully with no LLM wired up; production callers
   monkeypatch this to dispatch through their preferred backend (the
   nature-reader SKILL.md lists DeepSeek / GLM / Qwen / Kimi as
   OpenAI-compatible options).

Public API
----------

>>> from vaultlab.research.full_reader import build_paper_reader
>>> paper_md = build_paper_reader(
...     "10.1038/s41586-023-05915-x",
...     out_dir="reading/2026-paper",
...     target_lang="zh-CN",
... )
>>> paper_md.exists()
True
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vaultlab.provenance import ProvenanceRecord, write_receipts
from vaultlab.workflows.task_weight import (
    TaskSpec,
    Weight,
    classify,
    model_for_weight,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Block:
    """A single substantive block of paper content.

    Attributes
    ----------
    kind
        ``"body" | "abstract" | "caption" | "figure" | "table"``.
    text
        Original text (English, typically). For figure/table blocks, this is
        the caption.
    label
        Display label (e.g. ``"Introduction"``, ``"Figure 1"``, ``"Table 2"``).
        Section name for body blocks; figure/table label otherwise.
    asset
        For figure blocks: relative path to the figure file (e.g.
        ``"figures/fig_1.png"``). Empty for non-figure blocks.
    """

    kind: str
    text: str
    label: str = ""
    asset: str = ""


@dataclass(frozen=True)
class PaperContent:
    """Structured paper content prior to translation + rendering.

    Attributes
    ----------
    title
        Paper title.
    doi
        DOI string (no URL prefix).
    source
        Free-form source identifier (URL / path / paperclip-id) for the
        method.md narrative.
    abstract
        Original abstract text, or None if not available.
    body
        Ordered list of body paragraph blocks (kind=``body``).
    figures
        Ordered list of figure blocks (kind=``figure``, ``asset`` set).
    tables
        Ordered list of table blocks (kind=``table``).
    """

    title: str
    doi: str
    source: str
    abstract: str | None
    body: list[Block] = field(default_factory=list)
    figures: list[Block] = field(default_factory=list)
    tables: list[Block] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Extraction + translation seams (overridable for tests / production)
# ---------------------------------------------------------------------------


def _extract_paper_content(
    source: str,
    paperclip_id: str | None = None,
) -> PaperContent:
    """Pull structured content from a paper source.

    This is the integration seam for real PDF parsing / paperclip access /
    publisher HTML scraping. The default implementation refuses — the
    extraction layer is opt-in and must be supplied by the caller (or
    monkeypatched in tests). Returning an empty :class:`PaperContent` here
    would silently produce a useless ``paper.md``, which would violate
    Red Line #2 (no silent failures).

    Production callers monkeypatch this with a real implementation that
    dispatches through:

    * :func:`vaultlab.research.read_paper.read_paper_sections` for PDFs
    * paperclip MCP for the 8M-paper corpus
    * :func:`vaultlab.figures.acquisition.acquire_figures` for figures
    """
    raise NotImplementedError(
        "vaultlab.research.full_reader._extract_paper_content has no default "
        "implementation. Wire it to read_paper_sections / paperclip / "
        "figure-acquisition for production use, or monkeypatch in tests."
    )


def _translate_blocks(blocks: list[Block], target_lang: str) -> list[str]:
    """Translate a list of blocks into the target language.

    The default implementation is an **identity passthrough**: it returns
    the original text for each block, so the module never crashes when no
    LLM backend is configured. Real callers monkeypatch this to dispatch
    through their preferred LLM (DeepSeek / GLM / Qwen / Kimi /
    Anthropic / etc.) as described in nature-reader SKILL.md.

    The contract for replacements:

    * Input ``blocks`` and output list must be the same length and order.
    * Translate **for meaning**, not style. Preserve gene names, formulas,
      citations, units, hedging.
    * If a block cannot be confidently translated, return the original
      text verbatim (better than a hallucinated translation).
    """
    return [b.text for b in blocks]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_paper_md(
    content: PaperContent,
    *,
    translations: dict[str, list[str]],
    target_lang: str,
) -> str:
    """Render structured paper content into the bilingual ``paper.md``.

    Parameters
    ----------
    content
        The structured :class:`PaperContent`.
    translations
        Pre-translated text, keyed by section:

        * ``"abstract"`` — list of 0 or 1 strings (one per abstract block)
        * ``"body"`` — same length as ``content.body``
        * ``"figures"`` — same length as ``content.figures``
        * ``"tables"`` — same length as ``content.tables``

    target_lang
        ISO language code (e.g. ``"zh-CN"``, ``"ja"``). Used for the
        header annotation and the "翻译" callout (we use the literal
        word "translation" rather than a per-language word to keep the
        renderer language-neutral).

    Returns
    -------
    str
        The complete ``paper.md`` content.
    """
    from datetime import datetime, timezone

    lines: list[str] = []
    lines.append(f"# {content.title}")
    lines.append("")
    if content.doi:
        lines.append(f"**DOI:** {content.doi}")
    if content.source:
        lines.append(f"**Source:** {content.source}")
    lines.append(f"**Target language:** {target_lang}")
    lines.append(f"**Generated:** {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    lines.append("")

    # Abstract — C001
    abs_tr = translations.get("abstract", [])
    if content.abstract:
        lines.append('## Abstract <a id="C001"></a>')
        lines.append("")
        lines.append(f"> {content.abstract}")
        if abs_tr:
            lines.append(">")
            lines.append(f"> **Translation ({target_lang}):** {abs_tr[0]}")
        lines.append("")

    # Body — S001, S002, ...
    body_tr = translations.get("body", [])
    figures_tr = translations.get("figures", [])
    tables_tr = translations.get("tables", [])

    # We render body paragraphs in order, and after each one we *try* to
    # surface figures/tables whose label appears in the paragraph text.
    # Anything left over is appended at the end so nothing is dropped —
    # nature-reader's contract is "near the relevant discussion" not
    # "perfect semantic placement".
    figures_remaining = list(enumerate(content.figures))
    tables_remaining = list(enumerate(content.tables))

    for i, block in enumerate(content.body, start=1):
        anchor = f"S{i:03d}"
        section_label = block.label or "Body"
        lines.append(f"## {section_label} <a id=\"{anchor}\"></a>")
        lines.append("")
        lines.append(f"> {block.text}")
        if i - 1 < len(body_tr):
            lines.append(">")
            lines.append(f"> **Translation ({target_lang}):** {body_tr[i - 1]}")
        lines.append("")

        # Anchor figures/tables whose label is mentioned in this paragraph.
        figures_remaining, attached_figs = _pop_referenced(figures_remaining, block.text)
        for orig_idx, fig in attached_figs:
            tr = figures_tr[orig_idx] if orig_idx < len(figures_tr) else ""
            lines.extend(_render_figure(fig, orig_idx, tr, target_lang))

        tables_remaining, attached_tables = _pop_referenced(tables_remaining, block.text)
        for orig_idx, tab in attached_tables:
            tr = tables_tr[orig_idx] if orig_idx < len(tables_tr) else ""
            lines.extend(_render_table(tab, orig_idx, tr, target_lang))

    # Anything left over (no body reference detected, or no body at all)
    # is appended at the end so nothing is silently dropped.
    for orig_idx, fig in figures_remaining:
        tr = figures_tr[orig_idx] if orig_idx < len(figures_tr) else ""
        lines.extend(_render_figure(fig, orig_idx, tr, target_lang))
    for orig_idx, tab in tables_remaining:
        tr = tables_tr[orig_idx] if orig_idx < len(tables_tr) else ""
        lines.extend(_render_table(tab, orig_idx, tr, target_lang))

    return "\n".join(lines).rstrip() + "\n"


def _pop_referenced(
    remaining: list[tuple[int, Block]],
    body_text: str,
) -> tuple[list[tuple[int, Block]], list[tuple[int, Block]]]:
    """Split ``remaining`` into (still-remaining, just-attached).

    "Just-attached" = labels whose case-insensitive label appears in the body
    paragraph. Used to honor nature-reader's "place figures near the relevant
    discussion" rule without trying to be too clever about it.
    """
    text_lower = body_text.lower()
    keep: list[tuple[int, Block]] = []
    take: list[tuple[int, Block]] = []
    for entry in remaining:
        _idx, block = entry
        label_lower = (block.label or "").lower().strip()
        if label_lower and label_lower in text_lower:
            take.append(entry)
        else:
            keep.append(entry)
    return keep, take


def _render_figure(
    fig: Block,
    zero_based_idx: int,
    translation: str,
    target_lang: str,
) -> list[str]:
    anchor = f"F{zero_based_idx + 1:03d}"
    label = fig.label or f"Figure {zero_based_idx + 1}"
    out: list[str] = []
    out.append(f"### {label} <a id=\"{anchor}\"></a>")
    out.append("")
    if fig.asset:
        out.append(f"![{label}]({fig.asset})")
        out.append("")
    out.append(f"**Caption (original):** {fig.text}")
    if translation:
        out.append(f"**Caption (translated, {target_lang}):** {translation}")
    out.append("")
    return out


def _render_table(
    tab: Block,
    zero_based_idx: int,
    translation: str,
    target_lang: str,
) -> list[str]:
    anchor = f"T{zero_based_idx + 1:03d}"
    label = tab.label or f"Table {zero_based_idx + 1}"
    out: list[str] = []
    out.append(f"### {label} <a id=\"{anchor}\"></a>")
    out.append("")
    out.append(f"**Caption (original):** {tab.text}")
    if translation:
        out.append(f"**Caption (translated, {target_lang}):** {translation}")
    out.append("")
    return out


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def build_paper_reader(
    source: Path | str,
    *,
    out_dir: Path | str,
    target_lang: str = "zh-CN",
    paperclip_id: str | None = None,
    weight: Weight | None = None,
) -> Path:
    """Turn a paper into a bilingual figure-aware Markdown reading file.

    Implements the ``nature-reader`` skill contract on top of vaultlab
    primitives: extraction is delegated to :func:`_extract_paper_content`
    (production callers wire it to PDF/paperclip/figure-acquisition);
    translation is delegated to :func:`_translate_blocks` (default is an
    identity passthrough so the module never crashes without an LLM).

    Parameters
    ----------
    source
        Path to PDF, DOI string, arXiv ID, publisher URL, or arbitrary
        identifier handed to :func:`_extract_paper_content`.
    out_dir
        Directory where ``paper.md`` and its provenance sidecars are
        written. Created if missing.
    target_lang
        Translation target language (ISO code, e.g. ``"zh-CN"``, ``"ja"``,
        ``"es"``). Default ``"zh-CN"`` matches the nature-reader contract.
    paperclip_id
        Optional paperclip corpus ID. Forwarded to
        :func:`_extract_paper_content` so production callers can bypass
        re-parsing when the paper is already in the paperclip filesystem.
    weight
        Optional explicit task weight (``"light"`` / ``"medium"`` /
        ``"heavy"``). When ``None`` (the default), the SPEC-F dispatcher
        in :mod:`vaultlab.workflows.task_weight` auto-classifies the task
        as ``"medium"`` (single-paper read). The resolved model id is
        recorded in the provenance manifest under ``model`` and
        ``params["weight"]``.

    Returns
    -------
    pathlib.Path
        Absolute path to the generated ``paper.md``.

    Side effects
    ------------
    Writes three files per Red Line #2 (no silent failures):

    * ``<out_dir>/paper.md``
    * ``<out_dir>/paper.md.provenance.json``
    * ``<out_dir>/paper.md.method.md``

    Also appends a JSONL line to ``<out_dir>/.vaultlab-provenance.jsonl``.
    """
    out_dir_path = Path(out_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)

    source_str = str(source)
    content = _extract_paper_content(source_str, paperclip_id=paperclip_id)

    # SPEC-F: route via task-weight dispatcher. Single-paper bilingual
    # reads classify as ``medium`` by default (one input, summarize-class
    # work); callers may force a tier via the ``weight`` kwarg.
    resolved_weight: Weight = (
        weight
        if weight is not None
        else classify(TaskSpec(kind="single_paper_read", n_inputs=1))
    )
    resolved_model = model_for_weight(resolved_weight)

    translations: dict[str, list[str]] = {
        "abstract": (
            _translate_blocks(
                [Block(kind="abstract", text=content.abstract or "")],
                target_lang,
            )
            if content.abstract
            else []
        ),
        "body": _translate_blocks(list(content.body), target_lang) if content.body else [],
        "figures": _translate_blocks(list(content.figures), target_lang) if content.figures else [],
        "tables": _translate_blocks(list(content.tables), target_lang) if content.tables else [],
    }

    md_text = render_paper_md(content, translations=translations, target_lang=target_lang)
    output_path = out_dir_path / "paper.md"
    output_path.write_text(md_text, encoding="utf-8")

    record = ProvenanceRecord(
        generated_by="vaultlab.research.full_reader.build_paper_reader",
        kind="paper_reader",
        inputs=[source_str],
        model=resolved_model,
        params={
            "target_lang": target_lang,
            "paperclip_id": paperclip_id or "",
            "n_body_blocks": len(content.body),
            "n_figures": len(content.figures),
            "n_tables": len(content.tables),
            "has_abstract": content.abstract is not None,
            "doi": content.doi,
            "title": content.title,
            # SPEC-F task-weight dispatch
            "weight": resolved_weight,
            "model": resolved_model,
        },
        notes=(
            "Generated by vaultlab.research.full_reader (nature-reader skill "
            "absorbed in sub-goal 2.1). Paper.md uses bilingual paragraph "
            "alignment with stable anchor IDs (S/C/F/T) for source grounding."
        ),
    )
    write_receipts(str(output_path), record)

    return output_path


__all__ = [
    "Block",
    "PaperContent",
    "build_paper_reader",
    "render_paper_md",
]
