# Use cases — what vaultlab actually does for a researcher's week

These are the workflows vaultlab solves end-to-end. Drawn from real PhD work in the Hickey lab (Duke BME) — CODEX/MALDI lung tissue analysis, agent-based influenza modeling, multi-agent code generation. Use these as templates for your own workflows.

> **Status:** v0.0.x scaffold. The workflows below describe what vaultlab v0.1 will do end-to-end. Each is wired to slash commands that land in upcoming commits.

## 1. CODEX run → labeled spatial figure (~30 minutes)

**Before vaultlab:** Manual TIFF inspection → run Mesmer in a notebook → cluster in scanpy → eyeball top markers per cluster → write annotation labels by hand → screenshot panels into PowerPoint → maintain a Word doc of "what each cluster is."

**With vaultlab:**

```
You: I just got the tonsil CODEX run back. It's at Z:/lab_data/CODEX/run_2024_03/.
     Walk it through the standard pipeline.

vaultlab:
  ✓ Discovered modality: CODEX (35-marker panel, 4 donors)
  ✓ Segmented with Mesmer (47,832 cells)
  ✓ QC: 3 tiles flagged for CD8 saturation (will exclude)
  ✓ Normalized: per-channel z-score
  ✓ Clustered: Leiden resolution=0.7, found 12 clusters
  ✓ LLM cluster annotation:
      Cluster 0 (n=12,847): Mature epithelial (CD66+ Ki67-)
      Cluster 1 (n=8,392):  CD8+ T cells (CD3+ CD8+)
      Cluster 7 (n=312):    likely exhausted CD8+ (PD1+ LAG3+ TIM3+)
                            — markers consistent with Wherry & Kurachi 2015
      [...]
  ✓ Rendered Figure 1 (spatial overlay) at publication-tight density
  ✓ Audit verdict: PASS — 47/47 cells covered, no orphan markers
  ✓ Wrote KB note: <kb>/Wiki/Concepts/run_2024_03_clustering.md
  ✓ Drafted caption (hedged voice; you edit + finalize)

Total: 23 minutes wall-clock; $0.42 in Anthropic billing.

You: Okay, the cluster 7 exhausted T-cell call is interesting.
     What papers should I cite for that phenotype?

vaultlab:
  Searching PubMed + bioRxiv + paperclip MCP...
  Found 8 candidates (5 SUPPORTED, 2 WEAKLY_SUPPORTED, 1 PARTIALLY_RELEVANT)
  Top 3:
    [1] Wherry & Kurachi 2015 — canonical exhaustion signature  ✓ SUPPORTED
    [2] Im et al. 2016 — TCF1+ progenitor exhausted vs terminal  ✓ SUPPORTED
    [3] Beltra et al. 2020 — exhausted T cell developmental hierarchy  ✓ SUPPORTED
  All 3 PDFs ingested into KB; can be cited via [N] markers.
```

**Time saved:** ~6 hours (manual annotation + lit review). **Quality gain:** every annotation is hedged + cited; CoverageManifest sidecar means a reviewer can verify exactly which cells are included.

---

## 2. Methods section first draft with verified citations (~15 minutes)

**Before vaultlab:** Open Google Doc → start typing → switch to PubMed for every citation → copy DOI → paste → format → repeat 50 times → realize you cited the wrong paper for that claim → re-check.

**With vaultlab:**

```
You: Draft the Methods section for the LPI/GPR55 manuscript.
     Project is codex_lung. Use the standard format.

vaultlab:
  ✓ Read project KB (47 verified findings, 89 ingested papers)
  ✓ Read existing manuscript draft (sections/abstract.md, introduction.md)
  ✓ Drafting Methods (constrained generation; bound to manifest)
  ✓ Verify all citations:
      - 47/50 SUPPORTED (semantic match)
      - 2/50 WEAKLY_SUPPORTED (passages discuss related but distinct topic)
      - 1/50 NOT_FOUND — flagged for replacement
  ✓ Hedged voice enforced (replaced 3 unsupported claims with hedges)
  ✓ Methodology grounded in real software versions (Mesmer 0.10, scanpy 1.10.2,
    Cellpose cyto3 — all from your manifest)
  ✓ Saved to <kb>/Output/manuscript/main/sections/methods.md
  ✓ Evidence sidecar: <kb>/Output/manuscript/main/evidence.json
  ✓ method.md provenance receipt at sections/methods.method.md

⚠ 3 issues to resolve before finalizing:
  - Citation [12] (Smith 2024): verdict WEAKLY_SUPPORTED — passage discusses
    related epithelial signaling but not LPI specifically. Consider replacing
    with Doe 2023 (also in your KB).
  - Citation [27]: NOT_FOUND. Replace or add the paper to your KB.
  - Sentence "We demonstrate that LPI activates GPR55" is too strong; consider
    "Our data are consistent with LPI activation of GPR55."
```

**Time saved:** ~3 hours per Methods section. **Quality gain:** zero hallucinated citations get past the auditor; PI doesn't have to spot-check every [N].

**Reviewers won't know AI was used:** the hedged voice + verified citations + your final edits make the Methods section indistinguishable from one you wrote start to finish.

---

## 3. From paper PDF to journal-club deck in 90 seconds

**Before vaultlab:** Skim paper → open PowerPoint → screenshot Figure 1 → paste → write title → screenshot Figure 2 → paste → write speaker notes for the figure you mostly understand and bullet points for the one you don't → realize the slide text is too small → resize → repeat.

**With vaultlab:**

