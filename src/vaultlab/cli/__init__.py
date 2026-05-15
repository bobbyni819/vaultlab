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
    print(
        "Sorted by publisher cluster (Nature → Cell → Science → Wiley → "
        "Springer → other Elsevier → other).\n"
    )
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


def _cmd_slides(argv: list[str]) -> int:
    """Dispatch ``vaultlab slides <subcommand> ...``.

    Subcommands:
        review <pptx> [--html <out>]   Run the self-review pass on a rendered deck.
    """
    if not argv or argv[0] in {"-h", "--help"}:
        print(
            "Usage: vaultlab slides review <pptx> [--html <out>]\n"
            "\n"
            "  Runs the composite self-review pass (layout hard rules + story-arc\n"
            "  structural checks + bullet density + figure presence) on a rendered\n"
            "  .pptx. Prints a summary to stdout; emits an HTML report (with the\n"
            "  same look as the rigor-audit reports) when --html is supplied.",
            file=sys.stderr,
        )
        return 1
    sub, rest = argv[0], argv[1:]
    if sub == "review":
        return _cmd_slides_review(rest)
    print(f"vaultlab slides: unknown subcommand {sub!r}", file=sys.stderr)
    return 1


def _cmd_slides_review(argv: list[str]) -> int:
    """Run :func:`vaultlab.slides.review_deck` on a ``.pptx`` and print a summary."""
    if not argv or argv[0] in {"-h", "--help"}:
        print(
            "Usage: vaultlab slides review <pptx> [--html <out>]\n"
            "\n"
            "Exit codes:\n"
            "  0  no critical issues (warnings/info may be present)\n"
            "  2  at least one critical issue found\n"
            "  1  usage error / file not found",
            file=sys.stderr,
        )
        return 1
    html_out: Path | None = None
    pptx_path: Path | None = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--html":
            if i + 1 >= len(argv):
                print("vaultlab slides review: --html requires a path", file=sys.stderr)
                return 1
            html_out = Path(argv[i + 1]).expanduser()
            i += 2
            continue
        if a.startswith("--"):
            print(f"vaultlab slides review: unknown flag {a}", file=sys.stderr)
            return 1
        if pptx_path is None:
            pptx_path = Path(a).expanduser()
            i += 1
            continue
        print(f"vaultlab slides review: unexpected argument {a}", file=sys.stderr)
        return 1

    if pptx_path is None:
        print("vaultlab slides review: need a <pptx> path", file=sys.stderr)
        return 1
    if not pptx_path.exists():
        print(f"vaultlab slides review: file not found: {pptx_path}", file=sys.stderr)
        return 1

    from vaultlab.slides.self_review import review_deck, write_review_report

    report = review_deck(pptx_path)

    print(f"vaultlab slides review — {pptx_path}")
    for line in report.summary_lines():
        print(f"  {line}")
    if not report.ok() or report.n_warning > 0:
        print("\nIssues:")
        for issue in report.all_issues():
            sev = issue.get("severity", "info").upper()
            rule = issue.get("rule", "")
            loc = issue.get("loc", "")
            detail = issue.get("detail", "")
            print(f"  [{sev}] {loc} {rule}: {detail}")

    if html_out is not None:
        written = write_review_report(report, html_out)
        print(f"\nHTML report: {written}")

    return 2 if not report.ok() else 0


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
            'Usage: vaultlab paperclip-sql "<query>"\n'
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


def _find_vaultlab_repo_root() -> Path | None:
    """Locate the vaultlab repo root (where READ_FIRST.md + .claude/commands/ live).

    Strategy: start from the installed ``vaultlab`` package location and walk
    up looking for the marker files. Works for editable installs and for
    git-cloned-and-pip-installed cases. Returns ``None`` if not found
    (typical of pure-PyPI installs without the source repo on disk).
    """
    import vaultlab

    pkg_path = (
        Path(vaultlab.__file__).resolve().parent
    )  # .../site-packages/vaultlab/ OR .../src/vaultlab/
    for candidate in [pkg_path, *pkg_path.parents]:
        if (candidate / "READ_FIRST.md").exists() and (candidate / ".claude" / "commands").is_dir():
            return candidate
    return None


