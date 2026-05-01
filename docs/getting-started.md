# Getting started with VaultLab

(Audience: a researcher who just installed VaultLab. ~10–15 minutes from zero to your first useful KB output.)

> VaultLab is **alpha software**. v0.0.1 is mostly architectural scaffold; v0.1.0 lands late May 2026. Where something is not yet wired up, this guide says so. If anything breaks, [file an issue](https://github.com/bobbyni819/vaultlab/issues).

---

## Step 0 — What VaultLab gives you (60 seconds)

VaultLab is one tool that does four things, all sharing the same plain-markdown knowledge base:

1. **Knowledge base.** Your papers, notes, findings, and project state live as markdown files in a folder you pick — local disk, Google Drive, OneDrive, Dropbox, a lab NAS, anywhere that syncs. Obsidian renders it; you can share it with a labmate the way you'd share any folder.
2. **Citation-verified writing.** When you draft text with `[N]` markers, VaultLab checks every citation against the actual source paper and flags hallucinations before you ship.
3. **Slide decks** (`/build-deck <topic>`, v0.1.0) composed from whatever's in your KB — a paper PDF, your data, a manuscript draft, or just a topic.
4. **A literature + analysis stack you already trust.** PubMed / Semantic Scholar / CrossRef / bioRxiv for search; scanpy / squidpy / scikit-image for analysis. VaultLab calls real functions in real packages — nothing fabricated.

This guide takes you from clone to your first useful KB entry. No coding background required.

---

## Step 1 — Install (3 minutes)

```bash
pip install vaultlab
```

Or, if you want the editable / development install:

```bash
git clone https://github.com/bobbyni819/vaultlab && cd vaultlab
pip install -e ".[all]"
```

`[all]` pulls every optional dependency. If you only want the literature + citations layer, `pip install vaultlab[research,citations,kb]` is enough.

Verify the install:

```bash
python -c "import vaultlab; print(vaultlab.__version__)"
# 0.0.1
```

You also need **[Claude Code](https://claude.com/claude-code)**. VaultLab is Claude-Code-native: the LLM access comes through your existing Claude Code subscription. **No separate Anthropic API key required** for the slash-command path.

(Recommended but not required: install **[Obsidian](https://obsidian.md)**. The KB is plain markdown — any editor works — but Obsidian's wikilink graph is where cross-paper navigation pays off. Free for personal and academic use.)

---

## Step 2 — Initialize your first knowledge base (2 minutes)

A "knowledge base" is just a folder with a few standard subdirectories. Pick somewhere sensible — a synced cloud folder if you want to share with collaborators, or a local directory if you're solo:

```bash
~/research-kb/             # local
# or
~/Dropbox/research-kb/     # synced via Dropbox
# or
<your-cloud-drive>/research-kb/   # Google Drive / OneDrive / etc.
```

### Option A — `vaultlab init` (recommended)

```bash
vaultlab init ~/research-kb
```

This persists your KB root to `~/.config/vaultlab/locations.toml` so every later command picks it up automatically. Run this once per machine.

### Option B — Initialize the Obsidian config in Python

```python
from pathlib import Path
from vaultlab.kb.obsidian import init_vault

kb_root = Path("~/research-kb").expanduser()
kb_root.mkdir(parents=True, exist_ok=True)
init_vault(kb_root)
```

`init_vault` writes a `.obsidian/` config so Obsidian opens the folder cleanly with sensible defaults (wikilinks enabled, 16pt font, the right core plugins on). It's idempotent — safe to re-run.

### The vault structure VaultLab expects

You can let commands fill these in lazily, or pre-create them with `mkdir`:

```bash
mkdir -p ~/research-kb/{Sources/Articles,Sources/Papers,Sources/Notes}
mkdir -p ~/research-kb/{Wiki/Concepts,Wiki/Summaries,Wiki/Projects}
mkdir -p ~/research-kb/Output
```

Convention every command follows:

| Folder | What goes there | Who writes it |
|---|---|---|
| `Sources/Articles/` | Web articles, paper stubs (one markdown file per source) | `/lit-search`, `/lit-arc`, manual ingest |
| `Sources/Papers/` | Downloaded full-text PDFs | `/lit-arc` acquisition step, manual drop |
| `Sources/Notes/` | Your notes + auto-generated search logs | You + commands |
| `Wiki/Concepts/` | LLM-compiled concept articles with `[[wikilinks]]` | LLM (commands) |
| `Wiki/Summaries/` | Per-paper summaries (one per DOI, editable) | LLM, you can edit freely |
| `Wiki/Projects/<slug>/` | Project state — `START_HERE.md`, intake, decisions log | `/onboard-project`, `/start-project` |
| `Output/` | Generated reports, slides, figures | `/build-deck`, `/lit-report` |
| `_Index.md`, `_Catalog.md` | Auto-maintained navigation files | Commands |

Everything is plain markdown. You can `cat` it, edit it in any editor, share it via a sync service, or commit it to git. Nothing locks you in.

---

## Step 3 — Configure literature API keys (5 minutes)

VaultLab's literature module searches across PubMed, Semantic Scholar, CrossRef, bioRxiv, and Springer. CrossRef and bioRxiv need no key. The rest are free with a 5-minute signup and unlock 5–10× the request rate.

| Service | Why you want it | Sign up |
|---|---|---|
| **NCBI E-utilities** (PubMed) | 10 req/sec instead of 3, higher daily caps | https://www.ncbi.nlm.nih.gov/account/ |
| **Semantic Scholar** | Citation graphs, paper similarity | https://www.semanticscholar.org/product/api |
| **Springer Nature** (optional) | Springer + Nature OA full-text | https://dev.springernature.com/ |
| **Elsevier / ScienceDirect** (optional, institutional only) | ScienceDirect full-text retrieval | Through your library — you cannot apply as an individual |

Keys live in `~/.config/research_apis/config.json` (create if missing):

```json
{
  "ncbi_api_key": "your-key-here",
  "ncbi_email": "you@example.com",
  "semantic_scholar_api_key": "your-key-here",
  "springer_open_access_api_key": "your-key-here"
}
```

> **You do not need an Anthropic API key** when running VaultLab inside Claude Code — Claude Code provides the LLM via your subscription. The keys above only matter for direct literature-API queries. If you skip this step entirely, you'll still be able to use Claude Code's web browsing for paper search; you'll just hit rate limits sooner.

For most users, **NCBI alone is enough.** Add the others as you actually run into rate limits. See [`setup-api-keys.md`](setup-api-keys.md) for the full walkthrough.

---

## Step 4 (optional) — Connect your institutional VPN

If your institution has subscriptions to Elsevier / Springer / Wiley journals, full-text PDF retrieval works much better when you're on the institutional network. Two options:

1. **VPN.** Connect your institution's VPN before running `/lit-arc`. The acquisition waterfall transparently picks up institutional access — you don't tell VaultLab anything; the publisher endpoints just start returning PDFs they previously declined.
2. **Walk-up access.** When you can't VPN, VaultLab falls back to open-access mirrors (PMC, bioRxiv, the publisher's OA layer). For paywalled papers it logs a `manual-fetch` entry in the search log so you can drop the PDF into `Sources/Papers/` later.

If you don't have institutional access, skip this step — open-access coverage in biomedicine is good enough that the open path is genuinely useful.

---

## Step 5 — Onboard your first project (5 minutes)

Open Claude Code in any folder you'd like to use as a project root:

```bash
cd ~/my-project    # any folder; can also be inside your KB
claude
```

Pick the path that matches you:

### Path A — Full project (you have a folder + data)

For an existing research project (a folder with code, papers, notes, wet-lab data). Best onboarding fidelity:

```bash
# 1. Copy the intake template into your project folder
cp templates/project_intake.md ./project_intake.md

# 2. Open it in your editor and fill it in (~5 minutes — required:
#    topic, goal, audience; everything else optional)

# 3. Onboard
> /onboard-project .
```

VaultLab reads your intake, scans the folder (counts files by type, finds your data dirs and PDFs), writes `<kb-root>/Wiki/Projects/<slug>/START_HERE.md`, and asks 3-5 specific follow-up questions for any gaps. After that, every command (`/lit-arc`, `/build-deck`, `/cite audit`) knows your project context.

### Path B — Quick scoping (just a topic)

You don't have a folder yet — you just want to scope a topic and see what VaultLab does. ~30 seconds:

```
> /start-project "spatial transcriptomics in PDAC"
> /lit-arc "spatial transcriptomics in PDAC"
```

That writes a minimal `Wiki/Projects/<slug>/` scaffold and runs the literature lineage arc immediately. No intake form, no folder scan. Upgrade to Path A later with `/onboard-project` if the topic gets serious.

### Path C — Non-research use cases

VaultLab is a knowledge-management tool, not a lab-only tool. The intake template's required fields (`topic`, `goal`, `audience`) are generic — biomedical fields just stay blank if they don't apply:

```
> /start-project "evidence-based insomnia interventions"
> /start-project "personal finance and tax-loss harvesting"
> /start-project "marathon training plans for masters runners"
```

---

## Step 6 — Run `/lit-arc` (5 minutes)

`/lit-arc` is VaultLab's flagship command — it builds a citation-graph-backed literature lineage arc for any topic. In Claude Code:

```
> /lit-arc "T cell exhaustion"
```

Roughly what happens:

1. **Multi-source search.** PubMed + Semantic Scholar + CrossRef + bioRxiv (+ Springer if you have a key). Smart query expansion runs first so synonyms get caught.
2. **Citation-graph corpus.** Forward + backward citations expand the seed set. Each paper gets an `og_score` (foundational? methodological? recent?) and `forward_influence` count.
3. **Picker meeting.** A multi-agent step ranks candidates by relevance + diversity (catches off-topic-but-cited papers).
4. **PDF acquisition waterfall.** Open-access mirrors first, publisher APIs second, manual-fetch fallback for paywalled papers.
5. **Per-paper summaries.** Claude Code reads each PDF and writes `Wiki/Summaries/<doi-slug>.md` with `[pN]` page markers tying claims to evidence.
6. **Lineage arc.** A 3-section narrative (history → development → state-of-the-art) lands in `Wiki/Concepts/<topic-slug>-lineage-<date>.md`.

Output structure you'll see in your KB:

```
~/research-kb/
├── Sources/
│   ├── Articles/<doi-slug>.md           ← one stub per seed paper
│   ├── Papers/<doi-slug>.pdf            ← full-text PDFs (where retrievable)
│   └── Notes/
│       ├── lit-search-T-cell-exhaustion-<date>.md   ← decisions log + search log
│       └── ...
├── Wiki/
│   ├── Summaries/<doi-slug>.md          ← per-paper LLM summary
│   ├── Concepts/T-cell-exhaustion-lineage-<date>.md ← the arc narrative
│   └── Projects/T-cell-exhaustion/
│       ├── START_HERE.md                ← project state
│       ├── decisions-log.md             ← chronological decisions
│       └── papers-manifest.md           ← which papers were chosen, with rationale
└── ...
```

Every artifact has a `.provenance.json` + `.method.md` receipt next to it so you can audit how it was produced.

To open the result:

```bash
vaultlab kb open Wiki/Concepts/T-cell-exhaustion-lineage-<date>
```

(Or open the file directly in Obsidian.)

---

## Continual KB growth — the additivity principle

Every subsequent run **builds on what's there**. This is the most important property of VaultLab and what makes it different from a one-shot tool:

- **Re-running `/lit-arc` on the same topic** refreshes the citation graph (new papers get added, old summaries are preserved). Your manual edits to `Wiki/Summaries/<doi>.md` survive across re-runs.
- **Summaries are global.** A paper summarized for Project A is automatically reused when Project B references it. No duplication.
- **Figures are global.** Figures generated under `Output/<project>/` are referenced by DOI; cross-project insights surface automatically.
- **Cross-project memory compounds.** When you run `/lit-arc` on a new topic, papers already in your KB from prior topics get scored and re-considered. The graph grows.
- **Wikilinks compound.** Obsidian's graph view becomes useful around 20 sources in. Every cross-reference makes future retrieval better.

A monthly cadence on `/lit-arc` per active topic keeps your literature picture current — new papers cite old ones; old papers acquire new follow-ups.

---

## Where to go from here

- [`docs/use-cases.md`](use-cases.md) — concrete end-to-end workflows
- [`docs/architecture.md`](architecture.md) — how VaultLab is built
- [`docs/setup-api-keys.md`](setup-api-keys.md) — full literature key setup
- [`docs/setup-obsidian.md`](setup-obsidian.md) — Obsidian + recommended plugins
- [`docs/KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) — honest list of what's still placeholder
- [`.claude/commands/COMMANDS.md`](../.claude/commands/COMMANDS.md) — full slash-command inventory
- File issues at https://github.com/bobbyni819/vaultlab/issues

---

## 10 best practices (skim now, return when needed)

1. **Let the system pick KB paths.** When a slash command writes a file, it routes through `vaultlab.kb.paths`. Saving manually to a subfolder you invented breaks indexing silently.
2. **Use `vaultlab kb open <path>` to navigate.** Every command surfaces its outputs as an open command at end-of-turn. Click those — faster than the file tree, and the new-tab behavior keeps your context.
3. **Re-run `/lit-arc` on the same topic monthly.** Refreshes the citation lineage. New papers cite old ones; old papers acquire new follow-ups.
4. **Edit `Wiki/Summaries/<doi>.md` freely.** Your manual notes survive across re-runs.
5. **Cross-reference with `[[wikilinks]]`.** Compounding gains start around 20 sources.
6. **Keep PDFs in `Sources/Papers/`.** VaultLab manages them; don't move them around manually. The DOI-slug filenames are how citation verification matches papers to claims.
7. **Project-scope work via `Output/<project>/deck_plan.md`.** When you start a manuscript or talk, drop a `deck_plan.md` at the root of `Output/<project>/` — slide commands look there first.
8. **Use `/cite audit` before sharing any draft.** It catches the citation hallucinations LLMs occasionally produce. This is the difference between VaultLab being useful and embarrassing.
9. **Free API keys take 15 minutes total and unlock 10x more papers.** NCBI alone is the highest-leverage 5 minutes.
10. **The KB is plain markdown — share the folder to onboard a labmate.** No infrastructure, no server, no permissions system. They open the folder in Obsidian; their Claude Code reads the same files. Cross-project insights surface automatically because everyone's writing into the same memory.

---

## Stuck?

- Re-read Step 0 — VaultLab does four specific things; make sure you're trying to use it for one of them.
- Open an issue: https://github.com/bobbyni819/vaultlab/issues
- Check [`docs/KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) — VaultLab is alpha; some things you might expect to work are placeholders right now.
