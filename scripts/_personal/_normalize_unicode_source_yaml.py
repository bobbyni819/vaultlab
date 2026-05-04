"""One-shot Unicode-hyphen sweep over ``Wiki/Summaries/*.md`` source YAML.

Background
----------
OpenAlex returns mixed Unicode in author names — e.g.
``Kennedy‐Darling`` carries a U+2010 ``HYPHEN`` instead of an ASCII ``-``.
Visually identical, functionally different. The render-time normalizer
``vaultlab.kb.paths.format_author_lastname`` already handles this for
**output** wikilink labels, but the source YAML still carries the
exotic chars; anyone reading the markdown directly sees mixed
characters and any string-matching against ASCII forms breaks.

This script is the one-shot data-hygiene cleanup mentioned as
"OpenAlex U+2010 in source YAML" under "What still leaks (post
evening-5)" in
``Sources/Notes/semantic-audit-log-2026-04-30.md`` (Round 2 / Finding 8).

Behaviour
---------
* Walks ``<kb>/Wiki/Summaries/*.md`` (uses
  :func:`vaultlab.context.resolve_kb_root` so it works from any KB).
* For each file, parses the YAML frontmatter (delimiters ``---``).
* Normalizes any string field — recursively into list / dict — by
  replacing the four Unicode hyphen variants explicitly listed in
  :data:`HYPHEN_VARIANTS` with ASCII ``-``.
* Writes back **only** if at least one byte changed. Idempotent — a
  second run is guaranteed to be a no-op.
* Prints a per-Unicode-char count at the end.

Usage
-----
::

    python scripts/_normalize_unicode_source_yaml.py
    python scripts/_normalize_unicode_source_yaml.py --kb metabolism
    python scripts/_normalize_unicode_source_yaml.py --dry-run

Programmatic / test entry point
-------------------------------
:func:`normalize_yaml_value` and :func:`sweep_kb_summaries` are
imported by the regression tests in
``tests/test_vaultlab_kb/test_normalize_unicode_source_yaml.py``.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# Allow running as a script straight from a checkout without ``pip install -e .``.
if __package__ is None and not hasattr(sys, "frozen"):
    _SRC = Path(__file__).resolve().parent.parent / "src"
    if _SRC.is_dir() and str(_SRC) not in sys.path:
        sys.path.insert(0, str(_SRC))


# Unicode hyphen variants we replace with ASCII ``-``. Listed
# explicitly for auditability — this is the same set tracked by
# :data:`vaultlab.kb.paths._UNICODE_HYPHENS` plus minus sign / fullwidth.
# We keep the script's set narrow (only the four most-common offenders
# from OpenAlex) per the Round 2 task spec — broader cleanup belongs in
# the render-time helper which already handles a wider set.
HYPHEN_VARIANTS: dict[str, str] = {
    "‐": "-",  # HYPHEN
    "–": "-",  # EN DASH
    "—": "-",  # EM DASH
    "−": "-",  # MINUS SIGN
}


def normalize_string(value: str) -> tuple[str, Counter[str]]:
    """Replace each U+2010 / U+2013 / U+2014 / U+2212 with ASCII ``-``.

    Returns ``(normalized_value, per_char_counts)``. ``per_char_counts``
    is empty for an unchanged input — caller checks ``bool(counts)`` to
    decide whether the YAML needs rewriting.
    """
    counts: Counter[str] = Counter()
    out = value
    for src, dst in HYPHEN_VARIANTS.items():
        if src in out:
            counts[src] += out.count(src)
            out = out.replace(src, dst)
    return out, counts


def normalize_yaml_value(value: Any) -> tuple[Any, Counter[str]]:
    """Recursively normalize Unicode hyphens in any YAML-compatible value.

    Strings → :func:`normalize_string`. Lists and dicts recurse. Anything
    else (int, float, bool, None) is returned unchanged.

    The recursion is structural — we don't try to be clever about which
    fields to normalize; an exotic hyphen in a journal name or title
    deserves the same fix as one in an author name.
    """
    counts: Counter[str] = Counter()
    if isinstance(value, str):
        new_str, c = normalize_string(value)
        counts.update(c)
        return new_str, counts
    if isinstance(value, list):
        new_list = []
        for item in value:
            new_item, c = normalize_yaml_value(item)
            counts.update(c)
            new_list.append(new_item)
        return new_list, counts
    if isinstance(value, dict):
        new_dict = {}
        for key, item in value.items():
            new_item, c = normalize_yaml_value(item)
            counts.update(c)
            new_dict[key] = new_item
        return new_dict, counts
    return value, counts


def _split_frontmatter(text: str) -> tuple[str, str, str] | None:
    """Split ``text`` into ``(prefix, frontmatter_yaml, body)``.

    Returns ``None`` when the file does not start with a ``---`` YAML
    frontmatter delimiter — those files are skipped (no frontmatter to
    rewrite).

    ``prefix`` is whatever (if anything) precedes the opening ``---``;
    in practice always empty, but kept so that a round-trip preserves
    the file byte-for-byte when no normalization is needed.
    """
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return None
    # Find the closing delimiter on its own line.
    lines = text.splitlines(keepends=True)
    end_idx = None
    for i in range(1, len(lines)):
        stripped = lines[i].rstrip("\r\n")
        if stripped == "---":
            end_idx = i
            break
    if end_idx is None:
        return None
    prefix = lines[0]  # opening "---\n"
    fm_yaml = "".join(lines[1:end_idx])
    body = "".join(lines[end_idx:])  # closing "---\n" + rest
    return prefix, fm_yaml, body


def _load_yaml(text: str) -> Any:
    """Lazy-import ``yaml`` so the module is importable even if PyYAML
    is missing in some odd environment."""
    import yaml

    return yaml.safe_load(text)


def _dump_yaml(value: Any) -> str:
    import yaml

    # ``allow_unicode=True`` so non-Latin author names stay as their
    # native scripts; ``sort_keys=False`` so we don't reorder fields and
    # blow up the diff.
    return yaml.safe_dump(
        value,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )


def normalize_summary_file(
    path: Path,
    *,
    dry_run: bool = False,
) -> tuple[bool, Counter[str]]:
    """Normalize a single summary markdown file in place.

    Returns ``(changed, per_char_counts)``. ``changed`` is ``True`` when
    the file was rewritten; ``False`` for files with no Unicode-hyphen
    occurrences (or for malformed-frontmatter files we skip).
    """
    try:
        original = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False, Counter()

    parts = _split_frontmatter(original)
    if parts is None:
        return False, Counter()
    prefix, fm_yaml, body = parts

    # Quick pre-check — if no exotic chars exist anywhere in the file,
    # skip parsing entirely. Reading is cheap; YAML parsing is not.
    if not any(ch in original for ch in HYPHEN_VARIANTS):
        return False, Counter()

    try:
        data = _load_yaml(fm_yaml)
    except Exception:
        # Malformed YAML — leave alone. Bobby can spot-check manually.
        return False, Counter()

    new_data, counts = normalize_yaml_value(data)
    if not counts:
        return False, Counter()

    if dry_run:
        return True, counts

    new_fm = _dump_yaml(new_data)
    new_text = prefix + new_fm + body
    path.write_text(new_text, encoding="utf-8")
    return True, counts


def sweep_kb_summaries(
    kb_root: Path,
    *,
    dry_run: bool = False,
) -> dict[str, int | Counter[str] | list[Path]]:
    """Sweep every ``Wiki/Summaries/*.md`` file under ``kb_root``.

    Returns a stats dict with keys:

    * ``scanned`` — number of summary files we touched (read + frontmatter parse)
    * ``normalized`` — number of files that had at least one replacement
    * ``per_char`` — :class:`Counter` of replacement counts per Unicode char
    * ``files`` — list of normalized file Paths (sorted by name)
    """
    summaries_dir = Path(kb_root) / "Wiki" / "Summaries"
    if not summaries_dir.is_dir():
        return {
            "scanned": 0,
            "normalized": 0,
            "per_char": Counter(),
            "files": [],
        }

    scanned = 0
    normalized: list[Path] = []
    per_char: Counter[str] = Counter()
    for path in sorted(summaries_dir.glob("*.md")):
        scanned += 1
        changed, counts = normalize_summary_file(path, dry_run=dry_run)
        if changed:
            normalized.append(path)
            per_char.update(counts)
    return {
        "scanned": scanned,
        "normalized": len(normalized),
        "per_char": per_char,
        "files": normalized,
    }


def _resolve_kb(kb_arg: str | None) -> Path:
    """Resolve the KB root. ``kb_arg`` may be a name (``equities``) or path."""
    from vaultlab.context import resolve_kb_root

    if kb_arg:
        candidate = Path(kb_arg)
        if candidate.is_dir():
            return candidate
        # Treat as a KB name relative to the resolved root's parent.
        root = resolve_kb_root()
        named = root.parent / kb_arg if root.name != kb_arg else root
        if named.is_dir():
            return named
        # Fall through: try kb_root / kb_arg (sometimes resolve_kb_root
        # already points at the *vault* not a specific KB).
        nested = root / kb_arg
        if nested.is_dir():
            return nested
        raise SystemExit(f"Could not resolve KB '{kb_arg}'")
    return resolve_kb_root()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize Unicode hyphens in Wiki/Summaries source YAML."
    )
    parser.add_argument(
        "--kb",
        default=None,
        help=(
            "KB name or absolute path. Defaults to vaultlab.context.resolve_kb_root()."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing any files.",
    )
    args = parser.parse_args(argv)

    # Force UTF-8 stdout so that f-strings printing the Unicode hyphens
    # themselves don't blow up on Windows cp1252 consoles.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

    kb_root = _resolve_kb(args.kb)
    print(f"Sweep target: {kb_root}")
    print(f"Dry-run: {args.dry_run}")
    print(f"Looking for {len(HYPHEN_VARIANTS)} Unicode hyphen variants:")
    for src in HYPHEN_VARIANTS:
        print(f"  U+{ord(src):04X}  {src!r}")

    stats = sweep_kb_summaries(kb_root, dry_run=args.dry_run)
    scanned = int(stats["scanned"])  # type: ignore[arg-type]
    normalized = int(stats["normalized"])  # type: ignore[arg-type]
    per_char: Counter[str] = stats["per_char"]  # type: ignore[assignment]

    print()
    print("=" * 60)
    print(f"Scanned:    {scanned} files")
    print(f"Normalized: {normalized} files")
    if per_char:
        print("Per-char replacement counts:")
        for src, count in sorted(per_char.items()):
            print(f"  U+{ord(src):04X}  {src!r:>4}  {count:>5}")
    else:
        print("(no replacements needed — already clean)")

    if args.dry_run and normalized:
        print()
        print("Dry-run only — re-run without --dry-run to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