def _cmd_claude_setup(argv: list[str]) -> int:
    """Wire vaultlab into Claude Code globally — slash commands + global CLAUDE.md.

    Closes a friction point a fresh user hits: they pip install vaultlab,
    they open Claude Code in their own project, and Claude has no idea
    vaultlab exists. This subcommand:

    1. Copies vaultlab's ``.claude/commands/*.md`` -> ``~/.claude/commands/``
       so its slash commands appear in EVERY Claude Code session, not only
       sessions opened in the vaultlab repo
    2. Writes (or appends to) ``~/.claude/CLAUDE.md`` a "## VaultLab" pointer
       block citing the absolute path of vaultlab's ``READ_FIRST.md`` so any
       fresh session reads the dispatch table first

    Idempotent — safe to re-run after ``git pull`` to refresh the slash
    commands. Won't duplicate the CLAUDE.md block if already present.

    Usage:
        vaultlab claude-setup [--dry-run]
    """
    import datetime
    import shutil

    dry_run = "--dry-run" in argv

    repo_root = _find_vaultlab_repo_root()
    user_claude = Path.home() / ".claude"
    user_commands = user_claude / "commands"
    user_claude_md = user_claude / "CLAUDE.md"

    if dry_run:
        print("vaultlab claude-setup --dry-run — no files will be modified.\n")

    if repo_root is None:
        print(
            "vaultlab: cannot locate vaultlab repo root on this machine.\n"
            "  Slash-command copy will be skipped. CLAUDE.md block can still\n"
            "  be written (it will reference the package path instead of repo).\n"
            "\n"
            "  To get full setup, clone the repo and pip-install editable:\n"
            "    git clone https://github.com/bobbyni819/vaultlab\n"
            "    pip install -e ./vaultlab\n"
            "    vaultlab claude-setup",
            file=sys.stderr,
        )
        repo_marker = "(pure PyPI install — slash commands not auto-copied)"
    else:
        src_commands = repo_root / ".claude" / "commands"
        n_copied = 0
        skipped_meta = {"README.md", "COMMANDS.md"}
        if not dry_run:
            user_commands.mkdir(parents=True, exist_ok=True)
        for md in sorted(src_commands.glob("*.md")):
            if md.name in skipped_meta:
                continue
            target = user_commands / md.name
            if dry_run:
                print(f"  [dry-run] would copy: {md.name} -> {target}")
            else:
                shutil.copy(md, target)
            n_copied += 1
        if not dry_run:
            print(f"vaultlab: copied {n_copied} slash command(s) to {user_commands}")
        else:
            print(f"vaultlab: [dry-run] would copy {n_copied} slash command(s) to {user_commands}")
        repo_marker = str(repo_root)

    block_marker = "## VaultLab — research companion harness"
    today = datetime.date.today().isoformat()
    if repo_root is not None:
        read_first_path = repo_root / "READ_FIRST.md"
    else:
        read_first_path = Path(
            "(see https://github.com/bobbyni819/vaultlab/blob/main/READ_FIRST.md)"
        )
    block = (
        f"\n{block_marker}\n\n"
        f"Installed at: `{repo_marker}`\n\n"
        f"When the user asks anything related to literature search, figure generation, "
        f"data analysis, citation auditing, manuscript drafting, deck building, or any "
        f"knowledge-base-driven research workflow: read `{read_first_path}` FIRST. "
        f"It has the dispatch table that maps natural-language asks to vaultlab primitives "
        f"(`/lit-arc`, `/build-deck`, `/cite audit`, `methods_critic`, `rigor_auditor`, "
        f"figure recipes, plus state-aware additive defaults).\n\n"
        f"Slash commands installed at `{user_commands}` are vaultlab's; they appear in every "
        f"Claude Code session.\n\n"
        f"Auto-installed by `vaultlab claude-setup` on {today}. Re-run after `git pull` to refresh.\n"
    )

    if user_claude_md.exists():
        existing = user_claude_md.read_text(encoding="utf-8")
        if block_marker in existing:
            if dry_run:
                print(
                    f"vaultlab: [dry-run] {user_claude_md} already has vaultlab block (would skip)"
                )
            else:
                print(f"vaultlab: {user_claude_md} already has vaultlab block (skipping append)")
        else:
            new_content = existing.rstrip() + "\n" + block
            if dry_run:
                print(f"vaultlab: [dry-run] would append vaultlab block to {user_claude_md}")
            else:
                user_claude_md.write_text(new_content, encoding="utf-8")
                print(f"vaultlab: appended vaultlab block to {user_claude_md}")
    else:
        if dry_run:
            print(f"vaultlab: [dry-run] would create {user_claude_md} with vaultlab block")
        else:
            user_claude_md.parent.mkdir(parents=True, exist_ok=True)
            user_claude_md.write_text(block.lstrip("\n"), encoding="utf-8")
            print(f"vaultlab: created {user_claude_md} with vaultlab block")

    if not dry_run:
        print(
            "\nDone. Open Claude Code anywhere on this machine.\n"
            "  - Slash commands: now globally available\n"
            "  - First-message routing: Claude reads READ_FIRST.md and dispatches per the table"
        )
    return 0


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
    if cmd == "demo":
        from vaultlab.cli.demo import main as _demo_main

        return _demo_main(rest)
    if cmd == "list-policy-skipped":
        return _cmd_list_policy_skipped(rest)
    if cmd == "fetch-list":
        return _cmd_fetch_list(rest)
    if cmd == "paperclip-grep":
        return _cmd_paperclip_grep(rest)
    if cmd == "paperclip-sql":
        return _cmd_paperclip_sql(rest)
    if cmd == "claude-setup":
        return _cmd_claude_setup(rest)
    if cmd == "slides":
        return _cmd_slides(rest)

    print(f"vaultlab: unknown command {cmd!r}", file=sys.stderr)
    _print_usage(stream=sys.stderr)
    return 1


