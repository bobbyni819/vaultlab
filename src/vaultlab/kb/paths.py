"""vaultlab.kb.paths — canonical KB path routing.

This module is the *single source of truth* for where VaultLab writes things
inside a knowledge base. Every module or agent that produces a file output
MUST route through these helpers — never build paths by hand.

The full convention is documented in
``G:/My Drive/Knowledge/vaultlab/Sources/Notes/kb-output-conventions-2026-04-29.md``.

Three-layer rule
----------------
- ``Sources/`` — immutable inputs (raw PDFs, search-result stubs, manual notes)
- ``Wiki/`` — LLM-written content (per-paper summaries, cross-source concepts,
  project state)
- ``Output/`` — generated artifacts for delivery (slides, reports, run-id
  directories)

Design notes
------------
Every function takes an explicit ``kb_root: Path`` so callers control which
KB is targeted (no implicit globals — testable, deterministic). Path-builder
functions return :class:`pathlib.Path` and **do not** create directories;
that's the caller's responsibility — typically via :func:`ensure_parent`.

The module lives at ``vaultlab.kb.paths`` (not ``vaultlab.paths``) because
the path conventions are KB-shaped: every helper assumes the
``Sources/Wiki/Output`` layout that's specific to the LLM-Wiki / VaultLab
KB convention. Code that doesn't write into a KB doesn't need this module.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

__all__ = [
    "article_stub_path",
    "concept_path",
    "deck_path",
    "deck_plan_path",
    "ensure_parent",
    "evidence_path",
    "figure_path",
    "fulltext_md_path",
    "pdf_path",
    "project_decisions_path",
    "project_dir",
    "project_state_path",
    "run_dir",
    "search_log_path",
    "slugify_doi",
    "slugify_topic",
    "summary_path",
    "transcript_path",
    "turn_path",
]


# ---------------------------------------------------------------------------
# Slugification
# ---------------------------------------------------------------------------


def slugify_doi(doi: str) -> str:
    """Convert a DOI into a filesystem-safe slug.

    Replaces characters that are illegal or awkward on Windows / POSIX
    filesystems (``/``, ``\\``, ``:``, ``*``, ``?``, ``"``, ``<``, ``>``,
    ``|``) with underscores. Whitespace is stripped.

    Examples
    --------
    >>> slugify_doi("10.1126/science.1225829")
    '10.1126_science.1225829'
    >>> slugify_doi("10.1038/s41586-023-05915-x")
    '10.1038_s41586-023-05915-x'
    """
    if not doi:
        raise ValueError("slugify_doi requires a non-empty DOI")
    s = doi.strip()
    # Strip optional URL prefixes (`https://doi.org/...` etc).
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if s.lower().startswith(prefix):
            s = s[len(prefix):]
            break
    # Replace filesystem-illegal characters with underscore.
    s = re.sub(r'[\\/:*?"<>|]+', "_", s)
    # Collapse whitespace to single underscore.
    s = re.sub(r"\s+", "_", s)
    return s


def slugify_topic(topic: str) -> str:
    """Convert a topic / query string into a kebab-case ascii slug.

    Lowercases, strips accents, replaces non-alphanumeric runs with a single
    hyphen, and trims hyphens from the ends.

    Examples
    --------
    >>> slugify_topic("CRISPR base editing")
    'crispr-base-editing'
    >>> slugify_topic("  galectin-4  sulfatide  ")
    'galectin-4-sulfatide'
    """
    if not topic or not topic.strip():
        raise ValueError("slugify_topic requires a non-empty topic")
    # Strip accents (NFKD then drop combining marks).
    normalized = unicodedata.normalize("NFKD", topic)
    ascii_only = "".join(c for c in normalized if not unicodedata.combining(c))
    ascii_only = ascii_only.encode("ascii", "ignore").decode("ascii")
    # Lowercase and replace any non-alnum run with a hyphen.
    ascii_only = ascii_only.lower()
    ascii_only = re.sub(r"[^a-z0-9]+", "-", ascii_only)
    return ascii_only.strip("-")


def _today_str() -> str:
    return date.today().strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Sources/ — immutable inputs
# ---------------------------------------------------------------------------


def pdf_path(kb_root: Path, doi: str) -> Path:
    """``Sources/Papers/<doi-slug>.pdf`` — raw PDF storage (immutable input)."""
    return Path(kb_root) / "Sources" / "Papers" / f"{slugify_doi(doi)}.pdf"


def fulltext_md_path(kb_root: Path, doi: str) -> Path:
    """``Sources/Papers/<doi-slug>.md`` — scraped/converted full-text markdown (immutable)."""
    return Path(kb_root) / "Sources" / "Papers" / f"{slugify_doi(doi)}.md"


def article_stub_path(kb_root: Path, doi: str) -> Path:
    """``Sources/Articles/<doi-slug>.md`` — search-result stub (immutable)."""
    return Path(kb_root) / "Sources" / "Articles" / f"{slugify_doi(doi)}.md"


def search_log_path(kb_root: Path, query: str, date_str: str | None = None) -> Path:
    """``Sources/Notes/lit-search-<query-slug>-<date>.md`` — session log.

    Lives in Sources because it's a record of *what the user asked*, not
    LLM-synthesized content.
    """
    when = date_str or _today_str()
    slug = slugify_topic(query)
    return Path(kb_root) / "Sources" / "Notes" / f"lit-search-{slug}-{when}.md"


# ---------------------------------------------------------------------------
# Wiki/ — LLM-written content
# ---------------------------------------------------------------------------


def summary_path(kb_root: Path, doi: str) -> Path:
    """``Wiki/Summaries/<doi-slug>.md`` — LLM-written per-paper summary."""
    return Path(kb_root) / "Wiki" / "Summaries" / f"{slugify_doi(doi)}.md"


def concept_path(
    kb_root: Path,
    topic: str,
    kind: str = "lineage",
    date_str: str | None = None,
) -> Path:
    """``Wiki/Concepts/<topic-slug>-<kind>-<date>.md`` — cross-source synthesis.

    Used for lineage arcs, methodology overviews, and other concept articles
    that weave together evidence from multiple Wiki/Summaries entries.
    """
    if not kind or not kind.strip():
        raise ValueError("concept_path requires a non-empty kind (e.g. 'lineage')")
    when = date_str or _today_str()
    topic_slug = slugify_topic(topic)
    kind_slug = slugify_topic(kind)
    return (
        Path(kb_root)
        / "Wiki"
        / "Concepts"
        / f"{topic_slug}-{kind_slug}-{when}.md"
    )


def project_state_path(kb_root: Path, project: str) -> Path:
    """``Wiki/Projects/<project-slug>/START_HERE.md``."""
    return (
        Path(kb_root)
        / "Wiki"
        / "Projects"
        / slugify_topic(project)
        / "START_HERE.md"
    )


def project_decisions_path(kb_root: Path, project: str) -> Path:
    """``Wiki/Projects/<project-slug>/decisions-log.md``."""
    return (
        Path(kb_root)
        / "Wiki"
        / "Projects"
        / slugify_topic(project)
        / "decisions-log.md"
    )


# ---------------------------------------------------------------------------
# Output/ — generated artifacts for delivery
# ---------------------------------------------------------------------------


def project_dir(kb_root: Path, project: str) -> Path:
    """``Output/<project-slug>/`` — root for project-scoped artifacts."""
    return Path(kb_root) / "Output" / slugify_topic(project)


def deck_path(kb_root: Path, project: str, deck_name: str) -> Path:
    """``Output/<project-slug>/<deck-name>.pptx``.

    ``deck_name`` may include or omit the ``.pptx`` suffix; if missing it's
    appended.
    """
    if not deck_name or not deck_name.strip():
        raise ValueError("deck_path requires a non-empty deck_name")
    name = deck_name.strip()
    if not name.lower().endswith(".pptx"):
        name = f"{name}.pptx"
    return project_dir(kb_root, project) / name


def deck_plan_path(kb_root: Path, project: str) -> Path:
    """``Output/<project-slug>/deck_plan.md``."""
    return project_dir(kb_root, project) / "deck_plan.md"


def figure_path(
    kb_root: Path,
    project: str,
    fig_id: str,
    suffix: str = ".png",
) -> Path:
    """``Output/<project-slug>/figures/<fig-id><suffix>``.

    ``suffix`` defaults to ``.png``; pass ``.annotated.png`` etc. for
    variants. A leading dot is added if absent.
    """
    if not fig_id or not fig_id.strip():
        raise ValueError("figure_path requires a non-empty fig_id")
    sfx = suffix if suffix.startswith(".") else f".{suffix}"
    return project_dir(kb_root, project) / "figures" / f"{fig_id}{sfx}"


def evidence_path(kb_root: Path, project: str, file_slug: str) -> Path:
    """``Output/<project-slug>/citations/<file-slug>.evidence.json``.

    ``file_slug`` is the source document's identifier (e.g. ``manuscript-v2``).
    The ``.evidence.json`` suffix is appended automatically if missing.
    """
    if not file_slug or not file_slug.strip():
        raise ValueError("evidence_path requires a non-empty file_slug")
    name = file_slug.strip()
    if not name.endswith(".evidence.json"):
        name = f"{name}.evidence.json"
    return project_dir(kb_root, project) / "citations" / name


def run_dir(
    kb_root: Path,
    project: str,
    run_id: str | None = None,
) -> Path:
    """``Output/<project-slug>/runs/<run-id>/`` — multi-agent meeting outputs.

    If ``run_id`` is None, auto-generate from current local timestamp
    (``YYYY-MM-DDTHH-MM-SS``). Colons are avoided so the value is filesystem
    safe on every platform.
    """
    rid = run_id if run_id else datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    return project_dir(kb_root, project) / "runs" / rid


def turn_path(run_dir: Path, turn_n: int, role_id: str) -> Path:
    """``<run-dir>/turn-<n>-<role-id>.md`` — per-turn role output.

    ``turn_n`` is the zero- or one-based turn index — the convention is up
    to the caller; the function preserves whatever integer is passed in.
    """
    if turn_n < 0:
        raise ValueError("turn_path requires a non-negative turn number")
    if not role_id or not role_id.strip():
        raise ValueError("turn_path requires a non-empty role_id")
    return Path(run_dir) / f"turn-{turn_n}-{role_id.strip()}.md"


def transcript_path(run_dir: Path) -> Path:
    """``<run-dir>/transcript.md`` — combined meeting transcript."""
    return Path(run_dir) / "transcript.md"


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def ensure_parent(p: Path) -> Path:
    """Ensure ``p.parent`` exists; return ``p`` (so callers can chain).

    Use this immediately before writing a file so a freshly-built path's
    directory tree is created on demand. Path-builder functions in this
    module deliberately do not call this themselves.

    Examples
    --------
    >>> from pathlib import Path
    >>> p = ensure_parent(Path('/tmp/some/new/dir/file.md'))  # doctest: +SKIP
    >>> p.write_text('hello')  # doctest: +SKIP
    """
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
