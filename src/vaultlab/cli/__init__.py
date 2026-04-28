"""vaultlab CLI entry point.

Subcommands live in sibling modules (one .py + .md per subcommand):
    vaultlab setup, demo, doctor, evaluate, run, project, claude, kb, phase,
    manuscript, plan, stats

Conventions per AGENTS.md:
    - One file per subcommand
    - Each subcommand has a sibling .md describing what it does
    - The CLI uses click for argument parsing
"""

from __future__ import annotations


def main() -> None:
    """Entry point registered in pyproject.toml as `vaultlab`.

    NOTE: This is a placeholder during the v0.0.x scaffold phase. The full
    click-based dispatch will land as part of the migration commits.
    """
    print("vaultlab v0.0.1 — alpha scaffold. CLI dispatch coming in next migration commit.")
    print("See README.md for what's planned.")


if __name__ == "__main__":
    main()
