"""Robust abstract retrieval — the keystone fix for Tier-B coverage.

Background
----------
Tier-B abstract summarization (see :mod:`vaultlab.research.tier_b`)
requires a usable abstract. The corpus has *several* places an abstract
can live:

1. ``Corpus.papers[doi].abstract`` — populated by source modules
   (CrossRef / PubMed / S2) at search time.
2. ``Sources/Articles/<doi-slug>.md`` body — written under a
   ``## Abstract`` heading by :func:`lineage._write_article_stub`
   when ``Paper.abstract`` is non-empty at corpus-build time.
3. ``Sources/Articles/<doi-slug>.md`` frontmatter ``abstract`` field —
   added 2026-05-01 (this module's contribution); makes abstracts
   programmatically discoverable without a body regex.
4. CrossRef ``/works/{doi}`` live fetch — last resort when
   #1-3 are all empty. CrossRef returns abstracts in JATS XML format
   that needs HTML stripping (already handled by
   :class:`vaultlab.research.sources.crossref.CrossRefClient`).

The 2026-05-01 audit found that CODEX-corpus papers like Goltsev 2018
*Cell*, Black 2021 *Nature Protocols*, and DeepCell Types 2024 had no
abstracts in any of #1-#3 because their initial corpus-build runs
(via Semantic Scholar / NCBI) didn't return abstracts in those API
responses. The CrossRef live-fetch path closes the gap.

Public API
----------
:func:`get_abstract_for_doi` — read-only, tries #1-#3, optionally falls
through to #4 when ``allow_fetch=True``.

:func:`backfill_abstracts_in_kb` — bulk utility: scans existing
article stubs that lack abstracts and fills them in via #4. Run this
once after upgrading vaultlab, then again whenever new papers enter
the corpus from sources that don't carry abstracts.

Design choices
--------------
* **No exception leaks**: a failing CrossRef fetch returns ``""`` rather
  than raising, so callers can fall through to Tier-C without crashing.
* **Idempotent**: running the backfill twice is a no-op.
* **Frontmatter persistence**: abstracts are written into article-stub
  frontmatter (multi-line scalar) so future calls find them without
  re-fetching from CrossRef.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from vaultlab.kb.paths import article_stub_path

logger = logging.getLogger(__name__)


# Maximum reasonable abstract length. Real abstracts are 100-3000 chars;
# anything beyond is probably a paper body that got mis-tagged.
_MAX_ABSTRACT_CHARS = 5000


# ---------------------------------------------------------------------------
# Read-only retrieval
# ---------------------------------------------------------------------------


def get_abstract_for_doi(
    *,
    doi: str,
    corpus=None,  # Corpus | None; not type-imported to avoid circular dep
    kb_root: Path | None = None,
    allow_fetch: bool = False,
    crossref_client=None,  # CrossRefClient | None
) -> str:
    """Return the most authoritative abstract available for a DOI.

    Tries (in order):
    1. ``corpus.papers[doi].abstract``
    2. Article-stub frontmatter ``abstract`` field
    3. Article-stub body ``## Abstract`` heading
    4. CrossRef ``/works/{doi}`` live fetch (only when ``allow_fetch=True``)

    Args:
        doi: DOI to look up (case-insensitive).
        corpus: Optional :class:`Corpus` instance.
        kb_root: Optional KB root path for #2/#3 lookups.
        allow_fetch: When True, escalate to CrossRef live fetch if all
            cached sources are empty.
        crossref_client: Optional pre-initialized CrossRef client; one is
            created if needed.

    Returns:
        The abstract text, or ``""`` if no source has it. Always
        whitespace-stripped. Capped at :data:`_MAX_ABSTRACT_CHARS`.
    """
    if not doi:
        return ""
    doi = doi.strip().lower()

    # 1. Corpus.papers
    if corpus is not None and hasattr(corpus, "papers"):
        paper = corpus.papers.get(doi)
        if paper and paper.abstract:
            text = paper.abstract.strip()
            if text:
                return text[:_MAX_ABSTRACT_CHARS]

    # 2 + 3. Article stub
    if kb_root is not None:
        stub_text = _load_article_stub_text(kb_root=Path(kb_root), doi=doi)
        if stub_text:
            # 2. Frontmatter abstract field (most reliable)
            fm_abstract = _extract_frontmatter_abstract(stub_text)
            if fm_abstract:
                return fm_abstract[:_MAX_ABSTRACT_CHARS]
            # 3. Body ## Abstract heading
            body_abstract = _extract_body_abstract_heading(stub_text)
            if body_abstract:
                return body_abstract[:_MAX_ABSTRACT_CHARS]

    # 4. CrossRef live fetch
    if allow_fetch:
        client = crossref_client or _make_crossref_client()
        if client is not None:
            try:
                paper = client.resolve_doi(doi)
                if paper and paper.abstract:
                    return paper.abstract.strip()[:_MAX_ABSTRACT_CHARS]
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "CrossRef fetch failed for %s: %s", doi, exc,
                )

    # 5. PubMed fallback: many publishers (Elsevier/Cell, Nature
    # Protocols) don't deposit abstracts to CrossRef but DO have them
    # in PubMed. Bridges the gap that Bobby surfaced 2026-05-01.
    if allow_fetch:
        pm_abstract = fetch_abstract_from_pubmed(doi=doi)
        if pm_abstract:
            return pm_abstract[:_MAX_ABSTRACT_CHARS]

    return ""


def _load_article_stub_text(*, kb_root: Path, doi: str) -> str:
    """Load the raw markdown text of an article stub if it exists."""
    try:
        stub_path = article_stub_path(kb_root, doi)
    except Exception:  # noqa: BLE001
        return ""
    if not stub_path.is_file():
        return ""
    try:
        return stub_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _extract_frontmatter_abstract(text: str) -> str:
    """Pull the ``abstract`` field from YAML frontmatter, if present."""
    if not text.startswith("---"):
        return ""
    try:
        _, fm_text, _ = text.split("---", 2)
        fm = yaml.safe_load(fm_text) or {}
    except (ValueError, yaml.YAMLError):
        return ""
    raw = fm.get("abstract", "") or ""
    return str(raw).strip()


def _extract_body_abstract_heading(text: str) -> str:
    """Pull the body content under a ``## Abstract`` heading."""
    match = re.search(
        r"^##\s+Abstract\s*\n+(?P<body>.+?)(?=\n##\s+|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return ""
    return match.group("body").strip()


def _make_crossref_client():
    """Build a CrossRefClient lazily; returns None if module not importable."""
    try:
        from vaultlab.research.sources.crossref import CrossRefClient
        return CrossRefClient()
    except ImportError:
        return None


def _make_ncbi_client():
    """Build an NCBIClient lazily; returns None if module not importable."""
    try:
        from vaultlab.research.sources.ncbi import NCBIClient
        return NCBIClient()
    except ImportError:
        return None


def fetch_abstract_from_pubmed(*, doi: str, ncbi_client=None) -> str:
    """Try to fetch an abstract from PubMed by DOI.

    Many publishers (Elsevier/Cell, Nature Protocols, others) don't
    deposit abstracts to CrossRef but DO have them on PubMed via the
    journal's NLM submission. This function bridges that gap by:

    1. Searching PubMed with ``<doi>[DOI]`` to find the PMID.
    2. Fetching the paper's abstract via efetch.

    Args:
        doi: DOI to look up.
        ncbi_client: Optional pre-initialized client.

    Returns:
        Abstract text, or ``""`` on any failure (DOI not in PubMed,
        no PMID match, no abstract field, network error).
    """
    if not doi:
        return ""
    client = ncbi_client or _make_ncbi_client()
    if client is None:
        return ""
    try:
        # PubMed [DOI] field-tag query is the canonical DOI→PMID path.
        results = client.search(query=f"{doi}[DOI]", max_results=1)
        if not results:
            return ""
        paper = results[0]
        return (paper.abstract or "").strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("PubMed fetch failed for %s: %s", doi, exc)
        return ""


# ---------------------------------------------------------------------------
# Backfill utility
# ---------------------------------------------------------------------------


@dataclass
class BackfillResult:
    """Outcome of running :func:`backfill_abstracts_in_kb`.

    Attributes:
        scanned: Total article stubs visited.
        already_present: Stubs that already had an abstract (frontmatter
            or body); skipped without a fetch.
        fetched: Stubs that received a fresh abstract from CrossRef.
        no_abstract_available: Stubs where CrossRef also returned empty.
        errors: Stubs where the fetch raised an exception.
    """

    scanned: int = 0
    already_present: int = 0
    fetched: int = 0
    no_abstract_available: int = 0
    errors: int = 0


def backfill_abstracts_in_kb(
    *,
    kb_root: Path,
    crossref_client=None,
    max_papers: int | None = None,
    only_dois: Iterable[str] | None = None,
) -> BackfillResult:
    """Scan ``Sources/Articles/`` and fetch missing abstracts from CrossRef.

    For each article stub that doesn't already have an abstract (frontmatter
    OR body), this function:
    1. Extracts the DOI from the stub frontmatter.
    2. Calls CrossRef ``/works/{doi}`` to fetch the abstract.
    3. Persists the abstract back into the stub frontmatter.

    Idempotent — re-running is safe and cheap when no new stubs lack
    abstracts.

    Args:
        kb_root: KB root path.
        crossref_client: Optional pre-initialized client.
        max_papers: Cap on the number of stubs to process. ``None``
            means "all". Useful for incremental runs.
        only_dois: When provided, only process these specific DOIs.
            Useful for backfilling a small set after acquisition failure.

    Returns:
        :class:`BackfillResult` with counts.
    """
    articles_dir = kb_root / "Sources" / "Articles"
    if not articles_dir.is_dir():
        return BackfillResult()

    client = crossref_client or _make_crossref_client()
    if client is None:
        logger.warning(
            "CrossRefClient not importable; backfill is a no-op."
        )
        return BackfillResult()

    only_normalized: set[str] | None = None
    if only_dois is not None:
        only_normalized = {d.strip().lower() for d in only_dois if d}

    result = BackfillResult()

    for stub_path in sorted(articles_dir.glob("*.md")):
        if max_papers is not None and result.scanned >= max_papers:
            break
        result.scanned += 1
        try:
            text = stub_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            result.errors += 1
            continue

        # Skip if already has an abstract.
        if _extract_frontmatter_abstract(text) or _extract_body_abstract_heading(text):
            result.already_present += 1
            continue

        # Pull DOI from frontmatter.
        if not text.startswith("---"):
            continue
        try:
            _, fm_text, body = text.split("---", 2)
            fm = yaml.safe_load(fm_text) or {}
        except (ValueError, yaml.YAMLError):
            continue

        doi = (fm.get("doi") or "").strip().lower()
        if not doi:
            continue
        if only_normalized is not None and doi not in only_normalized:
            continue

        # Fetch from CrossRef.
        try:
            paper = client.resolve_doi(doi)
        except Exception as exc:  # noqa: BLE001
            logger.warning("CrossRef fetch failed for %s: %s", doi, exc)
            result.errors += 1
            continue

        if paper is None or not paper.abstract:
            result.no_abstract_available += 1
            continue

        abstract_text = paper.abstract.strip()[:_MAX_ABSTRACT_CHARS]

        # Write the abstract back into frontmatter.
        new_text = _inject_abstract_into_frontmatter(text, abstract_text)
        try:
            stub_path.write_text(new_text, encoding="utf-8")
            result.fetched += 1
            logger.info("backfilled abstract for %s (%d chars)",
                        doi, len(abstract_text))
        except OSError as exc:
            logger.warning("could not write %s: %s", stub_path, exc)
            result.errors += 1

    return result


def _inject_abstract_into_frontmatter(text: str, abstract: str) -> str:
    """Add ``abstract: |\\n  <text>`` block to YAML frontmatter.

    If frontmatter already has an ``abstract`` field, replace it.
    Otherwise add it just before the closing ``---`` of the frontmatter.
    """
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text
    _, fm_text, body = parts

    # Indent the abstract for the multi-line YAML scalar.
    indented = "\n".join(
        "  " + line for line in abstract.split("\n")
    )
    new_field = f"\nabstract: |\n{indented}\n"

    # Replace existing abstract field if present.
    if re.search(r"^abstract\s*:", fm_text, re.MULTILINE):
        new_fm = re.sub(
            r"^abstract\s*:.*?(?=^[a-zA-Z_]+\s*:|\Z)",
            new_field.lstrip("\n") + "\n",
            fm_text,
            count=1,
            flags=re.MULTILINE | re.DOTALL,
        )
    else:
        # Append at end of frontmatter (before closing ---).
        new_fm = fm_text.rstrip("\n") + new_field

    return f"---{new_fm}---{body}"


# ---------------------------------------------------------------------------
# Stub-creation-on-demand for DOIs not yet in the corpus
# ---------------------------------------------------------------------------


def ensure_article_stub_for_doi(
    *,
    doi: str,
    kb_root: Path,
    crossref_client=None,
    overwrite: bool = False,
) -> Path | None:
    """Ensure an article stub exists for a DOI, creating it if needed.

    Used when the orchestrator needs metadata (including abstract) for
    a DOI that wasn't surfaced by the picker — typically a user-required
    paper specified via ``--always-include``, or any DOI we want to
    Tier-B summarize without going through full corpus build.

    Workflow:
    1. If a stub already exists at ``Sources/Articles/<doi-slug>.md``
       and ``overwrite=False``, return its path unchanged.
    2. Fetch metadata from CrossRef (``client.resolve_doi(doi)``).
    3. Build a stub with all available metadata + abstract in
       frontmatter.
    4. Write to disk and return the path.

    Args:
        doi: DOI to ensure a stub for.
        kb_root: KB root path.
        crossref_client: Optional pre-initialized client.
        overwrite: When True, regenerate the stub even if one exists.

    Returns:
        Path to the article stub, or ``None`` if CrossRef returned no
        metadata for this DOI.
    """
    if not doi:
        return None
    doi = doi.strip().lower()

    try:
        stub_path = article_stub_path(Path(kb_root), doi)
    except Exception:  # noqa: BLE001
        return None

    if stub_path.is_file() and not overwrite:
        return stub_path

    client = crossref_client or _make_crossref_client()
    if client is None:
        logger.warning(
            "CrossRefClient not importable; cannot create stub for %s.",
            doi,
        )
        return None

    try:
        paper = client.resolve_doi(doi)
    except Exception as exc:  # noqa: BLE001
        logger.warning("CrossRef fetch failed for %s: %s", doi, exc)
        return None

    if paper is None:
        return None

    # If CrossRef returned no abstract, try PubMed as a fallback.
    # Many publishers don't deposit abstracts to CrossRef but DO have
    # them in PubMed (Cell/Elsevier, Nature Protocols, etc.).
    if not (paper.abstract or "").strip():
        pm_abstract = fetch_abstract_from_pubmed(doi=doi)
        if pm_abstract:
            paper.abstract = pm_abstract

    # Build the stub markdown.
    from datetime import date as _date

    title = (paper.title or "").replace('"', '\\"')
    fm_lines = ["---", f'title: "{title}"']
    if paper.authors:
        fm_lines.append("authors:")
        for a in paper.authors:
            esc = a.replace('"', '\\"')
            fm_lines.append(f'  - "{esc}"')
    if paper.year:
        fm_lines.append(f"year: {paper.year}")
    if paper.journal:
        j = paper.journal.replace('"', '\\"')
        fm_lines.append(f'journal: "{j}"')
    fm_lines.append(f'doi: "{doi}"')
    if getattr(paper, "pmid", ""):
        fm_lines.append(f'pmid: "{paper.pmid}"')
    if getattr(paper, "citation_count", 0):
        fm_lines.append(f"citation_count: {paper.citation_count}")
    if getattr(paper, "source_api", ""):
        fm_lines.append(f'source: "{paper.source_api}"')
    else:
        fm_lines.append('source: "crossref-on-demand"')
    fm_lines.append(f"created: {_date.today().isoformat()}")
    fm_lines.append("tags: [article, literature, on-demand-stub]")
    if paper.abstract:
        truncated = paper.abstract.strip()[:_MAX_ABSTRACT_CHARS]
        fm_lines.append("abstract: |")
        for body_line in truncated.split("\n"):
            fm_lines.append(f"  {body_line}")
    fm_lines.append("---")

    body_lines = [
        "",
        f"# {paper.title or doi}",
        "",
    ]
    if paper.authors:
        body_lines.append(f"**Authors:** {', '.join(paper.authors)}")
        body_lines.append("")
    if paper.journal and paper.year:
        body_lines.append(f"**Published in:** {paper.journal} ({paper.year})")
        body_lines.append("")
    body_lines.append(f"**DOI:** [{doi}](https://doi.org/{doi})")
    body_lines.append("")
    body_lines.append("> This stub was created on-demand by")
    body_lines.append("> ``abstract_recall.ensure_article_stub_for_doi`` —")
    body_lines.append("> typically because a user marked this DOI as required")
    body_lines.append("> (--always-include) or the Tier-B summarizer needed")
    body_lines.append("> a CrossRef-backed abstract.")
    body_lines.append("")

    stub_path.parent.mkdir(parents=True, exist_ok=True)
    stub_path.write_text(
        "\n".join(fm_lines + body_lines) + "\n",
        encoding="utf-8",
    )
    logger.info("created on-demand stub for %s at %s", doi, stub_path)
    return stub_path


__all__ = [
    "BackfillResult",
    "backfill_abstracts_in_kb",
    "ensure_article_stub_for_doi",
    "fetch_abstract_from_pubmed",
    "get_abstract_for_doi",
]
