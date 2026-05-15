"""Auto-generated KB indexes — ``_Index.md``, ``_Catalog.md``, ``_BackLinks.md``.

Layer 3 of the retrieval cascade documented in ``vaultlab/kb/retrieve.md``.
These three indexes are the "tables of contents" a human researcher would
build by hand if they were keeping the project organized: what notes exist,
when each was created, and which notes reference which.

Outputs
-------
``_Index.md``
    Flat list of every frontmattered markdown file in the KB, grouped by
    ``type:`` frontmatter field. Within each group, files are sorted
    alphabetically by relative path so re-builds are byte-identical.

``_Catalog.md``
    Same content reorganized chronologically by ``created:`` frontmatter
    field (most recent first). Files without ``created:`` are bucketed
    under ``## Undated`` at the bottom.

``_BackLinks.md``
    For every ``[[Target]]`` wikilink reference found anywhere in the KB,
    list every file that contains that reference. Sectioned by target.

Idempotency
-----------
``build_indexes`` is deterministic: given the same KB tree, it produces
byte-identical output. We achieve this by sorting paths, normalizing line
endings, and rendering dates with a fixed format. This matters for
git-tracking the indexes and for the "running twice produces no diff"
test that catches accidental nondeterminism.

Examples
--------
>>> from vaultlab.kb.indexes import build_indexes  # doctest: +SKIP
>>> result = build_indexes(Path("G:/My Drive/Knowledge/metabolism"))  # doctest: +SKIP
>>> result["index"]    # Path to _Index.md
>>> result["catalog"]  # Path to _Catalog.md
>>> result["backlinks"]  # Path to _BackLinks.md
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import frontmatter  # python-frontmatter, dep from pyproject.toml

__all__ = ["build_indexes"]


# Wikilink pattern: ``[[Target]]``, ``[[Target|Alias]]``, ``[[Target#Section]]``,
# ``[[Target#Section|Alias]]``. We capture only the target — the alias and
# section anchor are display-only; backlinks always resolve to the target's
# canonical page.
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]*)?\]\]")

_INDEX_BASENAMES = frozenset({"_Index.md", "_Catalog.md", "_BackLinks.md"})


def build_indexes(kb_root: str | Path) -> dict[str, Path]:
    """Generate ``_Index.md``, ``_Catalog.md``, ``_BackLinks.md`` at ``kb_root``.

    Returns a mapping with keys ``"index"``, ``"catalog"``, ``"backlinks"``
    pointing to the written files. Always writes all three, even if the KB
    has no frontmattered files (in which case the indexes contain just the
    header + a "no entries" placeholder).
    """
    root = Path(kb_root)
    root.mkdir(parents=True, exist_ok=True)

    entries = _scan(root)

    index_path = root / "_Index.md"
    catalog_path = root / "_Catalog.md"
    backlinks_path = root / "_BackLinks.md"

    index_path.write_text(_render_index(entries, root), encoding="utf-8", newline="\n")
    catalog_path.write_text(
        _render_catalog(entries, root), encoding="utf-8", newline="\n"
    )
    backlinks_path.write_text(
        _render_backlinks(entries, root), encoding="utf-8", newline="\n"
    )

    return {
        "index": index_path,
        "catalog": catalog_path,
        "backlinks": backlinks_path,
    }


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------


class _Entry:
    """One scanned KB file. Internal only — the public API returns Paths."""

    __slots__ = ("path", "rel", "stem", "meta", "wikilinks")

    def __init__(
        self,
        path: Path,
        rel: Path,
        stem: str,
        meta: dict[str, Any],
        wikilinks: list[str],
    ) -> None:
        self.path = path
        self.rel = rel
        self.stem = stem
        self.meta = meta
        self.wikilinks = wikilinks

    @property
    def type(self) -> str:
        t = self.meta.get("type")
        return str(t) if t else "untyped"

    @property
    def created(self) -> str | None:
        c = self.meta.get("created")
        if c is None:
            return None
        # Could be a date, datetime, or string — normalize to ISO-ish string.
        return str(c)


def _scan(root: Path) -> list[_Entry]:
    """Walk the KB and collect entries with frontmatter + extracted wikilinks."""
    entries: list[_Entry] = []
    for path in root.rglob("*.md"):
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if path.name in _INDEX_BASENAMES:
            continue

        try:
            post = frontmatter.load(path)
        except (OSError, Exception):  # noqa: BLE001 - tolerant by design
            continue
        meta = dict(post.metadata) if post.metadata else {}
        # Files without frontmatter are still scanned for wikilinks (so they
        # can show up as REFERRERS in _BackLinks.md), but they're filtered
        # out of _Index.md / _Catalog.md downstream.
        body = post.content or ""
        wikilinks = sorted(set(_WIKILINK_RE.findall(body)))
        entries.append(
            _Entry(
                path=path,
                rel=rel,
                stem=path.stem,
                meta=meta,
                wikilinks=wikilinks,
            )
        )

    entries.sort(key=lambda e: e.rel.as_posix().lower())
    return entries


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _render_index(entries: list[_Entry], root: Path) -> str:  # noqa: ARG001
    """``_Index.md`` — grouped by ``type:`` frontmatter field."""
    header = (
        "# KB Index\n\n"
        "> Auto-generated by `vaultlab.kb.build_indexes`. Do not hand-edit — "
        "regenerate via `bobby-kb index` (or call the Python primitive).\n\n"
        "Grouped by `type:` frontmatter field. Files without frontmatter are "
        "omitted (they still appear as referrers in `_BackLinks.md`).\n"
    )

    typed = [e for e in entries if e.meta]
    if not typed:
        return header + "\n_No frontmattered entries._\n"

    by_type: dict[str, list[_Entry]] = defaultdict(list)
    for e in typed:
        by_type[e.type].append(e)

    parts = [header]
    for type_name in sorted(by_type.keys()):
        parts.append(f"\n## {type_name}\n\n")
        for e in by_type[type_name]:
            parts.append(f"- [[{e.stem}]] — `{e.rel.as_posix()}`\n")
    return "".join(parts)


def _render_catalog(entries: list[_Entry], root: Path) -> str:  # noqa: ARG001
    """``_Catalog.md`` — chronological by ``created:`` (newest first)."""
    header = (
        "# KB Catalog\n\n"
        "> Auto-generated by `vaultlab.kb.build_indexes`. Do not hand-edit.\n\n"
        "Chronological by `created:` frontmatter field (most recent first). "
        "Files without `created:` are listed under **Undated** at the bottom.\n"
    )

    typed = [e for e in entries if e.meta]
    if not typed:
        return header + "\n_No frontmattered entries._\n"

    dated = [e for e in typed if e.created is not None]
    undated = [e for e in typed if e.created is None]

    # Newest first; ties broken by relative path for stability.
    dated.sort(key=lambda e: (e.created or "", e.rel.as_posix().lower()), reverse=True)
    # Stable secondary sort already applied via _scan; preserve.

    parts = [header, "\n## Dated\n\n"]
    if not dated:
        parts.append("_No dated entries._\n")
    else:
        for e in dated:
            parts.append(
                f"- `{e.created}` — [[{e.stem}]] — `{e.rel.as_posix()}`\n"
            )

    if undated:
        parts.append("\n## Undated\n\n")
        for e in undated:
            parts.append(f"- [[{e.stem}]] — `{e.rel.as_posix()}`\n")

    return "".join(parts)


def _render_backlinks(entries: list[_Entry], root: Path) -> str:  # noqa: ARG001
    """``_BackLinks.md`` — for each ``[[Target]]``, list referrers."""
    header = (
        "# KB BackLinks\n\n"
        "> Auto-generated by `vaultlab.kb.build_indexes`. Do not hand-edit.\n\n"
        "For every `[[Target]]` wikilink reference in the KB, the section "
        "below lists every file that contains that reference. Sectioned by "
        "target stem (alphabetical).\n"
    )

    # target → sorted list of referrer entries
    refs: dict[str, list[_Entry]] = defaultdict(list)
    for e in entries:
        # A file shouldn't list itself as a backlink to itself; skip self-refs
        # by stem so wikilinks like `[[self]]` in scratch notes don't bloat
        # output. Still register the target so we can list "no referrers"
        # explicitly? — no: a self-reference isn't a real backlink and the
        # target's own page already shows its own content.
        for target in e.wikilinks:
            if target == e.stem:
                continue
            refs[target].append(e)

    if not refs:
        return header + "\n_No wikilink references found._\n"

    parts = [header]
    for target in sorted(refs.keys()):
        parts.append(f"\n## {target}\n\n")
        # Stable order: by relative path.
        referrers = sorted(refs[target], key=lambda e: e.rel.as_posix().lower())
        for referrer in referrers:
            parts.append(f"- `{referrer.rel.as_posix()}`\n")
    return "".join(parts)
