# Getting started — your first 10 minutes with vaultlab

This walks you from `git clone` to *"vaultlab knows about my project and I can ask Claude Code to do useful work."*

## Before you start

You need:
- **Python 3.12+** (`python --version`)
- **[Claude Code](https://claude.com/claude-code)** — vaultlab is Claude-Code-native. Your Claude Code subscription provides the LLM access; vaultlab does **not** need a separate Anthropic API key.
- **(Optional, recommended) Obsidian** ([download](https://obsidian.md)) — vaultlab's KB renders beautifully here
- **(Optional) A Google account or Microsoft 365 account** — for life-context integrations
- **(Optional) Literature API keys** ([setup-api-keys.md](setup-api-keys.md)) — most importantly NCBI (free, 5 min); others are progressively nice-to-have

You do **not** need:
- An Anthropic API key (Claude Code provides LLM access)
- A GPU (unless you opt into local meeting transcription)
- A subscription to anything beyond Claude Code itself
- Prior experience with Claude Code (vaultlab is a great way to learn it)

## Step 1: Clone + install (2 minutes)

```bash
git clone https://github.com/bobbyni819/vaultlab && cd vaultlab
pip install -e ".[all]"
```

Or, if you only want the literature + citations layer for now:

```bash
pip install vaultlab            # PyPI
```

## Step 2: Run `vaultlab setup` (3 minutes — interactive)

```bash
vaultlab setup
```

This is the **interview-driven first-run flow.** vaultlab asks you about your work and configures itself accordingly. You'll be asked:

1. **API keys** — Anthropic (required), and optionally NCBI / Semantic Scholar / Springer / bioRxiv. Skip what you don't have.
2. **Knowledge base location** — default `G:/My Drive/Knowledge/` on Windows, `~/Knowledge/` elsewhere. You can change it.
3. **Obsidian** — auto-detected; vaultlab installs the Advanced URI / Dataview / Templater plugins for you.
4. **Tell me about your projects** — see Step 3 below.
5. **(Optional) Google Workspace integration** — see [`setup-google.md`](setup-google.md)
6. **(Optional, Windows only) Outlook integration** — see [`setup-outlook-windows.md`](setup-outlook-windows.md)

> **Note:** in v0.0.1 (current) `vaultlab setup` is a placeholder. The interview flow lands in v0.1.0 (target May 27). For now you can edit `~/.config/vaultlab/config.json` directly. The structure below describes how it'll work.

## Step 3: Tell vaultlab about your projects

When `vaultlab setup` asks about your projects, you describe them one at a time:

```
> What project are you working on?
  Name: codex_lung
  Description: CODEX/MALDI lung tissue analysis with your PI
  Where do project files live? Z:/lab_data/CODEX/run_2024_03/
  Where do papers + notes go? G:/My Drive/Knowledge/codex_lung
  Domain: spatial metabolomics, lipid biology
  Target journal: Nature Metabolism

✓ Created project codex_lung
  - .vaultlab-project.json (in current directory or specified)
  - <kb>/codex_lung/ (knowledge base, initialized with START_HERE.md)
  - <kb>/codex_lung/.kb.json (KB metadata)

> Add another project? [Y/n]
```

**Each project gets its own KB folder.** You can have as many as you need:
- `codex_lung` for one analysis
- `influenza_modeling` for an unrelated computational project
- `thesis_committee` for non-research org-stuff
- `lit_dive_<topic>` for ad-hoc deep reads

Don't try to put everything in one KB. **One KB per project context** is the discipline that makes cross-session resume work.

## Step 4: Open in Claude Code (2 minutes)

```bash
cd vaultlab
claude
```

(Or open the folder in Claude Code's app.)

Claude Code reads `CLAUDE.md` first — it knows what vaultlab is and how to navigate. The first slash command to try:

```
> /research-status
```

Shows current focus across your projects, recent activity, suggested files to read first.

For a specific project:

```
> /research-status --project codex_lung
```

## Step 5: Onboard your first project (3 minutes)

If you have an existing project folder you want to use vaultlab on:

```
> /onboard-project ~/Downloads/CODEX_lung
```

vaultlab walks the folder structure, reads top-level docs, builds a draft project understanding via Claude (with quoted-evidence requirement so it doesn't fabricate), asks a few clarifying questions, and initializes:

- `<kb>/codex_lung/Wiki/Projects/codex_lung.md` — canonical understanding
- `<kb>/codex_lung/Wiki/Projects/codex_lung/START_HERE.md` — current focus + files to read first
- `~/Downloads/CODEX_lung/.vaultlab-project.json` — config

After this, every subsequent slash command in this project context updates `START_HERE.md` automatically. Future sessions know exactly where to resume.

---

## Best practices

These rules emerged from real research-lab use. Follow them and vaultlab works smoothly; ignore them and you'll have a frustrating time.

### 1. **One KB per Claude Code chat session**

Don't talk about multiple knowledge bases in the same chat. vaultlab's context-retrieval scopes to your default KB; switching mid-chat causes contamination (the LLM mixes findings from different projects in confusing ways).

If you need to switch KBs:
- Either: open a fresh Claude Code chat for the second project
- Or: explicitly `/kb switch <name>` and tell Claude *"now we're working on project B"* — but expect some hiccups

The cleanest discipline: **one chat = one project**. Most users find this is also the right cognitive grouping.

### 2. **One project per `.vaultlab-project.json`**

Every research project gets its own folder + its own `.vaultlab-project.json`. Don't put 5 projects under one config; vaultlab's per-project state machines (START_HERE, run history, manuscript drafts) assume one project per config.

If a project genuinely splits (e.g., main paper + methods companion), use the `manuscripts:` field in `.vaultlab-project.json` to track multiple manuscripts under one project.

### 3. **Create new KBs liberally**

Disk space is cheap. New domain or new collaborator? New KB. You can always merge later (Obsidian makes this easy with file-system-level `mv`). You can't easily un-mix mixed KBs.

vaultlab supports as many KBs as you have projects. The KB switcher (`vaultlab kb switch <name>`) handles the routing.

### 4. **Don't fight the markdown**

vaultlab stores everything as markdown. Don't try to bring in proprietary formats (Notion exports, Word docs) without converting. Convert to markdown first, then ingest.

```bash
# Good:
pandoc paper.docx -o paper.md && vaultlab kb ingest paper.md

# Bad:
vaultlab kb ingest paper.docx   # may work but loses structure
```

### 5. **Let vaultlab maintain `START_HERE.md`**

Don't manually edit `START_HERE.md`. vaultlab updates it after every meaningful slash command. Your edits will be preserved across the auto-managed sections (Recent activity, Files to read first, Open questions are auto-managed; the rest of the file is yours).

If you need to reset: `vaultlab kb start-here refresh --project <slug>`.

### 6. **Read the trace.jsonl when something goes weird**

Every vaultlab run writes a structured trace to `<kb>/.vaultlab/runs/<run_id>/trace.jsonl`. When an LLM call returns a confusing answer, the trace shows what went into the prompt and what came out.

```bash
vaultlab run last --json    # show last run's full trace
vaultlab run diff <a> <b>   # diff two runs (params + outputs)
```

### 7. **Treat hedged voice as a feature**

vaultlab's outputs hedge: *"consistent with X"* not *"is X"*. **This is intentional.** Reviewers expect scientific writing to hedge appropriately. If you find yourself wanting confident assertions, you're asking vaultlab to overclaim — that's bad science.

When you finalize a paper, you (the human author) make the calls about which hedges to keep and which to harden. vaultlab won't make that call for you.

### 8. **Use `/cite audit` before submitting anything**

Run `/cite audit <manuscript.md>` before sending a draft to your PI. It runs the full 3-tier verification on every `[N]` and flags `WEAKLY_SUPPORTED` / `NOT_FOUND` / `HALLUCINATED`. Fix flags before submission.

This is the difference between vaultlab being useful and vaultlab being embarrassing.

### 9. **Don't enable Google + Outlook on regulated mailboxes**

If your institutional account has PHI or IRB-restricted data, **don't connect vaultlab to it**. Use a personal Google account or a separate non-regulated Microsoft account. See [`compliance.md`](compliance.md).

### 10. **Pick up where you left off**

When you come back to a project after time away:

```
> Read <kb>/<project>/Wiki/Projects/<slug>/START_HERE.md
```

Tell Claude Code that. It catches up in 30 seconds. Then ask whatever you'd ask a colleague who'd been on the project last week.

---

## What now?

- **Try the demo:** `vaultlab demo pbmc3k` (lands fully in v0.1.0; placeholder in v0.0.1)
- **Read the architecture:** [`architecture.md`](architecture.md)
- **See what slash commands exist:** [`.claude/commands/COMMANDS.md`](../.claude/commands/COMMANDS.md)
- **Understand what vaultlab is uniquely yours vs borrowed:** [`ORIGINAL-CONTRIBUTIONS.md`](ORIGINAL-CONTRIBUTIONS.md)
- **For contributors:** [`../CONTRIBUTING.md`](../CONTRIBUTING.md), [`../AGENTS.md`](../AGENTS.md)

## Stuck?

```bash
vaultlab doctor
```

Diagnoses common setup issues. If output isn't enough:

- Open an issue: https://github.com/bobbyni819/vaultlab/issues
- Check [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) — vaultlab is alpha; some things are placeholders
