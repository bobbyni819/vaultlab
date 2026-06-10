"""Per-KB papers ledger — the source-of-truth manifest of a KB's paper corpus.

Motivation (Bobby, 2026-06-08 / decided 2026-06-10): when papers are fetched and read
across several runs, we want **one index file** that records, per paper, its identity
(title, DOI), whether a local PDF exists and is *readable*, the exact PDF it was built
from (a content hash), how thoroughly it has been read, and its verification status. A
later agent reads the *index* to understand the whole corpus and only opens the per-paper
summaries it actually needs — instead of re-reading every PDF. The deep reading is done
once, up front, and the index aggregates it so re-runs are delta-only.

**Design decision (2026-06-10): the ledger is the source of truth, enumerated from disk.**
``scan_corpus`` walks the *actual* artifacts the pipeline writes —
``Sources/Papers/<slug>.pdf`` (raw PDFs from the acquisition waterfall) JOINed to
``Wiki/Summaries/<slug>.md`` (LLM-written summaries) on the shared DOI-slug
(:func:`vaultlab.kb.paths.slugify_doi`). It does NOT glob per-paper ``*.md`` notes the
pipeline never writes (the fatal bug in the earlier ``feat/writing-citation-practices``
draft, which would index zero rows on a real corpus).

Because the ledger is always rebuilt from disk, it cannot silently drift: it reflects what
is actually on disk at scan time. Two additive writes only (``_papers_index.json`` +
``_papers_index.md``); it never modifies a PDF or a summary.

What each row tells you:
- ``pdf_present``   — a ``<slug>.pdf`` exists in ``Sources/Papers/``.
- ``pdf_readable``  — that PDF passes the ``%PDF-`` magic + minimum-size check (mirrors
                       ``acquisition._looks_like_pdf``); ``False`` means a paywall stub /
                       HTML landing page / truncated download → needs re-fetch.
- ``pdf_sha256``    — content hash of the on-disk PDF; the gate that makes summarization
                       idempotent (re-read only when the PDF actually changed).
- ``read_depth``    — ``none`` (fetched, not yet read) / ``abstract`` (Tier-C stub) /
                       ``full`` (Tier-A/B full text read) / ``grounded`` (claims checked
                       against the PDF). The reading ladder.
- ``verification``  — ``VERIFIED`` / ``UNVERIFIED`` etc., from the summary's ``status:``
                       frontmatter; absent → ``UNVERIFIED`` (honest default until checked).

The idempotency query helpers (:func:`needs_fetch`, :func:`needs_summary`,
:func:`summary_is_current`) are what fetch and summarization consult so a multi-run workflow
skips work already done.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Mirrors acquisition._looks_like_pdf so the readability verdict here agrees with the fetcher.
_PDF_MAGIC = b"%PDF-"
_MIN_PDF_BYTES = 1024

# The read-depth ladder (decision 2026-06-10: tiered + idempotent reading).
READ_DEPTHS = ("none", "abstract", "full", "grounded")
_DEPTH_RANK = {d: i for i, d in enumerate(READ_DEPTHS)}


# ---------------------------------------------------------------------------
# Row schema
# ---------------------------------------------------------------------------


@dataclass
class PaperEntry:
    """One paper in the corpus ledger. The digest + sections let an agent grasp the paper
    without opening the full summary or the PDF."""

    slug: str
    doi: str = ""
    title: str = ""
    authors: str = ""
    year: str = ""
    journal: str = ""

    # PDF state (Sources/Papers/<slug>.pdf)
    pdf_present: bool = False
    pdf_readable: bool = False
    pdf_path: str = ""  # KB-relative
    pdf_sha256: str = ""  # content hash of the on-disk PDF ("" if absent/unhashed)
    pdf_bytes: int = 0

    # Summary state (Wiki/Summaries/<slug>.md)
    summary_present: bool = False
    summary_path: str = ""  # KB-relative
    summary_pdf_sha256: str = ""  # the PDF hash the summary was built from (frontmatter)
    tier: str = ""  # A / B / C from the summary frontmatter

    # Derived reading / trust state
    read_depth: str = "none"  # none | abstract | full | grounded
    verification: str = "UNVERIFIED"
    acquisition_source: str = ""  # waterfall tier recorded by the summarizer
    last_verified: str = ""  # ISO timestamp of the last readability/verification stamp

    # At-a-glance content (from the summary, when present)
    sections: list[str] = field(default_factory=list)
    digest: str = ""

    extra: dict = field(default_factory=dict)  # project-specific per-paper fields

    @property
    def summary_current(self) -> bool:
        """True when the summary was built from the PDF currently on disk.

        Requires a present summary, a hashed present PDF, and an exact hash match. When
        ``True``, re-reading the PDF would reproduce the same summary — so the read can be
        skipped (idempotent reading).
        """
        return bool(
            self.summary_present
            and self.pdf_sha256
            and self.pdf_sha256 == self.summary_pdf_sha256
        )

    @property
    def needs_refetch(self) -> bool:
        """True when there is no usable PDF: none present, or one present but unreadable
        (a stub / truncated download that should be re-fetched)."""
        return (not self.pdf_present) or (self.pdf_present and not self.pdf_readable)


# ---------------------------------------------------------------------------
# Disk readers (dependency-free so this works on any KB without PyYAML)
# ---------------------------------------------------------------------------


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


def _pdf_sha256(path: Path) -> str:
    """SHA-256 of a file, read in chunks. Empty string on any read error."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


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
    """The first prose paragraph of a summary — the at-a-glance digest. Skips leading heading
    lines (including a heading sitting directly above its prose with no blank line)."""
    para: list[str] = []
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            if para:
                break
            continue
        para.append(s)
    return re.sub(r"\s+", " ", " ".join(para))[:400]


