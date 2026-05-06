# Quickstart — paste this into Claude Code

The fastest way to set up vaultlab on a new machine is to paste the snippet below into a Claude Code chat. Claude does the entire bootstrap for you — clones the repo if missing, pip-installs, initializes the knowledge base, wires the slash commands globally, then asks what project you want to start.

## The snippet

Open Claude Code anywhere on your machine (an existing project folder is fine; an empty folder is also fine). Paste this verbatim:

```
Hi Claude. Set me up to use vaultlab — a research-companion harness
at github.com/bobbyni819/vaultlab. Please run this bootstrap sequence
end-to-end. Each step is idempotent — skip if already done.

1. Check if `vaultlab` is importable: `python -c "import vaultlab"`
   - If it fails: clone the repo to ~/code/vaultlab (or another sensible
     location), then `pip install -e <that-path>`. If `git` isn't on PATH,
     ask me to install it before proceeding.
   - If it succeeds: confirm version with `vaultlab --help`.

2. Run `vaultlab init` to set up my KB root. If it prompts interactively,
   accept the default (~/vaultlab-kb) for now — I can change it later.

3. Run `vaultlab claude-setup` to copy slash commands to ~/.claude/commands/
   and write a vaultlab pointer block to ~/.claude/CLAUDE.md.

4. Open the vaultlab repo's READ_FIRST.md and absorb the dispatch table
   (Step 3) and the role-pass discipline (Step 4). This is how you'll
   route my future natural-language asks to the right vaultlab primitive.

5. Once steps 1-4 are done, ask me: "What project do you want to set up?"
   When I describe my project, run /onboard-me to drive the natural-language
   intake.

After all 5 steps, give me a one-paragraph summary of what's installed,
where the KB lives, and which slash commands are now available. Then
wait for my project description.
```

## What Claude will do (step-by-step transparency)

When you paste this:

1. **Step 1 — Clone or confirm install**
   - Tries `python -c "import vaultlab"`
   - If missing: runs `git clone https://github.com/bobbyni819/vaultlab.git ~/code/vaultlab` then `pip install -e ~/code/vaultlab`
   - If already there: confirms version (currently v0.0.2 on PyPI; main branch may be ahead)

2. **Step 2 — KB root**
   - Runs `vaultlab init`
   - The prompt asks where your knowledge base should live; default is `~/vaultlab-kb`
   - Claude will accept the default unless you've told it a custom path
   - Persists to `~/.config/vaultlab/locations.toml` (one-time, never asks again)

3. **Step 3 — Wire Claude Code globally**
   - Runs `vaultlab claude-setup`
   - Copies 9 slash commands from vaultlab's `.claude/commands/*.md` → `~/.claude/commands/`
   - Writes (or appends to) `~/.claude/CLAUDE.md` a "## VaultLab" pointer block referencing `READ_FIRST.md`
   - **You may need to restart Claude Code after this step** for the global CLAUDE.md to be re-read; some sessions pick it up automatically, others don't

4. **Step 4 — Internalize the dispatch table**
   - Claude reads `vaultlab/READ_FIRST.md` from the cloned repo
   - Now has the natural-language → primitive mapping (lit search → `/lit-arc`, figure from data → `vaultlab.figures.recipes.*`, methodology audit → `rigor_auditor`, etc.)

5. **Step 5 — Ask what project**
   - Claude prompts: *"What project do you want to set up?"*
   - You describe your project in natural language: *"I'm doing CODEX multiplexed protein imaging on intestinal tissue, looking at lipid-class × cell-type spatial correlations. I have ~50 PDFs in a Box folder and ~5 GB of CODEX data on my D drive."*
   - Claude runs `/onboard-me` which parses your description into the structured project config + writes the initial KB skeleton

After step 5, you can:

- `/lit-arc <topic>` for literature search
- *"Make a marker dot-plot for these clusters"* → routes to `vaultlab.figures.recipes.marker_dot_plot`
- `/cite audit <draft.md>` for citation verification
- *"Explore this CSV"* → routes to `plan_deep_think_round` (after `/explore-data` lands in v0.1.0)
- Anything else from the dispatch table in `READ_FIRST.md`

## What if Claude Code doesn't have permission to run pip / git?

The snippet asks Claude to run shell commands. On most setups Claude Code can do this (with permission prompts the first time per command). If your setup blocks:

- `git clone` → install Git from https://git-scm.com first; or download the repo as a zip from the GitHub releases page
- `pip install` → tell Claude *"use `pip install --user vaultlab` instead"* if you don't have admin rights
- `vaultlab init` (interactive) → tell Claude *"use `vaultlab init ~/vaultlab-kb` to skip the prompt"*

Claude will retry with these alternatives if you mention them.

## What if you've already used vaultlab on this machine?

The snippet is idempotent. Step 1 finds the existing install. Step 2 reads the existing locations.toml. Step 3 detects the existing CLAUDE.md block and skips appending. Step 4-5 still run — Claude refreshes its understanding of the dispatch table and asks what you want to work on.

Safe to paste at the start of every fresh Claude Code session if you want a clean re-bind.

## Why a snippet instead of a CLI command?

Two reasons:

1. **Natural-language UX matters for adoption.** The PI's framing on 2026-05-06: *"how much time do I have to invest to get a similar output?"* — pasting a paragraph beats running 4 shell commands by hand. The snippet is the user's first experience of vaultlab; it should feel like talking to a colleague who knows what they're doing.

2. **Claude Code is the runtime anyway.** Even if you ran `pip install vaultlab && vaultlab init && vaultlab claude-setup` by hand, you'd still have to open Claude Code and ask it to read `READ_FIRST.md`. Folding that into the snippet saves a round-trip and lets Claude verify each step succeeded before moving on.

## Where to find vaultlab

- GitHub: https://github.com/bobbyni819/vaultlab
- PyPI: https://pypi.org/project/vaultlab/
- Issues / questions: https://github.com/bobbyni819/vaultlab/issues
