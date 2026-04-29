"""Read tools-index entries + external-repos registry from disk."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class ToolsIndexError(Exception):
    """Raised when an index entry is malformed or missing."""


@dataclass
class ToolEntry:
    """One curated package entry.

    Tiered for searchability per Bobby 2026-04-29: ``description`` + ``summary``
    are the always-loaded short form (~1 paragraph); ``body`` is the deep doc
    that the LLM only reads after deciding this package is relevant.

    Use :func:`summary_for` / :func:`deep_doc_for` for tiered access; ``body``
    is preserved for backwards compatibility.
    """

    name: str
    description: str
    summary: str  # one-paragraph TL;DR (always loaded)
    domains: list[str]
    install: str
    docs_url: str
    body: str  # full markdown for LLM consumption (loaded on demand)
    path: Path  # source file
    key_functions: list[str] = field(default_factory=list)


def packages_dir() -> Path:
    """Return the ``packages/`` directory inside this subpackage."""
    return Path(__file__).parent / "packages"


def external_repos_path() -> Path:
    """Return the path to ``external_repos.toml``."""
    return Path(__file__).parent / "external_repos.toml"


def load_index() -> dict[str, ToolEntry]:
    """Read every ``packages/*.md`` and return a dict keyed by package name.

    Returns
    -------
    dict[str, ToolEntry]
        Empty dict if the packages directory doesn't exist (e.g. fresh clone
        before seed).
    """
    pkg_dir = packages_dir()
    if not pkg_dir.exists():
        return {}

    out: dict[str, ToolEntry] = {}
    for md_file in sorted(pkg_dir.glob("*.md")):
        if md_file.name == "README.md":
            continue
        entry = _parse_tool_md(md_file)
        out[entry.name] = entry
    return out


def load_external_repos() -> list[dict[str, object]]:
    """Read ``external_repos.toml`` and return the list of repo entries.

    Returns
    -------
    list[dict]
        Empty list if the file is absent.
    """
    target = external_repos_path()
    if not target.exists():
        return []
    with target.open("rb") as f:
        data = tomllib.load(f)
    repos = data.get("repo", [])
    if not isinstance(repos, list):
        return []
    return list(repos)


def suggest_for_topic(
    topic: str,
    *,
    index: dict[str, ToolEntry] | None = None,
) -> list[ToolEntry]:
    """Return packages whose ``domains`` overlap with the given topic keyword.

    Case-insensitive substring match against each entry's ``domains`` list and
    a hit on the package description for catch-alls. Returns an empty list when
    nothing matches — the caller can then fall back to web search.

    Parameters
    ----------
    topic
        Free-form topic keyword (e.g., ``"spatial"``, ``"single-cell"``,
        ``"statistics"``).
    index
        Optional pre-loaded index (avoids re-reading files in tight loops).

    Returns
    -------
    list[ToolEntry]
        Matching entries, ordered by package name.
    """
    if index is None:
        index = load_index()
    needle = topic.lower().strip()
    if not needle:
        return []
    hits: list[ToolEntry] = []
    for entry in index.values():
        if any(needle in d.lower() for d in entry.domains):
            hits.append(entry)
            continue
        if needle in entry.description.lower():
            hits.append(entry)
    hits.sort(key=lambda e: e.name)
    return hits


# ---------------------------------------------------------------------------
# Internal: parse a tool .md
# ---------------------------------------------------------------------------


_FRONT_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_LIST_RE = re.compile(r"^\s*-\s+`([^`\n]+)`", re.MULTILINE)


def summary_for(name: str, *, index: dict[str, ToolEntry] | None = None) -> str | None:
    """Return the one-paragraph summary for a package, or ``None`` if unknown.

    The tiered-search entry point: read summaries across all 12 packages,
    decide which 1-3 to dive into, then call :func:`deep_doc_for` for those.
    """
    if index is None:
        index = load_index()
    entry = index.get(name)
    return entry.summary if entry is not None else None


def deep_doc_for(name: str, *, index: dict[str, ToolEntry] | None = None) -> str | None:
    """Return the full body for a package after summary triage.

    Per Bobby 2026-04-29: don't read 50 pages every time — read summaries first,
    only dive into deep docs when the summary indicates relevance.
    """
    if index is None:
        index = load_index()
    entry = index.get(name)
    return entry.body if entry is not None else None


def _parse_tool_md(path: Path) -> ToolEntry:
    text = path.read_text(encoding="utf-8")
    m = _FRONT_RE.match(text)
    if not m:
        raise ToolsIndexError(f"Tool file missing frontmatter: {path}")

    fm: dict[str, str | list[str]] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, raw_val = line.partition(":")
        val = raw_val.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            fm[key.strip()] = [x.strip().strip("\"'") for x in inner.split(",") if x.strip()]
        else:
            fm[key.strip()] = val.strip("\"'")

    body = text[m.end() :].strip()

    # Pull out function-list bullets under "## Key functions" if present
    key_functions: list[str] = []
    in_section = False
    for line in body.splitlines():
        if line.startswith("## "):
            in_section = "Key functions" in line
            continue
        if in_section:
            list_match = _LIST_RE.match(line)
            if list_match:
                key_functions.append(list_match.group(1).strip())

    # Extract the "## Summary" section (one-paragraph TL;DR for tiered search).
    # Falls back to the description if no Summary section is present.
    summary = _extract_summary(body) or str(fm.get("description", ""))

    name_val = fm.get("name") or path.stem
    desc_val = fm.get("description", "")
    domains_val = fm.get("domains", [])
    install_val = fm.get("install", "")
    docs_val = fm.get("docs_url", "")

    return ToolEntry(
        name=str(name_val),
        description=str(desc_val),
        summary=summary,
        domains=list(domains_val) if isinstance(domains_val, list) else [str(domains_val)],
        install=str(install_val),
        docs_url=str(docs_val),
        body=body,
        path=path,
        key_functions=key_functions,
    )


def _extract_summary(body: str) -> str:
    """Extract the first paragraph following a ``## Summary`` heading.

    Returns the empty string if no Summary section is present.
    """
    in_summary = False
    paragraph_lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            if in_summary:
                break  # next section ends Summary
            in_summary = "Summary" in line
            continue
        if in_summary:
            stripped = line.strip()
            if not stripped:
                if paragraph_lines:  # blank after content = end of first paragraph
                    break
                continue
            paragraph_lines.append(stripped)
    return " ".join(paragraph_lines).strip()
