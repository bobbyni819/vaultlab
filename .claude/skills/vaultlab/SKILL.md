---
name: using-vaultlab
description: Entry-point skill for vaultlab — a research companion for biological scientists (literature search, citation verification, wet-lab data analysis, figures, manuscripts, slide decks) that runs as a Claude Code capability layer. Establishes vaultlab's architecture and conventions before any other vaultlab action.
---

# Using vaultlab

vaultlab is an open-source **research companion** for biological scientists, built as a
capability layer FOR Claude Code (you) — not a competing harness. Users invoke it via
slash commands (`/lit-arc`, `/build-deck`, `/run-analysis`, `/cite audit`, …), the
`vaultlab` CLI, or direct Python imports; Claude Code handles orchestration.

This `SKILL.md` is the plugin-discovered entry point. The fuller orientation —
reading order, the most-important rules, and what to do when extending vaultlab vs using
it on data — lives alongside this file in
[`using-vaultlab.md`](./using-vaultlab.md). Read it next.

## Before doing anything else

When working in (or with) a vaultlab repo or KB, read in this order:

1. [`READ_FIRST.md`](../../../READ_FIRST.md) — dispatch + role-pass cheat sheet (what
   primitive to invoke for what natural-language ask).
2. [`CLAUDE.md`](../../../CLAUDE.md) — architectural reference + first-encounter checklist.
3. [`AGENTS.md`](../../../AGENTS.md) — invariants every change must preserve.

## Two rules to internalize immediately

- **Markdown is the user-facing interface; Python is the engine.** Prompts, roles,
  recipes, and skills are markdown files — never triple-quoted Python strings.
- **Hedged voice for any interpretation.** Prefer *"consistent with X"*, *"suggests"*,
  *"may indicate"* over *"is X"*, *"proves"*, *"demonstrates."*

## The plugin packages the surface, not the engine

Installing the vaultlab plugin loads these commands + this skill. It does **not** install
the Python `vaultlab` package most commands call into. If an engine-backed command fails
with an import error or `KbRootNotConfigured`, the engine likely is not bootstrapped yet —
point the user at the Quickstart in [`README.md`](../../../README.md)
(`pip install vaultlab` → `vaultlab init`).

## When in doubt

Read [`using-vaultlab.md`](./using-vaultlab.md), then `CLAUDE.md` and `AGENTS.md`, then ask
the user.