def _slug_to_doi(slug: str) -> str:
    """Best-effort inverse of ``slugify_doi`` for PDF-only rows that have no summary metadata.

    ``10.1016_j.cell.2018.07.010`` -> ``10.1016/j.cell.2018.07.010``. Mirrors
    ``claim_verification._slug_to_doi`` (kept local so this module stays dependency-free).
    Only the registrant-boundary ``_`` is restored to ``/``; the rest is left verbatim.
    """
    s = slug.strip()
    parts = s.split("_", 1)
    if len(parts) != 2:
        return s.lower()
    return (parts[0] + "/" + parts[1]).lower()


def _read_depth(summary_present: bool, fm: dict, sections: list[str], body: str) -> str:
    """Place a paper on the reading ladder from its summary's structure + frontmatter."""
    if not summary_present:
        return "none"
    if str(fm.get("grounded", "")).strip().lower() in ("true", "yes", "1"):
        return "grounded"
    tier = (fm.get("tier", "") or "").strip().upper()
    if tier in ("A", "B"):
        return "full"
    if tier == "C":
        return "abstract"
    # No tier recorded: infer from the body. A real read has sections + substantial prose.
    if sections and len(body.strip()) > 200:
        return "full"
    return "abstract" if body.strip() else "none"


# ---------------------------------------------------------------------------
# Per-paper scan + corpus scan
# ---------------------------------------------------------------------------


def scan_paper(
    slug: str,
    *,
    papers_dir: Path,
    summaries_dir: Path,
    hash_pdfs: bool = True,
) -> PaperEntry:
    """Build one :class:`PaperEntry` by joining a PDF and a summary that share ``slug``."""
    pdf_file = papers_dir / f"{slug}.pdf"
    summary_file = summaries_dir / f"{slug}.md"

    pdf_present = pdf_file.exists()
    pdf_readable = _pdf_readable(pdf_file) if pdf_present else False
    pdf_bytes = pdf_file.stat().st_size if pdf_present else 0
    pdf_sha = _pdf_sha256(pdf_file) if (pdf_present and pdf_readable and hash_pdfs) else ""

    summary_present = summary_file.exists()
    fm: dict = {}
    body = ""
    sections: list[str] = []
    if summary_present:
        text = summary_file.read_text(encoding="utf-8", errors="replace")
        fm, body = _parse_frontmatter(text)
        sections = re.findall(r"^##\s+(.+?)\s*$", body, flags=re.MULTILINE)

    doi = fm.get("doi", "") or (_slug_to_doi(slug) if not summary_present else "")

    return PaperEntry(
        slug=slug,
        doi=doi,
        title=fm.get("title", ""),
        authors=str(fm.get("authors", "")),
        year=str(fm.get("year", "")),
        journal=fm.get("journal", ""),
        pdf_present=pdf_present,
        pdf_readable=pdf_readable,
        pdf_path=f"Sources/Papers/{slug}.pdf" if pdf_present else "",
        pdf_sha256=pdf_sha,
        pdf_bytes=pdf_bytes,
        summary_present=summary_present,
        summary_path=f"Wiki/Summaries/{slug}.md" if summary_present else "",
        summary_pdf_sha256=fm.get("source_pdf_sha256", ""),
        tier=(fm.get("tier", "") or "").strip().upper(),
        read_depth=_read_depth(summary_present, fm, sections, body),
        verification=(fm.get("status", "") or "UNVERIFIED").strip().upper(),
        acquisition_source=fm.get("acquisition_source", ""),
        last_verified=fm.get("extracted_at", ""),
        sections=sections,
        digest=_first_paragraph(body),
    )


