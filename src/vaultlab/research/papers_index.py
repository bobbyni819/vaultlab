"""Per-project papers index — a persistent, queryable manifest of a KB's paper corpus.

Motivation (Bobby, 2026-06-08): when papers are fetched across several runs, we want one
index file that records, per paper, its identity (title, DOI), whether a local PDF exists and
is readable, how thoroughly it has been read, and its citation-verification status. A later
agent reads the *index* to understand the corpus and only opens the full per-paper notes it
actually needs, instead of re-reading every PDF. The deep reading is done once, up front, and
captured in the per-paper note (``Sources/Papers/<slug>.md``); the index aggregates it.

This module is read-only over the corpus plus two additive writes (``_papers_index.json`` and
``_papers_index.md``). It never modifies existing per-paper notes or PDFs.

Status fields tracked per paper:
- ``pdf_present``      — a ``<slug>.pdf`` exists next to the note.
- ``pdf_readable``     — that PDF passes the ``%PDF-`` magic + minimum-size check (mirrors
                          ``acquisition._looks_like_pdf``); a False here means a paywall stub /
                          HTML landing page / truncated download, i.e. needs re-fetch.
- ``read_depth``       — none / noted / deep, inferred from the per-paper note's structure.
- ``verification``     — from the note's ``status:`` frontmatter (e.g. VERIFIED / UNVERIFIED).

The schema intentionally carries an ``extra`` dict so a project can record its own per-paper
fields (relevance-to-aim, tags, reading TODOs) without a schema change.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Mirrors acquisition._looks_like_pdf so the readability verdict is consistent with the fetcher.
_PDF_MAGIC = b"%PDF-"
_MIN_PDF_BYTES = 1024


@dataclass
class PaperEntry:
    """One paper in the corpus index. The digest + sections let an agent grasp the paper
    without opening the full note or the PDF."""

    slug: str
    title: str = ""
    authors: str = ""
    year: str = ""
    journal: str = ""
    doi: str = ""
    ref_number: str = ""
    note_path: str = ""
    pdf_path: str = ""
    pdf_present: bool = False
    pdf_readable: bool = False
    read_depth: str = "none"  # none | noted | deep
    verification: str = "UNVERIFIED"
    sections: list[str] = field(default_factory=list)  # the note's "## " headings — its organization
    digest: str = ""  # first prose paragraph of the note, the at-a-glance summary
    extra: dict = field(default_factory=dict)  # project-specific per-paper fields


def _pdf_readable(path: Path) -> bool:
    """True when the on-disk file is a structurally valid, non-stub PDF.

    Mirrors ``acquisition._looks_like_pdf`` but reads from disk: checks the ``%PDF-`` magic
    number and a minimum size, so paywall HTML stubs saved as ``.pdf`` read as unreadable.
    """
    try:
        if path.stat().st_size < _MIN_PDF_BYTES:
            return False
        with open(path, "rb") as fh:
            return fh.read(5) == _PDF_MAGIC
    except OSError:
        return False


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a markdown file into (frontmatter dict, body). Minimal flat YAML: ``key: value``,
    optionally quoted. Dependency-free so this works on any KB without PyYAML."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block = text[3:end].strip("\n")
    body = text[end + 4 :].lstrip("\n")
    fm: dict = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        val = val.strip()
        if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
            val = val[1:-1]
        fm[key.strip()] = val
    return fm, body


def _first_paragraph(body: str) -> str:
    """The first prose paragraph of the note — the at-a-glance digest. Skips leading heading
    lines (including a heading that sits directly above its prose with no blank line)."""
    para: list[str] = []
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            if para:
                break
            continue
        para.append(s)
    return re.sub(r"\s+", " ", " ".join(para))[:400]


def _infer_read_depth(sections: list[str], body: str) -> str:
    """Heuristic read depth from the note's structure. A deep read has several sections and
    quoted evidence; a thin note is merely 'noted'."""
    has_quote = '"' in body or "*“" in body or "*\"" in body
    if len(sections) >= 3 and has_quote:
        return "deep"
    if body.strip():
        return "noted"
    return "none"


def scan_paper_note(note_path: Path) -> PaperEntry:
    """Build a single PaperEntry from a ``<slug>.md`` note and its sibling ``<slug>.pdf``."""
    slug = note_path.stem
    text = note_path.read_text(encoding="utf-8", errors="replace")
    fm, body = _parse_frontmatter(text)
    sections = re.findall(r"^##\s+(.+?)\s*$", body, flags=re.MULTILINE)

    pdf_path = note_path.with_suffix(".pdf")
    present = pdf_path.exists()
    readable = _pdf_readable(pdf_path) if present else False

    return PaperEntry(
        slug=slug,
        title=fm.get("title", ""),
        authors=fm.get("authors", ""),
        year=str(fm.get("year", "")),
        journal=fm.get("journal", ""),
        doi=fm.get("doi", ""),
        ref_number=str(fm.get("ref_number", "")),
        note_path=note_path.name,
        pdf_path=pdf_path.name if present else "",
        pdf_present=present,
        pdf_readable=readable,
        read_depth=_infer_read_depth(sections, body),
        verification=(fm.get("status", "") or "UNVERIFIED").upper(),
        sections=sections,
        digest=_first_paragraph(body),
    )


@dataclass
class PapersIndex:
    papers_dir: str
    entries: list[PaperEntry] = field(default_factory=list)

    @property
    def counts(self) -> dict:
        return {
            "total": len(self.entries),
            "pdf_present": sum(e.pdf_present for e in self.entries),
            "pdf_unreadable": sum(e.pdf_present and not e.pdf_readable for e in self.entries),
            "no_pdf": sum(not e.pdf_present for e in self.entries),
            "verified": sum(e.verification == "VERIFIED" for e in self.entries),
            "deep_read": sum(e.read_depth == "deep" for e in self.entries),
        }


def build_papers_index(papers_dir: Path) -> PapersIndex:
    """Scan ``papers_dir`` (a ``Sources/Papers/`` folder) into a PapersIndex. Skips index files
    and files starting with ``_``."""
    papers_dir = Path(papers_dir)
    entries: list[PaperEntry] = []
    for note in sorted(papers_dir.glob("*.md")):
        if note.stem.startswith("_"):
            continue
        entries.append(scan_paper_note(note))
    return PapersIndex(papers_dir=str(papers_dir), entries=entries)


def render_index_markdown(index: PapersIndex) -> str:
    """Render the agent-readable ``_papers_index.md``: a status table plus per-paper digests."""
    c = index.counts
    lines = [
        "# Papers index",
        "",
        f"> Generated by `vaultlab.research.papers_index`. {c['total']} papers: "
        f"{c['pdf_present']} with PDF ({c['pdf_unreadable']} unreadable / need re-fetch), "
        f"{c['no_pdf']} without PDF; {c['verified']} verified; {c['deep_read']} deep-read. "
        "Read this file to understand the corpus; open a per-paper note only when you need its detail.",
        "",
        "| Paper | Year | PDF | Read | Verified | DOI |",
        "|---|---|---|---|---|---|",
    ]
    for e in index.entries:
        if not e.pdf_present:
            pdf = "missing"
        elif e.pdf_readable:
            pdf = "ok"
        else:
            pdf = "UNREADABLE"
        label = e.title or e.slug
        lines.append(
            f"| [{label}]({e.note_path}) | {e.year} | {pdf} | {e.read_depth} | "
            f"{e.verification} | {e.doi} |"
        )
    lines += ["", "## Per-paper digests", ""]
    for e in index.entries:
        lines.append(f"### {e.title or e.slug}")
        meta = " · ".join(x for x in [e.year, e.journal, f"ref [{e.ref_number}]" if e.ref_number else ""] if x)
        if meta:
            lines.append(f"*{meta}*")
        if e.digest:
            lines.append(e.digest)
        if e.sections:
            lines.append(f"_Sections: {', '.join(e.sections)}_")
        lines.append("")
    return "\n".join(lines)


def save_index(index: PapersIndex, papers_dir: Path | None = None) -> tuple[Path, Path]:
    """Write ``_papers_index.json`` (machine source of truth) and ``_papers_index.md`` (agent/human
    readable) into ``papers_dir``. Additive: writes only these two files."""
    out_dir = Path(papers_dir or index.papers_dir)
    json_path = out_dir / "_papers_index.json"
    md_path = out_dir / "_papers_index.md"
    payload = {"papers_dir": index.papers_dir, "counts": index.counts,
               "entries": [asdict(e) for e in index.entries]}
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_index_markdown(index), encoding="utf-8")
    return json_path, md_path
