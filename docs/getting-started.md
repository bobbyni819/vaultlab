# Getting started with VaultLab

(Audience: a researcher who just cloned the repo. ~10–15 minutes to first useful output.)

> VaultLab is **alpha software** — v0.0.1 is mostly architectural scaffold, with v0.1.0 landing late May 2026. Many slash commands are still placeholders. Where something is not yet wired up, this guide says so. If something breaks, [file an issue](https://github.com/bobbyni819/vaultlab/issues) and Bobby will look.

---

## Step 0 — What VaultLab actually does for you (60 seconds)

VaultLab is one tool that does four things, with all four sharing the same plain-markdown knowledge base:

1. **Knowledge base.** Your papers, notes, findings, and project state live as markdown files in a folder you can put on Google Drive (or any sync service). Obsidian renders it; you can share it with a labmate or a collaborator the same way you'd share any folder.
2. **Citation-verified writing.** When you draft text with `[N]` markers, VaultLab checks every citation against the actual source paper and flags hallucinations before you ship.
3. **Slide decks.** `/build-deck <topic>` (v0.1.0) composes a deck from whatever's in your KB — a paper PDF, your data, a manuscript draft, or just a topic.
4. **Wraps the literature + analysis tools you already trust.** PubMed / Semantic Scholar / CrossRef / bioRxiv for search; scanpy / squidpy / scikit-image for analysis. VaultLab picks real functions from real packages, not made-up ones.

This guide takes you from clone to your first useful KB entry. Nothing here assumes you write code for a living — if you write a methods section for a paper, you can run VaultLab.

---

## Step 1 — Install (3 minutes)

```bash
git clone https://github.com/bobbyni819/vaultlab && cd vaultlab
pip install -e ".[all]"
```

`[all]` pulls every optional dependency. If you only want the literature + citations layer for now, `pip install -e ".[research,citations,kb]"` is enough.

Verify it imported cleanly:

```bash
python -c "import vaultlab; print(vaultlab.__version__)"
# 0.0.1
```

You also need **[Claude Code](https://claude.com/claude-code)** installed — VaultLab is Claude-Code-native, so the LLM access comes through your Claude Code subscription. **No separate Anthropic API key required.**

(Recommended: install **[Obsidian](https://obsidian.md)** as well. The KB is plain markdown, so any editor works, but Obsidian's wikilink graph is where the cross-paper navigation really pays off.)

---

## Step 2 — Tell VaultLab where your KB is (2 minutes)

The KB is just a folder. Pick somewhere your machine can reach — Google Drive (`G:/My Drive/Knowledge/<project>` is what Bobby uses), Dropbox, or a plain local directory. The advantage of putting it on a sync service is sharing: dragging the folder URL to a labmate gives them the whole vault.

In Python (the v0.0.1 path — a `vaultlab init` CLI is in flight for v0.1.0):

```python
from pathlib import Path
from vaultlab.kb.obsidian import init_vault

kb_root = Path("G:/My Drive/Knowledge/my_first_kb")
kb_root.mkdir(parents=True, exist_ok=True)
init_vault(kb_root)
```

That writes a `.obsidian/` config so Obsidian opens the folder cleanly with sensible defaults (wikilinks enabled, 16pt font, the right core plugins on). It's idempotent — safe to re-run.

You'll fill out the rest of the structure as you use VaultLab. The convention every command follows:

- `Sources/Articles/` — web articles, paper stubs (one markdown file per source)
- `Sources/Papers/` — downloaded full-text PDFs
- `Sources/Notes/` — your notes, plus auto-generated search logs
- `Wiki/Concepts/` — LLM-compiled concept articles with `[[wikilinks]]`
- `Wiki/Summaries/` — per-paper summaries (one per DOI, editable)
- `Output/` — generated reports, slides, figures
- `_Index.md`, `_Catalog.md` — auto-maintained navigation files

Everything is plain markdown. You can `cat` it, edit it in any editor, share it via Drive, or commit it to git. Nothing locks you in.

---

## Step 3 — (Optional) Get free literature API keys (5 minutes)

VaultLab's literature module searches across PubMed, Semantic Scholar, CrossRef, bioRxiv, and Springer. CrossRef and bioRxiv are public — no key needed. NCBI and Semantic Scholar are free with a 5-minute signup and unlock 10x the request rate.

| Service | Why you want it | Sign up |
|---|---|---|
| **NCBI E-utilities** (PubMed) | 10 req/sec instead of 3, higher daily caps | https://www.ncbi.nlm.nih.gov/account/ |
| **Semantic Scholar** | Cleaner citation graphs, paper similarity | https://www.semanticscholar.org/product/api |
| **Springer Nature** | Springer + Nature OA full-text | https://dev.springernature.com/ |

These go in `~/.config/bobby_research/config.json` (vaultlab also reads `G:/My Drive/Knowledge/tools/.config/research_apis.json` if you keep keys on Drive — Bobby's setup):

```json
{
  "ncbi_api_key": "your-key-here",
  "ncbi_email": "you@example.com",
  "semantic_scholar_api_key": "your-key-here",
  "springer_open_access_api_key": "your-key-here"
}
```

> **No Anthropic API key needed.** Claude Code provides LLM access via your subscription. The keys above only matter for direct literature-API queries. If you skip this step entirely, you can still use Claude Code's web browsing for paper search — you'll just get fewer hits per minute.
>
> *(In flight: a future `vaultlab` CLI will read keys from `~/.config/vaultlab/secrets.toml`. The current code path resolves through `vaultlab.research.config`, which uses the `bobby_research` location above. Either path works once it ships; for v0.0.x, use the JSON file.)*

See [`docs/setup-api-keys.md`](setup-api-keys.md) for the full walkthrough, including which keys most users genuinely need (short answer: NCBI is the only essential one).

---

## Step 4 — Onboard your first project (5 minutes)

Open Claude Code in the vaultlab folder:

```bash
cd vaultlab
claude
```

Claude Code reads `CLAUDE.md` automatically — it knows what VaultLab is and how to navigate the codebase. Now pick the path that matches you:

### Path A — Full project (you have a folder + data)

For an existing research project (a folder with code, papers, wet-lab data, notes). Best onboarding fidelity.

```bash
# 1. Copy the intake template into your project folder
cp templates/project_intake.md /path/to/your/project/

# 2. Open it in your editor and fill it in (~5 minutes — required:
#    topic, goal, audience; everything else optional)

# 3. Onboard
> /onboard-project /path/to/your/project
```

VaultLab reads your intake, scans the folder (counts files by type, finds your data dirs and PDFs), writes `Wiki/Projects/<slug>/START_HERE.md`, and asks 3-5 specific follow-up questions for any gaps. After that every command (`/lit-arc`, `/build-deck`, `/cite audit`) knows your project context.

### Path B — Quick scoping (just curious about a topic)

You don't have a project folder yet — you just want to explore a topic and see what VaultLab can do. ~30 seconds.

```
> /start-project "spatial transcriptomics in PDAC"
> /lit-arc "spatial transcriptomics in PDAC"
```

That writes a minimal `Wiki/Projects/<slug>/` scaffold and runs the literature lineage arc immediately. No intake form, no folder scan. Upgrade to full Path A onboarding later with `/onboard-project` if the topic gets serious.

### Path C — Non-research use cases

VaultLab is a knowledge-management tool, not a lab-only tool. The intake template's required fields (`topic`, `goal`, `audience`) are generic — biomedical fields just stay blank if they don't apply.

```
> /start-project "evidence-based insomnia interventions"
> /start-project "personal finance and tax-loss harvesting"
> /start-project "marathon training plans for masters runners"
```

Open-access papers exist for almost any topic. The KB doesn't care whether the topic is biomedical. If you ticked "Yourself (personal notes)" as the audience and the goal as "Understand a literature field," VaultLab works the same way.

---

If you skipped to here without a topic in mind, the simplest first command is just `/lit-search` against any topic that interests you. It does multi-source paper search and writes results to your KB without needing a project at all. (`/lit-arc`, the deeper end-to-end orchestrator that builds a citation graph and lineage narrative, lands fully in v0.1.0.)

Pick a generic topic — *"T cell exhaustion"*, *"spatial transcriptomics methods"*, *"insomnia interventions"*, anything you'd actually want to read about. In Claude Code:

```
> /lit-search "T cell exhaustion" --max-results 20 --kb my_first_kb
```

Roughly what happens:

1. **Phase 1 — multi-source search.** PubMed + Semantic Scholar + CrossRef + bioRxiv (+ Springer if you have a key). Smart query expansion runs first so synonyms get caught.
2. **Phase 2 — dedup + re-rank.** Same paper from multiple sources collapses to one entry, ranked by combined relevance + citation impact.
3. **Phase 3 — KB stubs.** Each result lands as `Sources/Articles/<doi-slug>.md` with title, authors, abstract, and a wikilink stub.
4. **Phase 4 — search log.** A `Sources/Notes/lit-search-T-cell-exhaustion-<date>.md` records the exact query and result IDs so you can trace later.

When `/lit-arc` lands in v0.1.0, two more phases run automatically: PDF acquisition (where legally available) and a per-paper Wiki/Summaries page with quoted-evidence summaries.

Browse the output:

```bash
# vaultlab-native (works now if Obsidian is installed)
python -c "from vaultlab.kb.obsidian import open_in_obsidian; open_in_obsidian('Sources/Notes/lit-search-T-cell-exhaustion-<date>')"
```

Or, if you have `bobby-tools` installed (Bobby's broader toolkit), `bobby-kb open <path>` is the shortcut form Claude Code uses throughout.

---

## Step 5 — Five things to try next (5 minutes each)

1. **Build a deck (v0.1.0).** `/build-deck "T cell exhaustion" --speaker "Your Name"` composes a journal-club-grade deck from your KB — figures, captions, speaker notes. Exports `.pptx`. *(Currently spec'd; lands in v0.1.0.)*

2. **Add a paper to your KB.** Drop a PDF into `Sources/Papers/`, or use the dispatcher:
   ```python
   from vaultlab.kb.ingest import ingest
   ingest("path/to/paper.pdf")
   # Also accepts DOIs, BibTeX files, folders of markdown
   ```

3. **Search your KB semantically.** Once you've ingested a few papers:
   ```python
   from vaultlab.kb.semantic_search import search
   for hit in search(kb_path="G:/My Drive/Knowledge/my_first_kb",
                     query="exhausted T cell signatures")[:5]:
       print(f"{hit.score:.3f}  {hit.path.name}")
   ```
   TF-IDF baseline works out of the box; flip on `backend="embeddings"` for better natural-language queries.

4. **Use VaultLab for a non-research project.** VaultLab is a knowledge-management tool, not a lab-only tool. Try `/lit-search "personal finance algorithmic trading"` or `/lit-search "evidence-based insomnia treatment"` — anything you want to read deeply about, build a reading list around, and have an LLM that knows your accumulated context. The KB doesn't care whether the topic is biomedical.

5. **Open your KB in Obsidian.** Open Obsidian → "Open vault" → point it at your KB folder. Click any `Wiki/Summaries/<doi>.md` file, then follow the `[[wikilinks]]` to traverse the citation network. The graph view (left sidebar) shows how your sources connect — increasingly useful as the KB grows.

---

## Step 6 — Where to go from here

- [`docs/use-cases.md`](use-cases.md) — concrete end-to-end workflows: CODEX run → labeled spatial figure, scRNA-seq → annotated clusters → manuscript section
- [`docs/architecture.md`](architecture.md) — how VaultLab is built (the four core commitments, the runner, the recipe library)
- [`docs/setup-api-keys.md`](setup-api-keys.md) — full literature key setup
- [`docs/setup-obsidian.md`](setup-obsidian.md) — Obsidian + the recommended plugins
- [`docs/KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) — honest list of what's a placeholder right now
- [`INSPIRATIONS.md`](../INSPIRATIONS.md) — what we lifted from where (virtual-lab, AI-Scientist, paperclip, scverse, gstack)
- [`.claude/commands/COMMANDS.md`](../.claude/commands/COMMANDS.md) — full slash-command inventory with status flags
- File issues at https://github.com/bobbyni819/vaultlab/issues

---

## 10 best practices (skim now, return when needed)

These emerged from real lab use. They're not arbitrary preferences — each one prevents a specific kind of frustration.

1. **Let the system pick KB paths.** When a slash command writes a file, it routes through `vaultlab.kb.paths` — that's how the index, search, and provenance receipts find it later. Saving manually to a subfolder you invented breaks those links silently.

2. **Use `bobby-kb open <path>` (or `vaultlab kb open`) to navigate.** Every command surfaces its outputs as an open command at end-of-turn. Click those — it's faster than hunting in the file tree, and the new-tab behavior keeps your context.

3. **Re-run `/lit-arc` on the same topic monthly.** It refreshes the citation lineage. New papers cite old ones; old papers acquire new follow-ups. Monthly cadence keeps the picture current.

4. **Edit `Wiki/Summaries/<doi>.md` freely.** Your manual notes survive across re-runs — the per-paper summary file is yours to annotate. The auto-generated content respects your edits.

5. **Cross-reference with `[[wikilinks]]`.** Obsidian's graph view becomes useful around 20 sources in. Wikilinks compound: every cross-reference makes future retrieval better.

6. **Keep PDFs in `Sources/Papers/`.** VaultLab manages them; don't move them around manually. The DOI-slug filenames are how citation verification matches papers to claims.

7. **Project-scope work via `Output/<project>/deck_plan.md`.** When you start a new manuscript or talk, drop a `deck_plan.md` at the root of `Output/<project>/` — VaultLab's slide commands look there first.

8. **Use `/cite audit` before sharing any draft.** Run it on every manuscript/email/grant before it leaves your machine. It catches the citation hallucinations that LLMs occasionally produce, with a 3-tier verifier (DOI lookup → abstract match → semantic claim match). This is the difference between VaultLab being useful and embarrassing.

9. **Free API keys take 15 minutes total and unlock 10x more papers.** NCBI alone is the highest-leverage 5 minutes you'll spend on setup. Without a key, you'll quietly hit rate limits and miss results.

10. **The KB is plain markdown — share the Drive folder to onboard a labmate.** No infrastructure, no server, no permissions system to configure. They open the folder in Obsidian; their Claude Code reads the same files. Cross-project insights surface automatically because everyone's writing into the same memory.

---

## Stuck?

- Re-read Step 0 — VaultLab does four specific things; make sure you're trying to use it for one of them.
- Open an issue: https://github.com/bobbyni819/vaultlab/issues
- Check [`docs/KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) — VaultLab is alpha; some things you might expect to work are placeholders right now.

VaultLab is being built openly. If something breaks, that's signal worth filing.
