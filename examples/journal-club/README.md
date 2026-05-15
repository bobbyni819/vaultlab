# Journal Club

**What this does:** End-to-end pipeline that takes a single DOI for a journal-club
target and produces a slide deck (`.pptx`) plus a Tier-A-style markdown summary
(`paper.md`). Composes `vaultlab.research` (best-effort metadata enrichment) with
the dict-plan slide builder in `vaultlab.slides`.

**Primitives composed:**

- `vaultlab.research.ResearchClient.get_paper(doi)` — best-effort enrichment of bundled metadata against PubMed / CrossRef / Semantic Scholar. Falls through to the bundled `inputs/paper.json` if no API config is available.
- `vaultlab.slides.build_from_plan(plan, out)` — renders a hand-authored slide-plan dict to `.pptx` using the Hickey-lab template + layouts.

**Run:**

```bash
python run.py
```

Optional flags:

- `--no-fetch` — skip the real-API enrichment step entirely (recommended in CI / offline).
- `--out PATH` — change output directory (default `./out/`).
- `--open` — `os.startfile` the deck after building (Windows only).

**Outputs land in:** `./out/` (created on first run; not committed).

`./out/` contains:

- `journal-club-<slug>.pptx` — 8-slide deck (title, why, who, divider, contribution, strengths/limits, discussion, refs)
- `paper.md` — Tier-A-style markdown summary with frontmatter

**Inputs:** `inputs/paper.json` — DOI + bundled fallback metadata. Pentimalli &
Rajewsky 2025 (*Cell Systems*) is a PMC-OA paper (CC BY); only metadata is
committed, not the PDF.

**Adapt this:**

- Swap `inputs/paper.json` for any other DOI + metadata. Required keys: `doi`, `title`. Optional: `authors`, `year`, `journal`, `abstract`.
- Edit `_build_plan(paper)` in `run.py` to change the slide structure. The dict shape is documented in `vaultlab.slides.build_from_plan`.
- For a richer multi-figure deck, see the historical reference output in `expected_outputs/journal-club-pentimalli-2026-05-05.pptx` (16-slide deck with extracted figures from the full paper PDF).

**Reference output:** see `expected_outputs/` — includes a 16-slide reference
`.pptx` from a previous full-fidelity build, plus `SUMMARY.md` describing what
`run.py` currently produces with the bundled inputs.
