# /goal: write CONTRIBUTING.md establishing the three-example rule for new primitives + describing how to contribute

_Created: 2026-05-15_
_Completed: 2026-05-15_
_Working dir: `C:/Users/bobby/Downloads/vaultlab`_

## CONTEXT

- **Sub-goal:** 3.2 of the north-star plan
- **Advances:** Criterion #5 (enables non-Bobby contributions) + scope discipline
- **Starting state:** CONTRIBUTING.md already existed (133 lines, strong) with three-example rule for figure recipes specifically. 5 issue templates existed (add-recipe, add-tool-wrapper, bug, documentation, feature). README linked CONTRIBUTING.md but not Discussions or testimony channel.

## SUCCESS CRITERIA

1. CONTRIBUTING.md generalizes the three-example rule beyond figure recipes — applies to all new primitives. ✅
2. New `.github/ISSUE_TEMPLATE/testimony.md` exists for adoption signals ("I used vaultlab for X"). ✅
3. README has a prominent link block pointing to Discussions + testimony template. ✅
4. Three-example rule cross-references the strategic spec's scope philosophy. ✅

## PROGRESS

- Added "The three-example rule (for new primitives)" section above "How to contribute" in CONTRIBUTING.md. ✅
- Cross-referenced `.claude/goals/vaultlab-north-star.md` in the new section. ✅
- Created `.github/ISSUE_TEMPLATE/testimony.md` with structured "what you did / primitives used / what worked / what was rough / sharing preferences" sections. ✅
- Added README link block above the Influences section: "Used vaultlab? Tell us!" with direct issue template + Discussions URLs. ✅

## EVIDENCE

- ✅ Criterion #1: `CONTRIBUTING.md` now contains a top-level "The three-example rule (for new primitives)" section that explicitly generalizes the rule from figure-specific to all-new-primitives.
- ✅ Criterion #2: `.github/ISSUE_TEMPLATE/testimony.md` exists, labeled `testimony, adoption`, with title prefix `[USED-IT]`.
- ✅ Criterion #3: README has a "Used vaultlab? Tell us!" block right after the Contributors line, with direct links to the testimony template and Discussions.
- ✅ Criterion #4: The three-example rule section links to `.claude/goals/vaultlab-north-star.md` for the scope-philosophy anchor.

### Decisions made

- **Did NOT enable GitHub Discussions on the repo.** That's a GitHub-side action requiring repo-admin auth via `gh` CLI; deferred to sub-goal 3.3 which is purpose-built for it. README links to `/discussions` URL anyway so the link works once Discussions are enabled.
- **Did NOT touch CODE_OF_CONDUCT.md.** It already exists (Covenant 2.1, mentioned in CONTRIBUTING.md). No work needed.
- **Did NOT remove the figure-recipe-specific three-example rule from CONTRIBUTING.md.** The new general rule supplements it; the specific rule stays as a concrete example.

### Known limitations / followups

- Sub-goal 3.3 (enable Discussions, pin welcome thread) is the natural next step. Once Discussions are on, the "Used vaultlab? Tell us!" link block already in README will work.