def _print_usage(stream: object = None) -> None:
    if stream is None:
        stream = sys.stdout
    msg = (
        "vaultlab v0.0.3 — alpha\n"
        "\n"
        "Usage:\n"
        "  vaultlab demo [--out-dir <path>]          First-run audit-clean artifact (<5 min)\n"
        "  vaultlab init [<kb-root-path>]            Configure KB root (one-time)\n"
        "  vaultlab claude-setup [--dry-run]         Wire slash commands + global CLAUDE.md\n"
        "  vaultlab list-policy-skipped <project>    Show LLM-refused papers\n"
        "  vaultlab fetch-list paywalled <log>       Manual-fetch shopping list\n"
        "  vaultlab slides review <pptx> [--html <o>] Self-review a rendered deck\n"
        "  vaultlab paperclip-grep <pat> [path]      Regex over paperclip corpus\n"
        '  vaultlab paperclip-sql "<query>"          SQL over paperclip corpus\n'
        "\n"
        "First-time setup (recommended order):\n"
        "  pip install vaultlab\n"
        "  vaultlab demo                              # produce your first artifact (<5 min)\n"
        "  vaultlab init                              # set KB root\n"
        "  vaultlab claude-setup                      # make slash commands global\n"
        "\n"
        "Other commands (search, run, project, etc.) are exposed as Claude Code\n"
        "slash commands inside .claude/commands/. See README.md for the full\n"
        "inventory."
    )
    print(msg, file=stream)  # type: ignore[arg-type]


if __name__ == "__main__":
    raise SystemExit(main())
