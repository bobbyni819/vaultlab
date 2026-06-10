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
    "author_year_label",
    "concept_path",
    "deck_path",
    "deck_plan_path",
    "ensure_parent",
    "evidence_path",
    "figure_path",
    "format_author_lastname",
    "fulltext_md_path",
    "pdf_path",
    "project_decisions_path",
    "project_dir",
    "project_intake_path",
    "project_lineage_pointer_path",
    "project_papers_path",
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
# Author-name normalization (for wikilink + citation labels)
# ---------------------------------------------------------------------------


# Unicode hyphen variants we normalize to ASCII so a wikilink label
# matches what Obsidian's autocompleter produces. Listed explicitly for
# auditability; this is the full set produced by NCBI / OpenAlex /
# CrossRef in the corpora we've seen.
_UNICODE_HYPHENS = {
    "‐",  # HYPHEN
    "‑",  # NON-BREAKING HYPHEN
    "‒",  # FIGURE DASH
    "–",  # EN DASH
    "—",  # EM DASH
    "−",  # MINUS SIGN
    "﹣",  # SMALL HYPHEN-MINUS
    "－",  # FULLWIDTH HYPHEN-MINUS
}


def _normalize_hyphens(name: str) -> str:
    """Replace exotic unicode hyphens with ASCII ``-``.

    OpenAlex returns names like ``Kennedy‐Darling`` (U+2010) which look
    fine in a markdown viewer but break wikilink autocompletion / pages
    that compare against ASCII forms. Normalizing here keeps every
    downstream renderer agreed on a single hyphen byte.
    """
    if not name:
        return name
    out = name
    for ch in _UNICODE_HYPHENS:
        if ch in out:
            out = out.replace(ch, "-")
    return out


def format_author_lastname(author: str) -> str:
    """Extract the surname from an author string in any of the known formats.

    Handles every author-name format VaultLab has seen in the wild:

    * ``"Last F"``                 -> ``"Last"``  (NCBI / S2 short form)
    * ``"Last FM"``                -> ``"Last"``
    * ``"Last, First"``            -> ``"Last"``  (Vancouver / CSL JSON)
    * ``"Last, F."``               -> ``"Last"``
    * ``"F. Last"``                -> ``"Last"``  (OpenAlex / CrossRef)
    * ``"J. Kennedy-Darling"``     -> ``"Kennedy-Darling"``
    * ``"First Middle Last"``      -> ``"Last"``  (Western full name)
    * ``"Sarah Black"``            -> ``"Black"``
    * single token (corp author)   -> as-is
    * empty / falsy                -> ``""`` (caller picks fallback)

    Unicode hyphens are normalized to ASCII ``-`` so
    ``"Kennedy‐Darling X"`` ends up as ``"Kennedy-Darling"``.

    Pre-evening-5 (2026-04-30) most call sites used a naive
    ``authors[0].split()[0]`` which ALWAYS picked the first whitespace
    token. That broke for OpenAlex's "F. Last" format (``J. Kennedy-Darling``
    rendered as ``J. 2020`` instead of ``Kennedy-Darling 2020``).
    """
    if not author:
        return ""
    s = _normalize_hyphens(author).strip()
    if not s:
        return ""

    # Comma-separated → "Last, First" — surname is unambiguous.
    if "," in s:
        last = s.split(",", 1)[0].strip()
        return last or s

    tokens = s.split()
    if len(tokens) == 1:
        # Single token: corp author or already a bare last name.
        return tokens[0]

    # Multi-token. We resolve the format in priority order:
    #
    #   1. NCBI short form ``Last F`` / ``Last FM`` — the LAST token is
    #      a 1-2-letter initials block. This is the dominant form in
    #      our corpora (PubMed, Semantic Scholar) so we check it first.
    #   2. OpenAlex / CrossRef ``F. Last`` / ``J. Kennedy-Darling`` —
    #      the FIRST token ends with '.' or is a single letter.
    #   3. Western full name ``First Last`` / ``First Middle Last`` —
    #      surname is the last token.
    #
    # Pre-evening-5 the original heuristic checked the last token first
    # but ALSO returned tokens[0] for short-but-real surnames like
    # ``Li C`` → which still works because "C" is the last token here.
    # However it FAILED for OpenAlex's ``F. Last`` because the last
    # token wasn't initial-shaped, so the function fell back to
    # last_tok and produced ``"Last"`` correctly — but for ``J.
    # Kennedy-Darling`` the last token is ``"Kennedy-Darling"``
    # (correct), so the bug only bit when the FIRST author had a
    # multi-token surname. The new logic explicitly handles the
    # initial-first form before falling through.

    suffixes = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}

    # Strip trailing generational suffixes BEFORE format detection so
    # ``"J. Smith Jr."`` doesn't look like NCBI's ``"Last Jr"`` form.
    while len(tokens) > 1 and tokens[-1].lower().rstrip(".") in suffixes:
        tokens = tokens[:-1]

    if len(tokens) == 1:
        return tokens[0]

    # 1. NCBI short form: last token is initials (1-2 chars all alpha,
    #    or 1-3 chars with periods).
    last_tok = tokens[-1]
    last_clean = last_tok.replace(".", "")
    last_looks_initial = (1 <= len(last_clean) <= 2 and last_clean.isalpha()) or (
        last_tok.endswith(".") and len(last_clean) <= 3
    )
    if last_looks_initial:
        return tokens[0]

    # 2. OpenAlex / CrossRef "F. Last" — first token is initials.
    first_tok = tokens[0]
    first_clean = first_tok.replace(".", "")
    first_looks_initial = first_tok.endswith(".") or (
        1 <= len(first_clean) <= 2 and first_clean.isalpha()
    )
    if first_looks_initial:
        return tokens[-1]

    # 3. Western "First Last" — surname is the last token.
    return tokens[-1]


