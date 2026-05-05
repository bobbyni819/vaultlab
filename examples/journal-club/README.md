# Journal-club deck example

`expected_outputs/journal-club-pentimalli-2026-05-05.pptx` is a 16-slide journal-club deck VaultLab built for Pentimalli & Rajewsky 2025, *Cell Systems* (3D NSCLC atlas via CosMx + SHG ECM imaging). All 7 figures were extracted from the paper PDF; layouts auto-picked from each figure's aspect ratio; speaker notes auto-derived from a Tier-A summary; bullets animated click-by-click; inline emphasis applied (bold ALL-CAPS labels + accent-color take-aways).

Open the `.pptx` to see the click-through animations. The README's "See it in action" section embeds a static GIF cycling through every slide and two representative still screenshots.

**Build time:** ~90 seconds. **Audit:** 0 overflow / 0 overlap.

## What's in the deck

1. Title — paper, speaker, audience tag
2. Why this paper — outline of the contribution
3. Who built it — Berlin × Munich × Padua × NanoString consortium
4. The field — 7-year arc of spatial-omics maturation
5. Section divider — "Now the figures"
6–12. The 7 paper figures, each with descriptive sentence titles and 3-tier speaker notes
13. Strengths vs limitations — `analogy` layout (side-by-side reveal on click)
14. Take-home — `quote` layout (single big-text claim)
15. Discussion seeds — 5 numbered questions
16. References

## How it was built

The build script lived on the `prelim/journal-club-pentimalli-2026-05-05` branch and wraps `vaultlab.slides.deck.build_from_plan` with a hand-authored slide-plan dict. The plan is the kind of structure VaultLab's `/build-deck` slash command emits automatically; this example shows what one looks like.

The full Pentimalli Tier-A summary feeding the speaker notes is at `Wiki/Summaries/10.1016_j.cels.2025.101261.md` in any KB that has run a literature pipeline including this paper.
