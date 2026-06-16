Build or refresh the project's ubiquitous language — a shared glossary of domain terminology that you and Bobby use the same way. Inspired by Domain-Driven Design and Matt Pocock's "Claude Code for real engineers" talk.

The point: when you and Bobby use the same terms with the same meanings, planning is tighter, code is more aligned, and AI thinking traces are less verbose.

## When to use

- Starting work in a new project (run once to establish baseline)
- After major architectural changes (refresh)
- When Bobby explicitly invokes `/ubiquitous-language`
- When you notice yourself or Bobby using a term inconsistently

## How to detect existing UL

A project has ubiquitous language if it has any of:

1. `<repo>/_Ubiquitous_Language.md` (preferred for code projects)
2. `<kb-root>/Wiki/_Ubiquitous_Language.md` (for KB-based projects like metabolism, equities)
3. A "## Ubiquitous Language" or "## Glossary" section in `CLAUDE.md`

If one exists, refresh it. If not, build from scratch.

## Step 1: Survey the codebase / KB

For a code project: scan
- All Python module names and key classes (`grep -r "^class \|^def "` in src/)
- Config keys in CLAUDE.md and `_DEFAULT_CONFIG` dicts
- CLI subcommand names
- Domain-specific identifier patterns (e.g. lipid names in metabolism, ticker symbols in equities)

For a KB: scan
- All filenames in `Wiki/Concepts/` and `Wiki/Methodology/`
- All `[[wiki-link]]` references in `_Index.md`
- Tag values in YAML frontmatter (`tags: [biology, methodology, ...]`)

## Step 2: Extract terms with meanings

For each term, capture:
- **Term** — the canonical word/phrase
- **Definition** — one-line plain-English meaning
- **Aliases** — other names you've seen for it (so we don't drift)
- **Used in** — which files / modules / contexts use it

Group terms into categories. Suggested categories:
- **Domain entities** — the things the project is about (e.g. "session" in dashboard, "lipid program" in metabolism)
- **Operations** — the verbs (e.g. "ingest", "lint", "compile")
- **Components / modules** — code structures
- **States / statuses** — lifecycle terms (e.g. "PLANNED", "ACTIVE", "ARCHIVED")
- **Files / artifacts** — common file types (e.g. "deal memo", "meeting prep")

## Step 3: Write the file

For code projects, write to `<repo>/_Ubiquitous_Language.md`:

```markdown
# Ubiquitous Language — <project>

Shared terminology for this project. Bobby and AI sessions use these exact terms with these exact meanings. If a term is missing or wrong, update this file.

## Domain entities

| Term | Definition | Aliases | Used in |
|------|------------|---------|---------|
| Session | A long-lived Claude Code conversation tied to a working directory | "chat", "conversation" | bobby_dashboard, /kb |
| Task  | A single prompt-response cycle within a session | "message", "turn" | bobby_dashboard |

## Operations

| Term | Definition |
|------|------------|
| Ingest | Add a new source to a KB and update wiki cross-references |
| Lint | Health-check a KB for contradictions, orphans, stale claims |

(... etc)
```

For KB projects, write to `<kb-root>/Wiki/_Ubiquitous_Language.md` and link it from `_Index.md`.

## Step 4: Inline a "Core Terms" section in CLAUDE.md

After writing the full glossary, append (or update) a compact "Core Terms" section to the project's `CLAUDE.md` — top 10-15 most-used terms, one line each. This stays in the always-loaded system prompt so AI sessions get the essentials for free without looking up the file.

```markdown
## Core Terms

- **Session** — long-lived Claude Code conversation in a working directory
- **Task** — one prompt-response cycle in a session
- **Adapter** — interface between dashboard and a Claude Code subprocess
- (... 10-15 lines max)

Full glossary: see `_Ubiquitous_Language.md`.
```

## Step 5: Verify and commit

- Show Bobby the new/refreshed file.
- Ask if any terms are wrong or missing.
- Commit with a clear message: `Add ubiquitous language glossary` or `Refresh ubiquitous language`.

## Anti-patterns

- Including every variable name in the codebase (only domain-meaningful terms)
- Using AI-generic definitions instead of project-specific ones
- Skipping the CLAUDE.md inline section (the whole point is that AI sees the core terms by default)
- Letting the file go stale — refresh it after major changes

## Reference

The convention to ALWAYS check for `_Ubiquitous_Language.md` (in repo root or KB Wiki/) and CLAUDE.md "Core Terms" section is in the global CLAUDE.md. This skill is for building / refreshing that file.
