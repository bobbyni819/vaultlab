# Expected outputs — journal-club

Reference output for the journal-club example.

## What `run.py` produces

Running `python run.py` writes two files to `../out/`:

1. **`journal-club-<slug>.pptx`** — 8-slide deck (~40-60 KB):
   - Slide 1: Title (paper title + first-author + venue + year)
   - Slide 2: Why this paper (3 bullets)
   - Slide 3: Who built it (authors + venue)
   - Slide 4: Section divider — "The contribution"
   - Slide 5: Take-home in one paragraph (full abstract)
   - Slide 6: Strengths vs. limitations (4 bullets, 2 STRENGTH + 2 LIMIT)
   - Slide 7: Discussion seeds (5 numbered questions)
   - Slide 8: References (1 entry — the source paper)

2. **`paper.md`** — Tier-A-style markdown summary with YAML frontmatter
   (`doi`, `title`, `year`, `journal`, `tier: A`, `generated_by`), the abstract
   in a "Abstract" section, and a "Why we read it" closing.

## Pre-existing reference deck

`journal-club-pentimalli-2026-05-05.pptx` (18 MB — over the 200 KB
example-commit threshold but already in repo history from a 2026-05-05
full-fidelity build) is preserved here for reference. It is a 16-slide
deck with all 7 figures extracted from the Pentimalli & Rajewsky 2025
paper PDF, layouts auto-picked from aspect ratios, speaker notes auto-derived
from a Tier-A summary, and bullets animated click-by-click.

The current `run.py` produces a leaner deck (8 slides, no figure extraction)
suitable as a starting-point template that external contributors can extend.

## How to refresh

```bash
python run.py
# ../out/journal-club-<slug>.pptx + ../out/paper.md
```

Use `--no-fetch` for fully offline runs (recommended in CI).
