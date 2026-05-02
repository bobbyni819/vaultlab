"""Paperclip source — search the 8M-paper biomedical corpus.

Paperclip (https://paperclip.gxl.ai) indexes full-text papers from
PubMed Central, bioRxiv, medRxiv, and arXiv into a virtual filesystem
at ``/papers/<id>/``. This module provides a thin wrapper around the
``paperclip`` CLI binary so vaultlab can use it as a parallel source
alongside PubMed, Semantic Scholar, CrossRef, etc.

Auth: ``paperclip login`` (browser) or ``PAPERCLIP_API_KEY`` env var.
If neither is set, ``is_authenticated()`` returns False and the source
is skipped silently in ``MultiSource`` (graceful degradation per
design-doc Q5).

Notes
-----
* Paperclip's CLI emits text, not JSON. We parse the standard search
  output format. If the CLI changes its format, the parser may need
  updates.
* arXiv coverage is paperclip's main non-overlap with vaultlab's
  existing federated stack — even after this integration, adding arXiv
  directly to vaultlab is still worthwhile for non-biomed queries.
* Per design-doc Q2, we discard paperclip's relevance ranking and let
  vaultlab's composite_score + recency_quota re-rank the union. The
  ``Paper`` records returned here have ``citation_count=0`` and no
  ``influential_citations`` — paperclip doesn't expose those metrics.
* Per design-doc Q1, this source runs in parallel with the existing 6.
  Per Q5, missing auth is a soft skip with a one-line stderr message.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from typing import Iterable

from vaultlab.research.paper import Paper

logger = logging.getLogger(__name__)


_PAPERCLIP_BINARY_NAME = "paperclip"

# Paperclip search-result regex.
#
# Output format (one block per paper, separated by blank lines):
#
#     1. Title text — possibly long, may wrap on multiple lines
#        Author1, Author2, Author3, ...
#        paper_id · source · YYYY-MM-DD
#        https://doi.org/<doi>             (optional)
#        "Brief abstract or first sentence."  (optional)
#
# We parse one block at a time.
_RESULT_HEADER_RE = re.compile(r"^\s*(\d+)\.\s+(.+?)\s*$")
# Paperclip paper IDs include arXiv-style dots (``arx_2501.06039``),
# bioRxiv-style underscores (``bio_3ac44def6d63``), and PMC-style digits
# (``PMC9684921``). The character class allows alphanumerics, ``_`` and
# ``.`` so all three families parse.
_ID_LINE_RE = re.compile(
    r"^\s*([A-Za-z0-9_.]+)\s*·\s*([^·]+?)\s*·\s*(\d{4}(?:-\d{2}-\d{2})?)\s*$"
)
_DOI_LINE_RE = re.compile(
    r"^\s*https?://(?:dx\.)?doi\.org/(.+?)\s*$", re.IGNORECASE,
)
_URL_LINE_RE = re.compile(r"^\s*https?://", re.IGNORECASE)
_ABSTRACT_LINE_RE = re.compile(r'^\s*"(.+)"\s*$')


class PaperclipUnavailable(RuntimeError):
    """Raised when ``paperclip`` CLI is missing or unauthenticated.

    ``MultiSource`` should catch this and skip paperclip silently with
    a one-line ℹ️ stderr message — per design-doc Q5 graceful
    degradation.
    """


class PaperclipClient:
    """Thin wrapper around the ``paperclip`` CLI binary."""

    def __init__(self, binary: str | None = None, timeout: int = 60):
        """Initialize client.

        Args:
            binary: Path to the ``paperclip`` executable. Defaults to
                whatever ``shutil.which`` finds on ``PATH``.
            timeout: Per-subprocess timeout in seconds.
        """
        self._binary = binary or shutil.which(_PAPERCLIP_BINARY_NAME)
        self._timeout = timeout

    @property
    def available(self) -> bool:
        """Return True if the paperclip binary is on PATH."""
        return self._binary is not None and os.path.exists(self._binary)

    def is_authenticated(self) -> bool:
        """Best-effort auth-state detection.

        Returns True unless we can affirmatively prove the CLI is
        unauthenticated. The actual ``search`` call surfaces auth
        failures via stderr / non-zero exit, so a wrong-positive here
        is benign — we just attempt and degrade gracefully.

        Detection strategy:
        1. ``PAPERCLIP_API_KEY`` env var → authenticated.
        2. Cached credentials at ``~/.paperclip/credentials.json`` (or
           the equivalent OS-specific path) → authenticated.
        3. ``paperclip config`` output explicitly says "not signed in"
           → unauthenticated. Note: paperclip 0.3.0 has a Windows
           console encoding bug that crashes ``config`` mid-output, so
           we cannot rely on this path on Windows. We fall back to the
           credentials-file check.
        4. Default: True (optimistic) — attempt search and let it fail
           with PaperclipUnavailable if needed.

        Note: MCP-level auth (used by Claude Code) and CLI auth use
        DIFFERENT credential stores. Authenticating via the MCP flow
        does NOT auth the CLI; users must run ``paperclip login`` in a
        terminal *or* set ``PAPERCLIP_API_KEY`` for vaultlab CLI
        subprocess calls to work.
        """
        if not self.available:
            return False
        if os.environ.get("PAPERCLIP_API_KEY"):
            return True

        # Check default credentials file location.
        candidates = [
            os.path.expanduser("~/.paperclip/credentials.json"),
            os.path.expanduser("~/.paperclip/auth.json"),
            os.path.expanduser("~/.paperclip/token"),
        ]
        for path in candidates:
            try:
                if os.path.isfile(path) and os.path.getsize(path) > 0:
                    return True
            except OSError:
                continue

        # Try ``paperclip config`` — but tolerate the Windows-encoding
        # bug in 0.3.0 by being lenient on parse failures.
        try:
            result = subprocess.run(
                [self._binary, "config"],
                capture_output=True,
                text=True,
                timeout=10,
                encoding="utf-8",
                errors="replace",
            )
            out = (result.stdout + result.stderr).lower()
            if "not signed in" in out or "not authenticated" in out:
                return False
        except (subprocess.TimeoutExpired, OSError):
            pass

        # Default optimistic: attempt the search and let it surface
        # auth failures itself. Q5 graceful-degradation lets MultiSource
        # skip silently on PaperclipUnavailable.
        return True

    def search(
        self,
        query: str,
        max_results: int = 20,
        sources: Iterable[str] | None = None,
        since: str | None = None,
    ) -> list[Paper]:
        """Run a paperclip search and return Paper objects.

        Args:
            query: Free-text search query.
            max_results: Cap on results returned.
            sources: Restrict to specific paperclip sources. One of
                ``pmc | biorxiv | medrxiv | arxiv | abstracts``. ``None``
                uses paperclip's default (pmc, biorxiv, medrxiv, arxiv).
            since: Filter to recent papers, e.g. ``"30d"``, ``"6mo"``,
                ``"1y"``.

        Returns:
            List of :class:`Paper`. Empty list on any failure (logged).

        Raises:
            PaperclipUnavailable: if the paperclip binary is missing or
                unauthenticated.
        """
        if not self.available:
            raise PaperclipUnavailable(
                "paperclip CLI not found on PATH; install via "
                "`pip install https://paperclip.gxl.ai/paperclip.whl`"
            )
        if not self.is_authenticated():
            raise PaperclipUnavailable(
                "paperclip is unauthenticated; run `paperclip login` "
                "or set PAPERCLIP_API_KEY"
            )

        cmd: list[str] = [self._binary, "search", "-n", str(int(max_results))]
        if sources:
            for s in sources:
                cmd.extend(["-s", s])
        if since:
            cmd.extend(["--since", since])
        cmd.append(query)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            logger.warning("paperclip search timed out: %s", query)
            return []
        except OSError as exc:
            logger.warning("paperclip search OSError: %s", exc)
            return []

        if result.returncode != 0:
            logger.warning(
                "paperclip search exit %s: %s",
                result.returncode,
                result.stderr.strip()[:200],
            )
            return []

        return _parse_search_output(result.stdout)


def _parse_search_output(text: str) -> list[Paper]:
    """Parse paperclip's text search output into Paper objects.

    Format per result block::

        1. Title
           Author1, Author2, ...
           paper_id · source · YYYY-MM-DD
           https://doi.org/<doi>          (optional)
           "Abstract snippet"             (optional)
    """
    papers: list[Paper] = []
    lines = text.splitlines()

    i = 0
    while i < len(lines):
        line = lines[i]
        m = _RESULT_HEADER_RE.match(line)
        if not m:
            i += 1
            continue

        title = m.group(2).strip()
        i += 1

        # Title may wrap onto subsequent indented lines until we hit a
        # comma-separated authors line, an id-line, or a URL/abstract.
        # Collect indented continuation lines as title until we see an
        # author-looking line (heuristic: contains a comma OR is a known
        # ID-line / URL / abstract).
        # Simplest heuristic: title is a single line; authors immediately
        # follow. If the next non-empty line looks like an ID line, then
        # the title was multi-line — paperclip indents continuations.
        continuation_lines: list[str] = []
        while i < len(lines):
            nxt = lines[i]
            if not nxt.strip():
                i += 1
                continue
            # If we hit an ID-line pattern, the title may have wrapped;
            # back up and re-treat the captured continuation as title
            # extension.
            if _ID_LINE_RE.match(nxt):
                break
            # If indented heavily and looks more like a continuation
            # (no commas, no URL), treat as title continuation.
            if nxt.startswith(("       ", "\t")) and "·" not in nxt and not _URL_LINE_RE.match(nxt) and not _ABSTRACT_LINE_RE.match(nxt):
                continuation_lines.append(nxt.strip())
                i += 1
                continue
            break
        if continuation_lines:
            title = (title + " " + " ".join(continuation_lines)).strip()

        # Next non-empty line is authors (comma-separated, may end with ...)
        authors: list[str] = []
        while i < len(lines):
            nxt = lines[i]
            if not nxt.strip():
                i += 1
                continue
            if _ID_LINE_RE.match(nxt):
                break
            authors = _parse_authors_line(nxt)
            i += 1
            break

        # Next is the id-line "paper_id · source · YYYY-MM-DD"
        paper_id = ""
        source_label = ""
        date_str = ""
        while i < len(lines):
            nxt = lines[i]
            if not nxt.strip():
                i += 1
                continue
            mid = _ID_LINE_RE.match(nxt)
            if mid:
                paper_id = mid.group(1)
                source_label = mid.group(2).strip()
                date_str = mid.group(3)
                i += 1
                break
            # Defensive — if no id line, stop trying
            break

        # Optional DOI URL
        doi = ""
        url = ""
        if i < len(lines):
            nxt = lines[i]
            mdoi = _DOI_LINE_RE.match(nxt)
            if mdoi:
                doi = mdoi.group(1).strip()
                url = nxt.strip()
                i += 1
            elif _URL_LINE_RE.match(nxt):
                url = nxt.strip()
                i += 1

        # Optional abstract snippet
        abstract = ""
        if i < len(lines):
            nxt = lines[i]
            mabs = _ABSTRACT_LINE_RE.match(nxt)
            if mabs:
                abstract = mabs.group(1).strip()
                i += 1

        # Year extraction
        try:
            year = int(date_str[:4]) if date_str else 0
        except ValueError:
            year = 0

        papers.append(Paper(
            title=title,
            authors=authors,
            year=year,
            journal=source_label,
            doi=doi,
            abstract=abstract,
            url=url or (f"https://doi.org/{doi}" if doi else ""),
            source_api="paperclip",
        ))

    return papers


def _parse_authors_line(line: str) -> list[str]:
    """Parse 'Author One, Author Two, Author Three...' into a list.

    Trailing ellipsis indicates truncation; we drop it.
    """
    s = line.strip()
    if s.endswith("..."):
        s = s[:-3].rstrip().rstrip(",")
    parts = [p.strip().rstrip(".") for p in s.split(",")]
    return [p for p in parts if p]


__all__ = [
    "PaperclipClient",
    "PaperclipUnavailable",
]
