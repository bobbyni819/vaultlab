# vaultlab.status

A **reserved, not-yet-implemented** package slot earmarked for the `/research-status` project-status reporter. As of this writing it is an empty placeholder with no public API.

> Plain-language subsystem guide: `G:/My Drive/Knowledge/vaultlab/Wiki/Concepts/vaultlab-subsystems.md`.
> Architectural map: [`docs/architecture.md`](../../../docs/architecture.md) (lists `status/` as "`/research-status` implementation").

## What it is

`vaultlab.status` is a placeholder that the architecture reserves for a project-status reporter — the thing that would answer *"where does this project stand right now?"* by reading the KB and summarizing pipeline state, recent work, and next steps. Right now the package contains nothing but a module docstring (`"""Placeholder. Will be populated by migration commits."""`); the `/research-status` behavior described in `docs/architecture.md` and `CLAUDE.md` has **not** been migrated into it yet. Treat this directory as a named intent, not a working component — nothing in the repo imports it, and it exports no symbols.

If you are looking for status-like functionality that *does* exist today, see the START_HERE auto-update layer in [`vaultlab.kb`](../kb/start_here.py) and the weekly-status HTML report under `vaultlab.report` (tested in `tests/test_vaultlab_report/test_weekly_status_html.py`) — those are separate from this slot.

## Public surface

This package currently has **no public API**. `__init__.py` defines no `__all__`, no classes, and no functions — only a placeholder docstring. There is nothing here to import or call yet.

When the `/research-status` reporter is migrated in, this section should be replaced with the real exported symbols.

## How it fits

Today: nothing reads from or writes to `vaultlab.status` — it sits unwired in the tree.

As intended (per `docs/architecture.md` and `CLAUDE.md`): this slot is meant to back the `/research-status` slash command, reading project state from the KB (`START_HERE.md`, `decisions-log.md`, the project's `Output/` glob, pipeline/provenance receipts) and emitting a human-readable "where things stand" summary — *current focus, recent activity, files to read next*.

The intent is more than a code comment: `/research-status` is listed in the slash-command inventory (`.claude/commands/COMMANDS.md`) as an available command. But that listing is aspirational — there is **no** `research-status.md` command spec, **no** CLI subcommand (`vaultlab status` does not exist), and **no** Python here to invoke. Until the migration lands, a user who tries `/research-status` finds nothing wired up behind it.

## What it does NOT do

- It does **not** implement `/research-status` yet — the directory is reserved, not built.
- It does **not** export any importable symbol; `import vaultlab.status` gives you an empty module.
- It is **not** the weekly-status report — that lives in `vaultlab.report`, not here.
- It does **not** maintain `START_HERE.md` — that is `vaultlab.kb.start_here`'s job.

## Files

- `__init__.py` — placeholder module; docstring only, no public surface.

## See also

- [`vaultlab.kb`](../kb/README.md) — the KB layer; `start_here.py` is the existing project-state surface this reporter would read from.
- [`vaultlab.report`](../report/README.md) — where the weekly-status HTML report actually lives.
- [`docs/architecture.md`](../../../docs/architecture.md) — the architectural sketch that reserves this slot for `/research-status`.
- `CLAUDE.md` (repo root) — top-level package map listing `status/` as "`/research-status` implementation".