```
You: /paper-to-slides 10.1038/s41586-024-XXXXX --intent journal-club

vaultlab:
  ✓ Fetched Smith et al. 2024 from Nature
  ✓ Extracted 6 figures (with captions + page numbers)
  ✓ Understood each panel via Claude Vision:
      Fig 1A: schematic of experimental design
      Fig 1B: heatmap of differential expression
      Fig 2A: spatial distribution of CD8+ T cells
      [...]
  ✓ Composed 8-slide deck:
      Slide 1: title + authors + journal
      Slide 2: background (3 bullets, drawn from intro)
      Slide 3: experimental approach (Fig 1A full-slide layout)
      Slide 4: key result (Fig 1B with auto-callout on top-DE genes)
      Slide 5: validation (Fig 2A with annotation arrows on regions of interest)
      [...]
      Slide 8: discussion + open questions (5 hedged bullets)
  ✓ Speaker notes drafted (3 sentences per slide)
  ✓ Exported: <kb>/Output/decks/smith_2024_journal_club.pptx

90 seconds wall-clock; $0.18 in Anthropic billing.
```

**Time saved:** ~half a day. **Quality gain:** speaker notes are coherent (LLM-drafted, reviewed by you). The deck is the FLAGSHIP demo for vaultlab — no other OS tool does this.

---

## 4. Daily morning briefing — what's actually pressing today

**Before vaultlab:** Open Outlook → scan unread → check calendar → check Google Doc work log → check Teams → check the 3 manuscript drafts → ask "what should I be doing this morning?"

**With vaultlab:**

```
You: /brief

vaultlab (reads Outlook + Google Doc + KB + calendar):
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Tuesday, April 28, 2026

  CALENDAR (4 events):
    10:00 AM — Lab meeting (Mr. Hickey + 6 others)
    1:30 PM — Manuscript review with John (LPI paper revision)
    3:00 PM — JHU collaborator call (CODEX panel)
    5:00 PM — Optional: workshop on spatial omics (skip if busy)

  EMAIL (3 flagged):
    From journal editor: revision deadline May 15 (LPI paper) — confirmed
    From John: "let's discuss the cluster 7 finding tomorrow"
    From Faye: MultiAgent v0.5.1 ready for review

  WORK LOG (yesterday):
    - Finished tonsil run segmentation (47k cells)
    - Drafted Methods §3.2 (12 citations verified)
    - Open: figure 4 panel A still needs caption

  NEXT BEST ACTIONS:
    1. Pre-meeting prep for 1:30 PM with John (cluster 7 finding)
    2. Caption + audit for figure 4 panel A
    3. Review Faye's MultiAgent v0.5.1 changes

  Run /prep "manuscript review john" to prep for the 1:30 PM.
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Time saved:** the 20 minutes you usually spend "figuring out what to do this morning."

This is the feature that **makes vaultlab a research companion instead of a research tool.** The companion knows your day.

---

## 5. End-of-day summary to PI without breaking your stride

**Before vaultlab:** Try to remember what you did → open Teams → type a summary → realize you forgot the cluster annotation work → edit → send.

**With vaultlab:**

```
You: /eod

vaultlab (synthesizes today's KB + Google Doc + work log):
  Drafted EOD summary for John:

  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Hi John —

  Today's progress on the LPI manuscript:
  - Finished tonsil CODEX cluster annotation (12 clusters; cluster 7
    presents an interesting exhausted CD8+ phenotype consistent with
    Wherry 2015)
  - Drafted Methods §3.2 (47/50 citations SUPPORTED; flagged 3 for review)
  - Generated Figure 4 panel B; audit PASSED
  - Caught up with Faye on MultiAgent v0.5.1 (will review tomorrow)

  Open for tomorrow:
  - Figure 4 panel A caption
  - Resolve 3 weakly-supported citations in Methods
  - 10:00 AM lab meeting

  Bobby
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Send via Teams to John? [Y/n]: Y
  ✓ Sent.
```

**Time saved:** 15 minutes of remembering + writing. **Quality gain:** PI sees consistent reporting; your work-log stays current automatically.

---

## What these use cases share

1. **Companion mode** — vaultlab does the rote 60% (annotation, citation verification, deck assembly, daily summaries). You do the insightful 40% (deciding what to investigate, judging the science, finalizing the paper).
2. **Full context** — works because vaultlab has access to your KB + Google Doc + Outlook + manuscripts. A generic LLM chat can't do these because it doesn't know what you did yesterday.
3. **Hedged voice** — every LLM-generated interpretation hedges ("consistent with X"), never asserts ("X is Y"). Reviewer-defensible.
4. **Verified by default** — every citation goes through semantic match; every figure gets an audit verdict. No silent hallucinations.
5. **Journal-compatible** — these workflows produce DRAFTS you finalize. The published paper has YOUR name as author; vaultlab is a tool, not a co-author. Most journal AI policies cover the latter.

## What vaultlab will NOT do

- **Generate research questions in a vacuum** — you bring the science; vaultlab amplifies it
- **Submit papers without your review** — every output is a draft for you to edit
- **Run experiments autonomously** — vaultlab analyzes wet-lab data; the wet-lab work is yours
- **Write the discussion section** — that's your novel insight; LLM-drafted discussions read like LLM-drafted discussions
- **Replace your judgment** — vaultlab presents options; you decide

## Try it yourself

```bash
git clone https://github.com/bobbyni819/vaultlab && cd vaultlab
pip install -e ".[all]"
vaultlab setup
vaultlab demo pbmc3k       # 2-min Hello World
```

For your own data, point at `Z:/lab_data/<your_run>/` with `vaultlab data discover` and follow the suggestions.
