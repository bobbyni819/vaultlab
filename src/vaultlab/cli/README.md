# vaultlab.cli

The `vaultlab` command-line entry point — the handful of things you run in a terminal, not in a Claude Code chat.

Plain-language companion: the **Onboarding + setup** section of the KB guide `Wiki/Concepts/vaultlab-subsystems.md` (`bobby-kb open vaultlab/Wiki/Concepts/vaultlab-subsystems.md`). Architectural context: [`docs/architecture.md`](../../../docs/architecture.md).

## What it is

Almost all of vaultlab is meant to be driven by Claude Code through slash commands and Python imports, not typed by hand. This package is the small exception: the `vaultlab` shell command, registered in `pyproject.toml` as `vaultlab = "vaultlab.cli:main"`. It exists for the few jobs that happen *outside* a chat session — confirming your install works, pointing vaultlab at where your knowledge base lives, wiring the slash commands into Claude Code globally, and a couple of human-triage utilities (which papers got skipped, which paywalled DOIs you still need to fetch by hand). It is deliberately a thin, hand-rolled dispatcher: `main()` reads `argv[0]`, routes to one `_cmd_*` handler, and returns a shell exit code. The full click-based CLI sketched in the module docstring is still pending, so the subcommand subdirectories (`cli/kb/`, `cli/run/`, `cli/project/`, …) are placeholders today.

## Public surface

The package exposes one real entry point plus the demo's reusable API. Everything else is internal command handlers (the `_cmd_*` functions) reached only through `main`.

- `main(argv=None) -> int` — the `vaultlab` shell entry point. Dispatches the first argument to a subcommand and returns the process exit code. With no args or `--help`, prints usage.
- `vaultlab.cli.demo.run_demo(out_dir=...) -> Path` — runs the offline first-run demo end-to-end and returns the path to the rendered `.pptx`. Importable from scripts and tests, not just the CLI.
- `vaultlab.cli.demo.main(argv=None) -> int` — the `vaultlab demo` subcommand wrapper (argparse-based; supports `--out-dir`).

The subcommands routed by `main` (each a `_cmd_*` handler, invoked as `vaultlab <name>`):

- `init` — set where your knowledge base lives. Interactive prompt, or `vaultlab init <path>` to skip it; persists to `~/.config/vaultlab/locations.toml` so every later orchestrator and slash command resolves the same KB root.
- `demo` — produce a real, audit-clean slide deck from bundled sample data, fully offline, in seconds. The "does my install work?" command.
- `claude-setup` — wire vaultlab into Claude Code globally: copies its `.claude/commands/*.md` into `~/.claude/commands/` and appends a pointer block to `~/.claude/CLAUDE.md`. Idempotent; supports `--dry-run`.
- `list-policy-skipped <project>` — print the papers the LLM refused to summarize (from a project's `policy_skipped.json`) so you can triage them by hand.
- `fetch-list paywalled <log>` — turn an acquisition log into a manual-fetch shopping list of paywalled DOIs, grouped by publisher cluster with URL hints and a drop-the-PDF-here path.
- `slides review <pptx> [--html <out>]` — run the slide self-review pass (layout hard rules, story-arc checks, bullet density, figure presence) on a rendered deck; exit `2` if any critical issue is found.
- `paperclip-grep <pattern> [path]` — thin passthrough to the `paperclip` CLI's `grep` (regex over the external full-text corpus).
- `paperclip-sql "<query>"` — thin passthrough to `paperclip sql` (SQL over the corpus's `documents` table).

## How it fits

This package is the seam between the shell and the rest of vaultlab; it owns no science of its own and delegates everything to other packages. `init` calls into `vaultlab.context.locations` (`register_path`, `resolve_kb_root`) — and the path it persists is what *every* downstream primitive reads to find the KB. `demo` composes a `vaultlab.slides.deck.DeckPlan` and renders it via `build_deck`, then writes receipts with `vaultlab.provenance.write_receipts`, from sample data bundled in `vaultlab.data.demo`. `slides review` calls `vaultlab.slides.self_review`. The two triage commands read JSON written by `vaultlab.research.policy_skip`. `claude-setup` copies from the repo's `.claude/commands/` and writes the global `~/.claude/CLAUDE.md`, which is the mechanism by which a fresh Claude Code session anywhere on the machine learns vaultlab exists and reads `READ_FIRST.md` first.

Upstream of it: the user, and the bootstrap scripts (`scripts/bootstrap.ps1` / `.sh`) which call `vaultlab claude-setup` as their last step. Downstream of it: Claude Code sessions (which inherit the slash commands and the KB-root config) and the rendered demo artifact on disk.

## What it does NOT do

- It is **not** the home of vaultlab's features. Literature search, figure generation, lit-arcs, citation auditing, manuscript drafting, deck building, and analysis are Claude Code slash commands and Python APIs — not `vaultlab <subcommand>`. The CLI surface is intentionally tiny.
- It does **not** implement any analysis itself. `demo` composes a deck deterministically from bundled metadata with no LLM and no network; `slides review` and the triage commands only read and report on artifacts other packages produced.
- The subcommand subdirectories (`cli/kb/`, `cli/run/`, `cli/project/`, `cli/manuscript/`, `cli/plan/`, `cli/stats/`, `cli/phase/`, `cli/evaluate/`, `cli/claude/`) are **placeholders** — the full click-based dispatch in the docstring has not landed; only the `main` routes listed above work.
- It does **not** break paywalls or log into your institution. `fetch-list paywalled` just produces the shopping list of what you still have to fetch by hand.

## Files

- `__init__.py` — the dispatcher: `main` plus the `_cmd_*` handlers (`init`, `claude-setup`, `list-policy-skipped`, `fetch-list`, `slides`, `paperclip-grep`, `paperclip-sql`) and the usage printer.
- `demo.py` — the `vaultlab demo` subcommand and its reusable `run_demo` API (offline deck + provenance from bundled sample data).
- `demo.md` — what `vaultlab demo` does, why it exists (the time-to-first-artifact north-star), and the test contract.
- `claude_setup.md` — what `vaultlab claude-setup` does and the friction it closes (Claude Code not knowing vaultlab exists).
- `claude/`, `evaluate/`, `kb/`, `manuscript/`, `phase/`, `plan/`, `project/`, `run/`, `stats/` — placeholder subdirectories awaiting the full click-based CLI.

## See also

- [`vaultlab.context`](../context/README.md) — `resolve_kb_root` / `register_path` / `locations.toml`, the KB-root config `init` writes.
- [`vaultlab.slides`](../slides/README.md) — `build_deck` (used by `demo`) and `self_review` (used by `slides review`).
- [`vaultlab.provenance`](../provenance/README.md) — the receipts `demo` writes next to the deck.
- [`vaultlab.research`](../research/README.md) — `policy_skip`, the source of the `list-policy-skipped` / `fetch-list` data.
- `READ_FIRST.md` (repo root) — the dispatch table `claude-setup` points fresh Claude Code sessions at; the real feature surface lives there, not in this CLI.
