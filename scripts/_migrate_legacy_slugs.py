"""Migrate legacy dash-format DOI slugs to the canonical dot-format.

Background
----------
Pre-2026-04-30, ``vaultlab.research.acquisition.doi_slug`` produced
dash-format slugs like ``10-1126_science-1225829`` (replacing both the
``/`` *and* the ``.`` with ``-`` / ``_``). On 2026-04-30 this was unified
with :func:`vaultlab.kb.paths.slugify_doi` which uses the canonical
dot-format ``10.1126_science.1225829``. ``cache_path_for`` falls back to
the legacy path on read, but disk artifacts written under the old slug
remain stranded. This script migrates them in-place:

* ``Sources/Papers/<dash-slug>.pdf`` -> ``<dot-slug>.pdf``
* ``Sources/Papers/<dash-slug>/`` (figure dirs) -> ``<dot-slug>/``
* ``Sources/Articles/<dash-slug>.md`` -> ``<dot-slug>.md`` (rare)
* ``Wiki/Summaries/<dash-slug>.md`` -> ``<dot-slug>.md`` (rare)
* Updates wikilinks ``[[<dash-slug>...]]`` in
  ``Wiki/Concepts/<topic>-lineage-*.md`` and
  ``Wiki/Projects/<slug>/lineage.md`` / ``papers.md`` /
  ``decisions-log.md`` / ``START_HERE.md``.

Usage
-----
    python scripts/_migrate_legacy_slugs.py [--kb PATH] [--dry-run]

Default ``--kb`` is ``G:/My Drive/Knowledge/vaultlab``. Use ``--dry-run``
to preview the rename plan without touching disk.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Make the script runnable without `pip install -e .`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vaultlab.research.acquisition import _legacy_doi_slug, doi_slug  # noqa: E402

DEFAULT_KB = Path("G:/My Drive/Knowledge/vaultlab")

# A legacy slug looks like ``10-NNNN_xxx-yyy`` (registrant has dashes,
# suffix has dashes inside the registrant section). Regex anchored to the
# DOI prefix.
_LEGACY_RE = re.compile(r"^10-\d+_")


def _is_legacy_slug(stem: str) -> bool:
    """Heuristic: stem starts with ``10-NNNN_`` (dash between 10 and the
    registrant code)."""
    return bool(_LEGACY_RE.match(stem))


def _legacy_to_canonical(stem: str) -> str | None:
    """Reverse a legacy dash-prefix slug to a canonical dot-prefix slug.

    The legacy slug ``_legacy_doi_slug`` replaced ``/`` with ``_`` AND
    replaced every ``.`` with ``-``. The replacement is **lossy** — given
    just the slug we cannot tell whether an internal ``-`` originally
    came from a dash or a dot. To avoid corrupting suffixes (e.g.
    ``s41586-021-03525-z`` which legitimately has internal dashes), we
    only rewrite the **registrant prefix** (``10-NNNN`` -> ``10.NNNN``)
    and leave the suffix intact.

    For DOIs whose suffix originally contained dots (e.g.
    ``10.1126/science.1225829`` -> legacy ``10-1126_science-1225829``),
    this conservative migration is incorrect — but those entries are
    already discoverable via ``cache_path_for``'s legacy fallback, so
    we leave them alone rather than risk corruption.

    Returns the canonical-form slug or ``None`` when the stem doesn't
    look like a legacy slug.
    """
    if "_" not in stem:
        return None
    registrant_dash, sep, rest = stem.partition("_")
    if not _LEGACY_RE.match(stem):
        return None
    registrant = registrant_dash.replace("-", ".")
    canonical = f"{registrant}{sep}{rest}"
    return canonical.lower()


def _scan_directory(directory: Path) -> list[tuple[Path, Path]]:
    """Find all legacy-slug entries in ``directory`` and return a rename plan.

    Each plan entry is ``(legacy_path, canonical_path)``.
    Skips when the canonical destination already exists (we'd merge).
    """
    plan: list[tuple[Path, Path]] = []
    if not directory.exists():
        return plan
    for entry in sorted(directory.iterdir()):
        stem = entry.stem if entry.is_file() else entry.name
        if not _is_legacy_slug(stem):
            continue
        canonical_stem = _legacy_to_canonical(stem)
        if canonical_stem is None:
            continue
        if entry.is_file():
            new_path = entry.with_name(f"{canonical_stem}{entry.suffix}")
        else:
            new_path = entry.with_name(canonical_stem)
        plan.append((entry, new_path))
    return plan


def _rewrite_wikilinks(file_path: Path, slug_map: dict[str, str], dry_run: bool) -> int:
    """Rewrite ``[[old-slug...]]`` -> ``[[new-slug...]]`` in ``file_path``.

    Returns the number of replacements made.
    """
    try:
        text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0
    original = text
    n = 0
    for old, new in slug_map.items():
        # Match [[old]] or [[old|...]] anywhere in the doc. Use word boundaries.
        pattern = re.compile(r"\[\[(" + re.escape(old) + r")(\||\])")
        text, count = pattern.subn(r"[[" + new + r"\2", text)
        n += count
    if n and text != original and not dry_run:
        file_path.write_text(text, encoding="utf-8")
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Migrate legacy dash-slug DOI artifacts to canonical dot-slug."
    )
    parser.add_argument(
        "--kb", type=Path, default=DEFAULT_KB, help="KB root (default: %(default)s)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without renaming."
    )
    args = parser.parse_args(argv)

    kb = args.kb
    if not kb.exists():
        print(f"[ERROR] KB root not found: {kb}", file=sys.stderr)
        return 2

    targets = [
        kb / "Sources" / "Papers",
        kb / "Sources" / "Articles",
        kb / "Wiki" / "Summaries",
    ]

    full_plan: list[tuple[Path, Path]] = []
    for d in targets:
        plan = _scan_directory(d)
        full_plan.extend(plan)
        if plan:
            print(f"[scan] {d.relative_to(kb)} : {len(plan)} legacy entries")

    if not full_plan:
        print("[OK] No legacy-slug entries found. Nothing to migrate.")
        return 0

    # Build slug_map from stems for wikilink rewriting.
    slug_map: dict[str, str] = {}
    for old_path, new_path in full_plan:
        old_stem = old_path.stem if old_path.is_file() else old_path.name
        new_stem = new_path.stem if new_path.is_file() else new_path.name
        slug_map[old_stem] = new_stem

    # Rename files / directories. Track conflicts.
    renamed = 0
    skipped_existing = 0
    for old_path, new_path in full_plan:
        if new_path.exists():
            print(
                f"[skip] {old_path.name} -> {new_path.name} (canonical exists)"
            )
            skipped_existing += 1
            continue
        print(f"[move] {old_path.name} -> {new_path.name}")
        if not args.dry_run:
            old_path.rename(new_path)
        renamed += 1

    # Rewrite wikilinks across known docs.
    link_targets: list[Path] = []
    concepts_dir = kb / "Wiki" / "Concepts"
    projects_dir = kb / "Wiki" / "Projects"
    if concepts_dir.exists():
        link_targets.extend(concepts_dir.glob("*-lineage-*.md"))
    if projects_dir.exists():
        for proj_dir in projects_dir.iterdir():
            if not proj_dir.is_dir():
                continue
            for fname in (
                "lineage.md",
                "papers.md",
                "decisions-log.md",
                "START_HERE.md",
            ):
                p = proj_dir / fname
                if p.exists():
                    link_targets.append(p)

    total_link_replacements = 0
    for f in link_targets:
        n = _rewrite_wikilinks(f, slug_map, args.dry_run)
        if n:
            print(f"[link] {f.relative_to(kb)} : {n} wikilinks updated")
            total_link_replacements += n

    print()
    print("=" * 60)
    print(
        f"Migration {'(dry-run) ' if args.dry_run else ''}summary:\n"
        f"  Renamed:           {renamed}\n"
        f"  Skipped (exists):  {skipped_existing}\n"
        f"  Wikilinks updated: {total_link_replacements} across "
        f"{len(link_targets)} candidate files"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
