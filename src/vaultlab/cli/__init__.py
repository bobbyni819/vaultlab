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


def _cmd_list_policy_skipped(argv: list[str]) -> int:
    """Print the project's policy-skipped papers for human review.

    Usage: ``vaultlab list-policy-skipped <project_dir>``

    Surfaces the records appended by
    :func:`vaultlab.research.policy_skip.mark_skipped` so the user can
    triage papers the LLM refused to summarize. Exit 0 when zero
    skipped (clean), 0 when some skipped (still success — these are
    expected outcomes), 1 on usage error.
    """
    from vaultlab.research.policy_skip import list_skipped

    if not argv or argv[0] in {"-h", "--help"}:
        print(
            "Usage: vaultlab list-policy-skipped <project_dir>\n"
            "\n"
            "Reads <project_dir>/policy_skipped.json and prints the\n"
            "skip records sorted newest-first. Exit 0 on success.",
            file=sys.stderr,
        )
        return 1
    project = Path(argv[0]).expanduser()
    skipped = list_skipped(project)
    if not skipped:
        print(f"vaultlab: no policy-skipped papers in {project}")
        return 0
    print(f"vaultlab: {len(skipped)} policy-skipped paper(s) in {project}\n")
    for i, entry in enumerate(skipped, 1):
        print(f"  {i}. {entry.get('doi')}")
        print(f"     reason:    {entry.get('reason')}")
        if entry.get("batch"):
            print(f"     batch:     {entry.get('batch')}")
        print(f"     skipped:   {entry.get('skipped_at')}")
        if entry.get("notes"):
            print(f"     notes:     {entry.get('notes')}")
    return 0


def _cmd_fetch_list(argv: list[str]) -> int:
    """Print the manual-fetch shopping list of paywalled DOIs.

    Usage: ``vaultlab fetch-list paywalled <acquisition-log.json>``

    Reads the acquisition-results JSON written by
    ``acquire_pdfs_for_corpus`` (or any caller that serialises a
    ``{doi: AcquisitionResult.to_dict()}`` map) and prints the
    failed_paywalled entries grouped by publisher cluster, with
    publisher URL hints so the user knows which institutional access
    path applies.
    """
    from vaultlab.research.policy_skip import fetch_list_paywalled

    if not argv or argv[0] in {"-h", "--help"} or argv[0] != "paywalled":
        print(
            "Usage: vaultlab fetch-list paywalled <acquisition-log.json>\n"
            "\n"
            "Currently only the 'paywalled' subcommand is supported.",
            file=sys.stderr,
        )
        return 1
    if len(argv) < 2:
        print("vaultlab: fetch-list paywalled needs a log path", file=sys.stderr)
        return 1
    log_path = Path(argv[1]).expanduser()
    if not log_path.exists():
        print(f"vaultlab: file not found: {log_path}", file=sys.stderr)
        return 1
    entries = fetch_list_paywalled(log_path)
    if not entries:
        print(f"vaultlab: no paywalled entries in {log_path.name}")
        return 0
    print(f"vaultlab: {len(entries)} paywalled paper(s) need manual fetch\n")
    print("# Manual-fetch shopping list")
    print(f"\nGenerated from {log_path.name}.")
    print("Sorted by publisher cluster (Nature → Cell → Science → Wiley → "
          "Springer → other Elsevier → other).\n")
    for i, entry in enumerate(entries, 1):
        print(f"## {i}. {entry.get('title') or '(no title)'}")
        print(f"- DOI: `{entry.get('doi')}`")
        if entry.get("journal"):
            print(f"- Journal: {entry['journal']} ({entry.get('year', '?')})")
        print(f"- Try: {entry.get('publisher_url')}")
        if entry.get("cache_target_path"):
            print(f"- Drop the PDF here: `{entry['cache_target_path']}`")
        print(f"- Why: {entry.get('why_paywalled')}")
        print()
    return 0


def _cmd_paperclip_grep(argv: list[str]) -> int:
    """Passthrough to ``paperclip grep``.

    Usage: ``vaultlab paperclip-grep <pattern> [<path>] [opts]``
    """
    import subprocess
    if not argv or argv[0] in {"-h", "--help"}:
        print(
            "Usage: vaultlab paperclip-grep <pattern> [<path>] [opts]\n"
            "\n"
            "Thin passthrough to `paperclip grep`. Useful for full-corpus\n"
            "regex queries (sub-second across 8M papers).",
            file=sys.stderr,
        )
        return 1
    cmd = ["paperclip", "grep"] + argv
    try:
        return subprocess.call(cmd)
    except FileNotFoundError:
        print(
            "vaultlab: paperclip CLI not on PATH. Install via:\n"
            "  pip install https://paperclip.gxl.ai/paperclip.whl",
            file=sys.stderr,
        )
        return 1


def _cmd_paperclip_sql(argv: list[str]) -> int:
    """Passthrough to ``paperclip sql``.

    Usage: ``vaultlab paperclip-sql "<query>"``
    """
    import subprocess
    if not argv or argv[0] in {"-h", "--help"}:
        print(
            "Usage: vaultlab paperclip-sql \"<query>\"\n"
            "\n"
            "Thin passthrough to `paperclip sql`. The corpus exposes a\n"
            "`documents` table with title/doi/authors/journal/etc.\n"
            "200-row limit per query.",
            file=sys.stderr,
        )
        return 1
    cmd = ["paperclip", "sql"] + argv
    try:
        return subprocess.call(cmd)
    except FileNotFoundError:
        print(
            "vaultlab: paperclip CLI not on PATH. Install via:\n"
            "  pip install https://paperclip.gxl.ai/paperclip.whl",
            file=sys.stderr,
        )
        return 1


def main(argv: list[str] | None = None) -> int:
    """Entry point registered in pyproject.toml as ``vaultlab``.

    Minimal dispatcher until the full click-based CLI lands.
    """
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv[0] in {"-h", "--help", "help"}:
        _print_usage()
        return 0

    cmd, rest = argv[0], argv[1:]
    if cmd == "init":
        return _cmd_init(rest)
    if cmd == "list-policy-skipped":
        return _cmd_list_policy_skipped(rest)
    if cmd == "fetch-list":
        return _cmd_fetch_list(rest)
    if cmd == "paperclip-grep":
        return _cmd_paperclip_grep(rest)
    if cmd == "paperclip-sql":
        return _cmd_paperclip_sql(rest)

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
        "  vaultlab init [<kb-root-path>]            Configure KB root\n"
        "  vaultlab list-policy-skipped <project>    Show LLM-refused papers\n"
        "  vaultlab fetch-list paywalled <log>       Manual-fetch shopping list\n"
        "  vaultlab paperclip-grep <pat> [path]      Regex over paperclip corpus\n"
        "  vaultlab paperclip-sql \"<query>\"          SQL over paperclip corpus\n"
        "\n"
        "Other commands (search, run, project, etc.) are exposed as Claude Code\n"
        "slash commands inside .claude/commands/. See README.md for the full\n"
        "inventory."
    )
    print(msg, file=stream)  # type: ignore[arg-type]


if __name__ == "__main__":
    raise SystemExit(main())
