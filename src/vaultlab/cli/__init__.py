"""vaultlab CLI entry point.

Subcommands live in sibling modules (one .py + .md per subcommand):
    vaultlab setup, demo, doctor, evaluate, run, project, claude, kb, phase,
    manuscript, plan, stats

Conventions per AGENTS.md:
    - One file per subcommand
    - Each subcommand has a sibling .md describing what it does
    - The CLI uses click for argument parsing

The full click-based dispatch is still pending; this scaffold supports the
single subcommand the multi-tenant landing flow needs:

    vaultlab init    # explicitly run the KB-root first-run prompt

so users who want to relocate their KB (or set one up without going through
a slash command) have a documented entry point.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _cmd_init(argv: list[str]) -> int:
    """Run the KB-root first-run prompt and persist the result.

    No-arg form prompts the user. ``vaultlab init <path>`` skips the prompt
    and writes ``<path>`` directly. Either way the choice lands in
    ``~/.config/vaultlab/locations.toml`` under ``[paths] kb_root`` so every
    later orchestrator and slash command picks it up via
    :func:`vaultlab.context.locations.resolve_kb_root`.

    Returns the shell exit code (``0`` on success).
    """
    from vaultlab.context.locations import (
        _DEFAULT_KB_ROOT_NAME,
        register_path,
        resolve_kb_root,
    )

    if argv:
        # Non-interactive flow: caller provided a path explicitly.
        chosen = Path(argv[0]).expanduser()
        register_path("paths.kb_root", str(chosen))
        print(f"vaultlab: KB root set to {chosen}")
        print("(Persisted to ~/.config/vaultlab/locations.toml)")
        return 0

    # Interactive flow — let resolve_kb_root drive the prompt + persistence.
    # We force ``interactive=True`` so the prompt fires even when stdin is
    # piped (e.g. running through a deployment harness that wants the
    # prompt to surface anyway).
    print("vaultlab init — choose where your knowledge base lives.")
    print(f"  (default: ~/{_DEFAULT_KB_ROOT_NAME})")
    chosen = resolve_kb_root(interactive=True, persist_first_run=True)
    print(f"\nvaultlab: KB root set to {chosen}")
    print("(Persisted to ~/.config/vaultlab/locations.toml)")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point registered in pyproject.toml as ``vaultlab``.

    Minimal dispatcher until the full click-based CLI lands. Recognises:

    - ``vaultlab init [<path>]`` — first-run / relocate KB
    - ``vaultlab --help`` — usage banner
    - everything else — print usage and exit 1
    """
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv[0] in {"-h", "--help", "help"}:
        _print_usage()
        return 0

    cmd, rest = argv[0], argv[1:]
    if cmd == "init":
        return _cmd_init(rest)

    print(f"vaultlab: unknown command {cmd!r}", file=sys.stderr)
    _print_usage(stream=sys.stderr)
    return 1


def _print_usage(stream: object = None) -> None:
    if stream is None:
        stream = sys.stdout
    msg = (
        "vaultlab v0.0.1 — alpha scaffold\n"
        "\n"
        "Usage:\n"
        "  vaultlab init [<kb-root-path>]   Configure KB root (interactive if no path given)\n"
        "\n"
        "Other commands (search, run, project, etc.) are exposed as Claude Code slash\n"
        "commands inside .claude/commands/. See README.md for the full inventory."
    )
    print(msg, file=stream)  # type: ignore[arg-type]


if __name__ == "__main__":
    raise SystemExit(main())