def author_year_label(authors: list[str], year: int | None) -> str:
    """Render an Obsidian wikilink label like ``"Kennedy-Darling 2020"``.

    Uses :func:`format_author_lastname` for surname extraction (so every
    callsite handles OpenAlex / NCBI / CSL formats consistently) and
    falls back to ``"Anon"`` + ``"n.d."`` only when the inputs are
    actually empty.
    """
    last = ""
    for a in authors or []:
        last = format_author_lastname(a)
        if last:
            break
    if not last:
        last = "Anon"
    year_str = str(year) if year else "n.d."
    return f"{last} {year_str}"


# ---------------------------------------------------------------------------
# Slugification
# ---------------------------------------------------------------------------


def slugify_doi(doi: str) -> str:
    """Convert a DOI into a filesystem-safe slug.

    Replaces characters that are illegal or awkward on Windows / POSIX
    filesystems (``/``, ``\\``, ``:``, ``*``, ``?``, ``"``, ``<``, ``>``,
    ``|``) with underscores. Whitespace is stripped. The result is
    lowercased so summary paths and PDF cache paths agree on slug form
    even if a mixed-case DOI sneaks in from a search engine.

    Strips trailing file extensions (``.pdf``, ``.md``, ``.json``, ``.xml``,
    ``.html``, ``.htm``, ``.txt``) because callers occasionally pass
    ``Path(p).name`` instead of ``Path(p).stem`` and we don't want
    ``[[10.7554_elife.31657.pdf|...]]`` wikilinks leaking into LLM output.
    See evening-5 / Round 2 audit log Finding 3 (2026-04-30).

    Examples
    --------
    >>> slugify_doi("10.1126/science.1225829")
    '10.1126_science.1225829'
    >>> slugify_doi("10.1038/s41586-023-05915-x")
    '10.1038_s41586-023-05915-x'
    >>> slugify_doi("10.7554/elife.31657.pdf")
    '10.7554_elife.31657'
    >>> slugify_doi("10.1126/Science.xyz") == slugify_doi("10.1126/science.xyz")
    True
    """
    if not doi:
        raise ValueError("slugify_doi requires a non-empty DOI")
    s = doi.strip()
    # Strip optional URL prefixes (`https://doi.org/...` etc).
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if s.lower().startswith(prefix):
            s = s[len(prefix) :]
            break
    # Strip a trailing file extension (case-insensitive) if one slipped in
    # from `Path.name`-style callers. Only strip extensions we'd realistically
    # encounter for paper artifacts; anything else is kept verbatim so we
    # don't accidentally chop part of a DOI that happens to look like an
    # extension. Listed explicitly for auditability.
    _STRIPPABLE_SUFFIXES = (".pdf", ".md", ".json", ".xml", ".html", ".htm", ".txt")
    s_lower = s.lower()
    for suffix in _STRIPPABLE_SUFFIXES:
        if s_lower.endswith(suffix):
            s = s[: -len(suffix)]
            break
    # Replace filesystem-illegal characters with underscore.
    s = re.sub(r'[\\/:*?"<>|]+', "_", s)
    # Collapse whitespace to single underscore.
    s = re.sub(r"\s+", "_", s)
    # Lowercase the result so the slug is canonical regardless of how the
    # DOI was capitalised by the upstream source.
    return s.lower()


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


