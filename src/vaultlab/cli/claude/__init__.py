"""``vaultlab claude <subcommand>`` — slash-command tooling.

Currently one subcommand:

* ``validate`` — lint ``.claude/commands/*.md`` so a malformed slash-command file
  (missing frontmatter, missing ``name``, empty body) is caught before it ships.
  ``--list`` prints the command names instead of linting.

Referenced as a CI gate by the slash-command template + onboarding docs.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Index/inventory files in .claude/commands/ that are not themselves commands.
_NON_COMMAND_FILES = {"README.md", "COMMANDS.md"}


def _parse_frontmatter(text: str) -> dict[str, str] | None:
    """Parse a leading ``---``-delimited YAML-ish frontmatter block into a flat dict.

    Returns ``None`` if there is no frontmatter. Only the simple ``key: value`` lines
    that slash-command files actually use are parsed (no nested YAML).
    """
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    fm: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip()
    return fm


def _body_after_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :].strip()
    return text.strip()


def validate_commands(commands_dir: Path) -> list[tuple[Path, str, list[str]]]:
    """Lint every command ``.md`` in ``commands_dir``.

    Returns ``[(path, name, problems)]`` — ``problems`` is empty when the file is valid.
    A ``name`` that differs from the filename stem is a (non-fatal) warning, prefixed
    ``warn:``; everything else is a hard problem.
    """
    results: list[tuple[Path, str, list[str]]] = []
    for path in sorted(commands_dir.glob("*.md")):
        if path.name in _NON_COMMAND_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        problems: list[str] = []
        name = ""
        if fm is None:
            problems.append("missing YAML frontmatter")
        else:
            name = fm.get("name", "")
            if not name:
                problems.append("frontmatter missing 'name'")
            elif name != path.stem:
                problems.append(f"warn: name '{name}' != filename stem '{path.stem}'")
        if not _body_after_frontmatter(text):
            problems.append("empty body")
        results.append((path, name, problems))
    return results


def main(argv: list[str]) -> int:
    """Dispatch ``vaultlab claude <subcommand>``."""
    if not argv or argv[0] in {"-h", "--help"}:
        print("Usage: vaultlab claude validate [--list]")
        print("  Lint .claude/commands/*.md (frontmatter + name + body).")
        return 0

    sub, rest = argv[0], argv[1:]
    if sub != "validate":
        print(f"vaultlab claude: unknown subcommand {sub!r}", file=sys.stderr)
        print("Supported: validate", file=sys.stderr)
        return 1

    commands_dir = Path(".claude/commands")
    if not commands_dir.is_dir():
        print(
            f"vaultlab claude validate: no .claude/commands/ under {Path.cwd()}",
            file=sys.stderr,
        )
        return 1

    results = validate_commands(commands_dir)

    if "--list" in rest:
        for path, name, _ in results:
            print(f"/{name or path.stem}")
        return 0

    n_fail = 0
    for path, name, problems in results:
        hard = [p for p in problems if not p.startswith("warn:")]
        if hard:
            n_fail += 1
            print(f"FAIL {path.name}: " + "; ".join(problems))
        elif problems:  # warnings only
            print(f"warn {path.name}: " + "; ".join(p[6:] for p in problems))
        else:
            print(f"ok   {path.name}  (/{name})")

    total = len(results)
    print(f"\n{total - n_fail}/{total} command files valid")
    return 1 if n_fail else 0
