# Graphics for the vaultlab repo

The README has 3 marked placeholders for graphics. This doc tells you what to make and where to put it.

## Placeholder 1: Hero banner (top of README)

**Marker in README:** `<!-- HERO GRAPHIC GOES HERE -->`

**What it should show:** vaultlab name + tagline + a 4-icon row hinting at the pillars (Literature / Data / Figures / Slides), OR a short animated GIF showing one slash command running end-to-end.

**Specs:**
- Static image: 1200×400 px (2:1 aspect ratio renders well on GitHub mobile + desktop)
- Animated GIF: 800×450 px, ≤6 seconds, ≤2 MB (auto-loops)
- File: `assets/hero.png` or `assets/hero.gif`

**Tools:**
- **Figma** (free, browser-based) — for static designs
- **Excalidraw** (free, hand-drawn aesthetic) — fits a research/lab vibe
- **Canva** (free tier, template-driven) — fastest if you want to start
- **Terminalizer** or **vhs** — for animated terminal demos
- **OBS Studio + ffmpeg** — for screencasts converted to GIF

**Design tip:** Keep it un-busy. A research-tool README's hero is competing with people scrolling past. Tagline + 4 icons + repo name is enough.

## Placeholder 2: Capability diagram

**Marker in README:** `<!-- CAPABILITY DIAGRAM GOES HERE -->`

**What it should show:** the 4 pillars (Literature / Data / Figures / Manuscripts & Slides) connected through the central Knowledge Base. Or a 2×2 grid where each cell has an icon + 2-3 word label.

**Specs:** 800×600 px, PNG with transparent background ideal.

**Tools:** Excalidraw is great for this — looks hand-drawn, reads as approachable.

## Placeholder 3: Comparison / positioning graphic

**Marker in README:** `<!-- COMPARISON / POSITIONING GRAPHIC GOES HERE -->`

**What it should show:** Either:
- A Venn diagram with 5 circles (vaultlab + PaperQA + scanpy + FutureHouse + scverse) with vaultlab in the middle
- A capability matrix as an image (more compact than the markdown table currently in the README)
- A "stack" diagram showing vaultlab as a layer ON TOP of existing tools (positioning as a capability layer, not a competitor)

**Specs:** 1000×600 px.

**Tools:** Figma, Excalidraw, draw.io.

## Bonus places to add graphics later

These don't have placeholders yet but are common in well-presented OSS READMEs:

### Architecture diagram

A cleaner image-based version of the existing Mermaid diagram. Mermaid renders fine but a static SVG can carry more visual weight.

**Where:** Replace the `mermaid` code block in the README's "How it works" section.

### Output demo screenshots

Side-by-side: a snippet of generated `Methods` paragraph with `[N]` citations highlighted; a screenshot of a generated slide deck; a screenshot of a published-quality figure with caption.

**Where:** New "Output examples" section between "Four pillars" and "Specialized modules."

**Specs:** Each image 800×400 px, 3 stacked or in a row.

### Logo / favicon

vaultlab doesn't have a logo yet. When you make one:
- Save SVG to `assets/logo.svg`
- Update `pyproject.toml` to reference it (some package portals show logos)
- Add to README at the very top, left of the project name

### Roadmap chart

A timeline graphic showing v0.0.1 (today) → v0.1.0 (May 27) → v0.2.0 (autumn) → v1.0.0 (next year).

**Where:** New "Roadmap" section near the bottom.

## File organization

```
assets/
  hero.png                # placeholder 1
  capability-grid.png     # placeholder 2
  comparison.png          # placeholder 3
  architecture.svg        # bonus
  output-methods.png      # bonus
  output-deck.png         # bonus
  output-figure.png       # bonus
  logo.svg                # bonus
  logo-small.png          # for badge / package portal
```

## Branding notes

vaultlab visual identity (informal, can evolve):
- **Color palette suggestion:** dark teal + warm grey + accent yellow (matches "lab notebook" vibe — not corporate)
- **Typography:** monospace for code/CLI elements; serif or sans-serif for body
- **Logo concept ideas:**
  - A vault door with markdown brackets `[ ]` inside
  - A lab notebook with a `>` cursor
  - A simple wordmark in a clean monospace (Karpathy's `nanoGPT` does this — just text, works fine)

## Where to share

When you have the hero image:
1. Add to `assets/hero.png`
2. Replace the README placeholder comment with `![vaultlab hero](assets/hero.png)`
3. Tag a release (or just push to main)
4. Use it as the X/Bluesky launch tweet image
5. Use it as the GitHub social preview image (Settings → Social preview)

## Helpful references

Repos with strong visual presentation worth studying:
- [karpathy/nanoGPT](https://github.com/karpathy/nanoGPT) — minimalist, all text, still beautiful
- [garrytan/gstack](https://github.com/garrytan/gstack) — terminal-recording GIFs
- [scverse/scanpy](https://github.com/scverse/scanpy) — scientific tool with logo + clean README
- [paul-gauthier/aider](https://github.com/paul-gauthier/aider) — animated GIF demo at top
- [ggerganov/llama.cpp](https://github.com/ggerganov/llama.cpp) — minimal, just works
