---
name: using-vaultlab
description: Entry-point skill for working with vaultlab. Loaded automatically by Claude Code when this repo is opened. Establishes vaultlab's architecture and conventions before any other action.
---

# Using vaultlab

You are working in the **vaultlab** repository — an open-source AI lab for biological researchers, designed as a capability layer FOR Claude Code (you).

Before doing anything else, read in this order:

1. [`README.md`](../../../README.md) — what vaultlab is
2. [`CLAUDE.md`](../../../CLAUDE.md) — repo entrypoint with reading order + structure + common tasks
3. [`AGENTS.md`](../../../AGENTS.md) — invariants and conventions

## Most-important rules

1. **Markdown is the user-facing interface; Python is the engine.** When asked to add a prompt, role, recipe, layout, or skill — these are MARKDOWN files in the repo. Never embed prompts as triple-quoted Python strings.

2. **Anti-laziness rule for any LLM call you make.** Prompts must REQUIRE quoted evidence. Use phrases: "quote the exact sentence supporting this," "if you cannot quote, the claim is NOT_FOUND."

3. **Hedged voice for any interpretation/hypothesis output.** Use: *"consistent with X"*, *"suggests"*, *"may indicate"*. Never: *"is X"*, *"proves"*, *"demonstrates."*

4. **Use templates** for new recipes, roles, slash commands, data modalities, tool index entries, pipeline phases — see `templates/`.

5. **Tests must stay green** on every commit. Run `pytest -m "not llm"` before claiming work is complete.

6. **Provenance receipts** are written automatically by `vaultlab.provenance`. Don't bypass them.

7. **Writing + PDF-citation practices.** For thesis, proposal, or grant prose and for zero-hallucination
   citation work, follow [`docs/writing-and-citation-practices.md`](../../../docs/writing-and-citation-practices.md)
   (consumed by `/style-check` and `/cite`). No em-dashes, no arrows, no filler, US English, capabilities-only
   honesty; every citation read from its actual PDF page images, no-PDF means UNVERIFIED.

## When the user asks you to extend vaultlab

Always:
1. Identify which subpackage the addition belongs to (per `CLAUDE.md` structure)
2. Use the appropriate template
3. Run `vaultlab claude validate` after creating files
4. Add tests
5. Confirm AGENTS.md invariants are preserved

## When the user asks you to use vaultlab on their data

1. First check if `.vaultlab-project.json` exists — load it to know data sources
2. Suggest a slash command: `/discover-data <path>` for unknown data, `/analyze "<question>"` for known datasets
3. Show the user `vaultlab doctor` output if anything seems off
4. Outputs land in the user's KB (per `.vaultlab-project.json` `kb_path`)

## When in doubt

Read `CLAUDE.md`. Read `AGENTS.md`. Then ask the user.