@dataclass
class PapersIndex:
    kb_root: str
    entries: list[PaperEntry] = field(default_factory=list)

    @property
    def counts(self) -> dict:
        return {
            "total": len(self.entries),
            "pdf_present": sum(e.pdf_present for e in self.entries),
            "pdf_unreadable": sum(e.pdf_present and not e.pdf_readable for e in self.entries),
            "no_pdf": sum(not e.pdf_present for e in self.entries),
            "summarized": sum(e.summary_present for e in self.entries),
            "read_none": sum(e.read_depth == "none" for e in self.entries),
            "read_abstract": sum(e.read_depth == "abstract" for e in self.entries),
            "read_full": sum(e.read_depth == "full" for e in self.entries),
            "read_grounded": sum(e.read_depth == "grounded" for e in self.entries),
            "verified": sum(e.verification == "VERIFIED" for e in self.entries),
        }

    @property
    def by_slug(self) -> dict[str, PaperEntry]:
        return {e.slug: e for e in self.entries}

    def entry_for_doi(self, doi: str) -> PaperEntry | None:
        from vaultlab.kb.paths import slugify_doi

        if not doi:
            return None
        return self.by_slug.get(slugify_doi(doi))

    def reading_backlog(self) -> list[PaperEntry]:
        """Papers with a readable PDF on disk but not yet read full-text — the work queue."""
        return [
            e for e in self.entries if e.pdf_present and e.pdf_readable and e.read_depth in ("none", "abstract")
        ]

    def needs_refetch(self) -> list[PaperEntry]:
        """Papers whose PDF is missing or an unreadable stub — the re-fetch queue."""
        return [e for e in self.entries if e.needs_refetch]


def scan_corpus(kb_root: Path, *, hash_pdfs: bool = True) -> PapersIndex:
    """Scan a KB's corpus into a :class:`PapersIndex`.

    Enumerates the union of ``Sources/Papers/*.pdf`` and ``Wiki/Summaries/*.md`` (skipping
    ``_``-prefixed files such as the index itself) and joins them on DOI-slug. A bare fetched
    PDF with no summary shows as ``pdf_present=True, read_depth='none'`` — i.e. it surfaces the
    reading backlog rather than hiding it.

    Set ``hash_pdfs=False`` to skip content hashing (faster; disables the summary-currency check).
    """
    kb_root = Path(kb_root)
    papers_dir = kb_root / "Sources" / "Papers"
    summaries_dir = kb_root / "Wiki" / "Summaries"

    pdf_slugs = {p.stem for p in papers_dir.glob("*.pdf")} if papers_dir.exists() else set()
    summary_slugs = (
        {p.stem for p in summaries_dir.glob("*.md") if not p.stem.startswith("_")}
        if summaries_dir.exists()
        else set()
    )

    entries = [
        scan_paper(slug, papers_dir=papers_dir, summaries_dir=summaries_dir, hash_pdfs=hash_pdfs)
        for slug in sorted(pdf_slugs | summary_slugs)
    ]
    return PapersIndex(kb_root=str(kb_root), entries=entries)


# ---------------------------------------------------------------------------
# Idempotency query helpers — what fetch + summarization consult
# ---------------------------------------------------------------------------


def needs_fetch(entry: PaperEntry) -> bool:
    """True when ``entry`` should be (re-)fetched: no PDF, or an unreadable stub."""
    return entry.needs_refetch


def summary_is_current(entry: PaperEntry) -> bool:
    """True when the summary already reflects the PDF on disk (skip the LLM re-read)."""
    return entry.summary_current


def needs_summary(entry: PaperEntry, *, target_depth: str = "full") -> bool:
    """True when ``entry`` should be (re-)summarized to reach ``target_depth``.

    Re-summarize when: there is no summary; OR the summary was built from a different PDF
    than the one now on disk (the PDF changed); OR the current read depth is below the target
    on the ladder. Otherwise the existing summary stands and the expensive read is skipped.
    """
    if target_depth not in _DEPTH_RANK:
        raise ValueError(f"unknown target_depth {target_depth!r}; one of {READ_DEPTHS}")
    if not entry.summary_present:
        return True
    if entry.pdf_present and not entry.summary_current:
        return True  # PDF changed since the summary was written
    return _DEPTH_RANK.get(entry.read_depth, 0) < _DEPTH_RANK[target_depth]