def papers_index_path(kb_root: Path) -> Path:
    """``Wiki/Summaries/_papers_index.json`` — the KB's papers ledger (machine).

    The single source of truth for "what papers does this KB hold, and what is
    their state": one row per DOI-slug recording PDF presence/readability/hash,
    summary presence + read-depth, verification status, and acquisition outcome.
    Built by :func:`vaultlab.research.papers_index.scan_corpus`, which enumerates
    ``Sources/Papers/*.pdf`` JOINed to ``Wiki/Summaries/*.md`` on the shared
    DOI-slug. Lives in ``Wiki/Summaries/`` so it sits with the summaries it
    indexes; the leading underscore keeps it out of the per-paper glob.
    """
    return Path(kb_root) / "Wiki" / "Summaries" / "_papers_index.json"


def papers_index_md_path(kb_root: Path) -> Path:
    """``Wiki/Summaries/_papers_index.md`` — the papers ledger (agent/human readable).

    A status table + per-paper digests + a reading-backlog section, rendered from
    the same scan as :func:`papers_index_path`. An agent reads THIS to understand
    the corpus instead of re-reading every summary; open a per-paper note only for
    the detail you actually need.
    """
    return Path(kb_root) / "Wiki" / "Summaries" / "_papers_index.md"


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
    return Path(kb_root) / "Wiki" / "Concepts" / f"{topic_slug}-{kind_slug}-{when}.md"


def project_state_path(kb_root: Path, project: str) -> Path:
    """``Wiki/Projects/<project-slug>/START_HERE.md``."""
    return Path(kb_root) / "Wiki" / "Projects" / slugify_topic(project) / "START_HERE.md"


def project_decisions_path(kb_root: Path, project: str) -> Path:
    """``Wiki/Projects/<project-slug>/decisions-log.md``."""
    return Path(kb_root) / "Wiki" / "Projects" / slugify_topic(project) / "decisions-log.md"


def project_intake_path(kb_root: Path, project: str) -> Path:
    """``Wiki/Projects/<project-slug>/intake.md`` — saved copy of the intake form.

    The user's filled-in intake form lives in their project folder
    (``<project>/project_intake.md``). After ``/onboard-project`` runs,
    a copy is saved here so future commands can read project context
    without going back to the project folder. Both copies stay in sync
    when the user re-runs ``/onboard-project``.
    """
    return Path(kb_root) / "Wiki" / "Projects" / slugify_topic(project) / "intake.md"


def project_papers_path(kb_root: Path, project: str) -> Path:
    """``Wiki/Projects/<project-slug>/papers.md`` — per-project paper manifest.

    Lists Tier-A papers (read full-text) and Tier-C stubs (citation-graph
    only) with `[[wikilinks]]` to the **global** ``Wiki/Summaries/<doi>.md``
    files. Includes an "Also in" column showing which other projects also
    surfaced each paper. Overwritten on every run — reflects current state.
    """
    return Path(kb_root) / "Wiki" / "Projects" / slugify_topic(project) / "papers.md"


def project_lineage_pointer_path(kb_root: Path, project: str) -> Path:
    """``Wiki/Projects/<project-slug>/lineage.md`` — pointer to the lineage arc.

    A short pointer page that links to the actual narrative arc at
    ``Wiki/Concepts/<topic>-lineage-<date>.md``. Lives in the project
    folder so Obsidian users can jump to the full arc with one click.
    Overwritten on every run.
    """
    return Path(kb_root) / "Wiki" / "Projects" / slugify_topic(project) / "lineage.md"


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
