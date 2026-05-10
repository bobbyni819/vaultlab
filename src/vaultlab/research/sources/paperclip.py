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
from collections.abc import Iterable

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
# (``PMC9684921``).
#
# The separator between (id, source, date) fields is U+00B7 MIDDLE DOT in
# the MCP output, but on Windows the CLI emits cp1252-encoded bytes which
# our UTF-8 subprocess capture turns into U+FFFD. To handle both, the
# regex matches "any non-whitespace single-character separator" via
# ``[^\s\w]``. Also tolerates ``\xb7`` raw byte through the latin-1
# fallback the subprocess uses.
_ID_LINE_RE = re.compile(
    r"^\s*([A-Za-z0-9_.]+)\s+[^\s\w]\s+([^\d]+?)\s+[^\s\w]\s+(\d{4}(?:-\d{2}-\d{2})?)\s*$"
)
_DOI_LINE_RE = re.compile(
    r"^\s*https?://(?:dx\.)?doi\.org/(.+?)\s*$",
    re.IGNORECASE,
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

    def _run_paperclip(
        self,
        cmd: list[str],
        *,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess:
        """Invoke the paperclip CLI with Windows-friendly env + decoding.

        Two Windows-specific quirks are handled here:

        1. **Git Bash / MSYS path mangling.** When this code runs from
           Git Bash on Windows, paths like ``/papers/<id>/`` get
           auto-converted to
           ``/papers/C:/Program Files/Git/papers/<id>/`` by MSYS. We
           set ``MSYS_NO_PATHCONV=1`` in the subprocess env to disable
           this. Harmless on Linux / macOS where the var has no effect.

        2. **CLI emits cp1252 bytes on Windows.** The MCP HTTP transport
           returns UTF-8, but the CLI's stdout is the Windows console
           default (cp1252) — for example U+00B7 MIDDLE DOT (the field
           separator) lands as a single ``\\xb7`` byte instead of the
           UTF-8 two-byte ``\\xc2\\xb7``. We capture as bytes, then try
           UTF-8 first, falling back to cp1252 / latin-1 on
           UnicodeDecodeError so all bytes are recoverable.
        """
        import os as _os

        env = _os.environ.copy()
        env.setdefault("MSYS_NO_PATHCONV", "1")
        # Force paperclip's own Python stdout to UTF-8. Default on
        # Windows is cp1252, which can't encode Greek letters, math
        # symbols, or accented author names — paperclip 0.3.0 crashes
        # mid-output with UnicodeEncodeError when the content has any
        # non-cp1252 character. PYTHONIOENCODING fixes the inner
        # process's stdout encoding.
        env["PYTHONIOENCODING"] = "utf-8"
        # Run with raw bytes so we can decode-attempt cleanly.
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=False,
            timeout=timeout if timeout is not None else self._timeout,
            env=env,
        )
        # Decode stdout / stderr with multi-encoding fallback.
        for enc in ("utf-8", "cp1252", "latin-1"):
            try:
                stdout = proc.stdout.decode(enc)
                stderr = proc.stderr.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            # latin-1 never raises; this branch is theoretically
            # unreachable, but keep a defensive fallback.
            stdout = proc.stdout.decode("latin-1", errors="replace")
            stderr = proc.stderr.decode("latin-1", errors="replace")
        return subprocess.CompletedProcess(
            proc.args,
            proc.returncode,
            stdout,
            stderr,
        )

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

    def lookup_doi(self, doi: str) -> Paper | None:
        """Check whether paperclip has a paper for this DOI.

        Used by ``vaultlab.research.acquisition.acquire_pdf`` as the
        first tier of the waterfall — if paperclip has the paper, we
        skip PDF download entirely and read full-text sections directly
        from the virtual filesystem.

        Args:
            doi: DOI to look up (case-insensitive).

        Returns:
            :class:`Paper` if found, else ``None``. Returns ``None``
            silently on auth / binary / timeout errors (graceful
            degrade per Q5) — callers should NOT treat ``None`` as
            "definitely not in corpus", just "couldn't find via this
            client right now". To distinguish, check
            :meth:`is_authenticated` separately.
        """
        if not self.available:
            return None
        if not doi:
            return None

        cmd = [self._binary, "lookup", "doi", doi.strip().lower()]
        try:
            result = self._run_paperclip(cmd, timeout=min(self._timeout, 30))
        except (subprocess.TimeoutExpired, OSError):
            return None
        if result.returncode != 0:
            # Not found in corpus is a non-zero exit; auth errors also
            # come through here. Treat both as "not available via this
            # path right now" and let the caller fall through.
            return None

        # The lookup output is the same one-paper-block format as
        # search, so the search-output parser handles it.
        papers = _parse_search_output(result.stdout)
        if not papers:
            return None
        return papers[0]

    def get_paper_text(self, paper_id: str) -> str:
        """Read the full-text content of a paper from paperclip's
        virtual filesystem.

        Returns the concatenated body text from
        ``/papers/<paper_id>/content.lines`` with the leading line-number
        prefixes stripped (paperclip prepends ``L<n>:`` to each line).

        Args:
            paper_id: Paperclip paper ID (e.g. ``arx_2107.07953`` or
                ``PMC9684921``).

        Returns:
            The paper's body text as a single string. Empty string on
            any error (graceful degrade).
        """
        if not self.available or not paper_id:
            return ""
        cmd = [self._binary, "cat", f"/papers/{paper_id}/content.lines"]
        try:
            result = self._run_paperclip(cmd, timeout=self._timeout)
        except (subprocess.TimeoutExpired, OSError):
            return ""
        if result.returncode != 0:
            return ""

        # Each line is prefixed with "L<n>: " — strip that for a clean read.
        cleaned: list[str] = []
        for line in result.stdout.splitlines():
            # Match "L<digits>: <text>" prefix
            m = re.match(r"^L\d+:\s?(.*)$", line)
            cleaned.append(m.group(1) if m else line)
        return "\n".join(cleaned)

    def list_sections(self, paper_id: str) -> list[str]:
        """List the section names available for a paper.

        Args:
            paper_id: Paperclip paper ID.

        Returns:
            Section names without the ``.lines`` suffix
            (e.g. ``["Title", "Abstract", "Introduction", ...]``).
            Empty list on any error.
        """
        if not self.available or not paper_id:
            return []
        cmd = [self._binary, "ls", f"/papers/{paper_id}/sections/"]
        try:
            result = self._run_paperclip(cmd, timeout=min(self._timeout, 30))
        except (subprocess.TimeoutExpired, OSError):
            return []
        if result.returncode != 0:
            return []
        # Output format: "Title.lines  Authors.lines  Abstract.lines  ..."
        # whitespace-separated. We split on whitespace and strip the
        # ``.lines`` suffix.
        sections: list[str] = []
        for token in result.stdout.split():
            if token.endswith(".lines"):
                sections.append(token[: -len(".lines")])
        return sections

    def get_section(self, paper_id: str, section_name: str) -> str:
        """Read a single named section of a paper.

        Args:
            paper_id: Paperclip paper ID.
            section_name: Section name as returned by
                :meth:`list_sections` (no ``.lines`` suffix).

        Returns:
            Section text as a single string. Empty string on any error.
        """
        if not self.available or not paper_id or not section_name:
            return ""
        path = f"/papers/{paper_id}/sections/{section_name}.lines"
        cmd = [self._binary, "cat", path]
        try:
            result = self._run_paperclip(cmd, timeout=min(self._timeout, 30))
        except (subprocess.TimeoutExpired, OSError):
            return ""
        if result.returncode != 0:
            return ""
        cleaned: list[str] = []
        for line in result.stdout.splitlines():
            m = re.match(r"^L\d+:\s?(.*)$", line)
            cleaned.append(m.group(1) if m else line)
        return "\n".join(cleaned)

    def list_figures(self, paper_id: str) -> list[str]:
        """List figure filenames available for a paper.

        Returns figure filenames (e.g. ``["figure_1.jpg",
        "figure_1_b.jpg", ...]``). Empty list on any error.
        """
        if not self.available or not paper_id:
            return []
        cmd = [self._binary, "ls", f"/papers/{paper_id}/figures/"]
        try:
            result = self._run_paperclip(cmd, timeout=min(self._timeout, 30))
        except (subprocess.TimeoutExpired, OSError):
            return []
        if result.returncode != 0:
            return []
        return [tok for tok in result.stdout.split() if tok.endswith((".jpg", ".png"))]

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
                "paperclip is unauthenticated; run `paperclip login` or set PAPERCLIP_API_KEY"
            )

        cmd: list[str] = [self._binary, "search", "-n", str(int(max_results))]
        if sources:
            for s in sources:
                cmd.extend(["-s", s])
        if since:
            cmd.extend(["--since", since])
        cmd.append(query)

        try:
            result = self._run_paperclip(cmd, timeout=self._timeout)
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
            if (
                nxt.startswith(("       ", "\t"))
                and "·" not in nxt
                and not _URL_LINE_RE.match(nxt)
                and not _ABSTRACT_LINE_RE.match(nxt)
            ):
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

        papers.append(
            Paper(
                title=title,
                authors=authors,
                year=year,
                journal=source_label,
                doi=doi,
                abstract=abstract,
                url=url or (f"https://doi.org/{doi}" if doi else ""),
                source_api="paperclip",
            )
        )

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