def existing_summary_pdf_sha(kb_root: Path, doi: str) -> str | None:
    """Return the ``source_pdf_sha256`` recorded in an existing summary, or ``None``.

    A light single-file read used by ``summarize_corpus`` to hash-gate the LLM read without a
    full corpus scan: if this equals the current PDF's hash, the read can be skipped.
    """
    from vaultlab.kb.paths import summary_path

    path = summary_path(Path(kb_root), doi)
    if not path.exists():
        return None
    fm, _ = _parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    return fm.get("source_pdf_sha256") or None


def pdf_sha256(path: Path) -> str:
    """Public alias for the chunked SHA-256 used across the spine (fetch + summarize)."""
    return _pdf_sha256(Path(path))


# ---------------------------------------------------------------------------
# Render + persist
# ---------------------------------------------------------------------------


def render_index_markdown(index: PapersIndex) -> str:
    """Render the agent-readable ``_papers_index.md``: a status table, a reading backlog, and
    per-paper digests."""
    c = index.counts
    lines = [
        "# Papers index",
        "",
        f"> Generated by `vaultlab.research.papers_index.scan_corpus`. {c['total']} papers: "
        f"{c['pdf_present']} with PDF ({c['pdf_unreadable']} unreadable → re-fetch), "
        f"{c['no_pdf']} without PDF. Reading: {c['read_full'] + c['read_grounded']} full "
        f"({c['read_grounded']} grounded), {c['read_abstract']} abstract-only, "
        f"{c['read_none']} unread; {c['verified']} verified. "
        "Read THIS file to understand the corpus; open a per-paper summary only for detail.",
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
        link = f"[{label}]({e.summary_path})" if e.summary_present else label
        lines.append(
            f"| {link} | {e.year} | {pdf} | {e.read_depth} | {e.verification} | {e.doi} |"
        )

    backlog = index.reading_backlog()
    if backlog:
        lines += [
            "",
            "## Reading backlog",
            "",
            "_Readable PDF on disk but not yet read full-text — the work queue._",
            "",
        ]
        for e in backlog:
            lines.append(f"- [{e.title or e.slug}]({e.pdf_path}) — read_depth `{e.read_depth}`")

    lines += ["", "## Per-paper digests", ""]
    for e in index.entries:
        lines.append(f"### {e.title or e.slug}")
        meta = " · ".join(x for x in [e.year, e.journal, e.read_depth] if x)
        if meta:
            lines.append(f"*{meta}*")
        if e.digest:
            lines.append(e.digest)
        if e.sections:
            lines.append(f"_Sections: {', '.join(e.sections)}_")
        lines.append("")
    return "\n".join(lines)


def save_index(index: PapersIndex, kb_root: Path | None = None) -> tuple[Path, Path]:
    """Write ``_papers_index.json`` (machine source of truth) + ``_papers_index.md`` (readable)
    under ``Wiki/Summaries/``. Additive: writes only these two files."""
    from vaultlab.kb.paths import papers_index_md_path, papers_index_path

    root = Path(kb_root or index.kb_root)
    json_path = papers_index_path(root)
    md_path = papers_index_md_path(root)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "kb_root": str(root),
        "counts": index.counts,
        "entries": [asdict(e) for e in index.entries],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_index_markdown(index), encoding="utf-8")
    return json_path, md_path


def load_index(kb_root: Path) -> dict | None:
    """Load the persisted ``_papers_index.json`` payload, or ``None`` if it doesn't exist."""
    from vaultlab.kb.paths import papers_index_path

    path = papers_index_path(Path(kb_root))
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def build_and_save(kb_root: Path, *, hash_pdfs: bool = True) -> tuple[PapersIndex, Path, Path]:
    """Scan the corpus and persist the ledger in one call. Returns ``(index, json, md)``."""
    index = scan_corpus(Path(kb_root), hash_pdfs=hash_pdfs)
    json_path, md_path = save_index(index, kb_root)
    return index, json_path, md_path


__all__ = [
    "READ_DEPTHS",
    "PaperEntry",
    "PapersIndex",
    "scan_paper",
    "scan_corpus",
    "needs_fetch",
    "needs_summary",
    "summary_is_current",
    "existing_summary_pdf_sha",
    "pdf_sha256",
    "render_index_markdown",
    "save_index",
    "load_index",
    "build_and_save",
]
