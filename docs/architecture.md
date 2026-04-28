# vaultlab architecture

> **Status:** stub. The canonical architectural reference is the master plan at
> `G:/My Drive/Knowledge/ailab/Sources/Notes/architecture-grill-2026-04-26/99-MASTER-PLAN-vaultlab-shared-design.md`.
> This file will be populated in a migration commit with the public-facing version.

For now, see:

- [`README.md`](../README.md) — what vaultlab is + how to install
- [`CLAUDE.md`](../CLAUDE.md) — entrypoint for Claude Code sessions
- [`AGENTS.md`](../AGENTS.md) — invariants and conventions

## Quick reference: the four core commitments

1. **Markdown is the user-facing interface; Python is the engine.**
2. **Anti-laziness on semantic reading** — every LLM call requires quoted evidence.
3. **Result-oriented agentic loop** — bounded loop with internal verifiers; user sees finished result.
4. **KB is the smartness** — every analysis writes to KB; cross-project reasoning emerges via retrieval.

## Top-level package layout

See [`CLAUDE.md`](../CLAUDE.md) for the full tree.

## Distribution model

Hybrid C — fork-and-clone primary, PyPI secondary, MCP server deferred to v0.2.

```bash
git clone https://github.com/bobbyni819/vaultlab && cd vaultlab
pip install -e ".[all]"
vaultlab setup
```

## Coming in this doc (post-scaffold)

- Diagram of the package dependency graph
- Slash command inventory with type (pure capability vs orchestrated)
- Per-package architectural sketch
- The 9 invariants, restated for non-contributor readers
