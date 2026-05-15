# Sub-goal 5.1 — SPEC-B meta-agent roles

## Status: ALREADY SHIPPED (verified 2026-05-15)

## What

SPEC-B adds 4 persona-specific meta-agent roles that evaluate vaultlab
outputs against journal-grade and publication-readiness standards. The
"audit gate" every other workflow can call to answer *"is this output
good?"*.

Each role is a directory under `src/vaultlab/roles/` containing
`prompt.md` (the system prompt the LLM sees verbatim) and
`metadata.yaml` (the sidecar metadata loaded by `vaultlab.roles.load_role`).

| Role id | Persona | Lens |
| --- | --- | --- |
| `journal_reviewer` | Cell/Nature/eLife reviewer | Claim hedging, citation style, abstract-body alignment, figure-caption discipline, methodology-results-claim chain |
| `expert_reviewer` | PI / advisor / mentor (full project oversight + domain expertise) | Grant readiness, paper readiness, anticipated reviewer questions, power, replication, methodology alignment |
| `adoption_evaluator` | Fresh new user (lab member or external researcher in first 30 minutes) | Missing deps, assumed knowledge, hardcoded paths, interactive prompts, sequence pitfalls, recovery paths |
| `publication_guideline_compliance` | Deterministic compliance auditor | DPI, font sizes, palette accessibility, max categorical hues, panel-label convention, axis treatments, RGB color space |

## Naming note — `pi_evaluator` → `expert_reviewer`

The original SPEC-B task list named the PI-persona role `pi_evaluator`.
It was renamed to `expert_reviewer` in commits `59d0bf8` (rename) and
`613e528` (refine framing) on 2026-05-08, per Bobby's design call:

> "PI / advisor / mentor" is the gold-standard archetype because they
> have full project oversight + domain expertise. The role is named
> `expert_reviewer` (audience-neutral) but the prompt leans on the PI
> archetype as the simulated voice, so the role still applies to solo
> researchers, postdocs, industry researchers, and lab heads who don't
> sit under a formal academic PI structure.

The prompt explicitly references the PI archetype as the gold standard
while also surfacing non-PI user categories. Two existing test cases
enforce this:

- `test_expert_reviewer_uses_pi_archetype_as_gold_standard`
- `test_expert_reviewer_scales_beyond_academic_pi`

## Files (all on disk, no edits this session)

```
src/vaultlab/roles/
├── journal_reviewer/
│   ├── prompt.md       (3,776 chars, 6 focus areas, 6 eval criteria)
│   └── metadata.yaml
├── expert_reviewer/
│   ├── prompt.md       (5,814 chars, 6 focus areas, 6 eval criteria)
│   └── metadata.yaml
├── adoption_evaluator/
│   ├── prompt.md       (4,498 chars, 6 focus areas, 6 eval criteria)
│   └── metadata.yaml
└── publication_guideline_compliance/
    ├── prompt.md       (4,563 chars, 8 focus areas, 6 eval criteria)
    └── metadata.yaml
```

Slash commands at `.claude/commands/`:

- `journal-reviewer-audit.md`
- `expert-reviewer-audit.md`
- `adoption-evaluator-audit.md`
- `publication-guideline-audit.md`

## Loader / registry wiring

All 4 roles are auto-discoverable by `vaultlab.roles._loader`. They
appear in `list_roles()` (15-role catalog) and load through
`load_role(id)` without registry-side edits — the loader scans
`src/vaultlab/roles/*/` for any directory containing both `prompt.md`
and `metadata.yaml`.

## Metadata schema (`metadata.yaml`, not `role_card.json`)

The task spec proposed `role_card.json`. The repo's established convention
is `metadata.yaml` — same fields the original Bobby AI-Lab roles used,
loaded by `vaultlab.runner.models.Role`. It supports richer typed fields
(`focus_areas`, `evaluation_criteria`, `output_format`, `tools_allowed`,
`kb_outputs`) than a flat JSON card. No drift introduced.

## Anti-laziness compliance (per SPEC-B requirement)

Each prompt names at least 5 specific things to look for, not generic
checklists. Sample structure-by-structure tasks:

- `journal_reviewer` enumerates: (1) claim-hedging at low n, (2) citation
  style consistency, (3) abstract-body alignment, (4) figure-caption
  length limits per journal, (5) abbreviation discipline,
  (6) methodology-results-claim chain integrity.
- `expert_reviewer` enumerates: (1) power calc at n, (2) replication in
  independent cohort, (3) cohort/sample generalization, (4) methodology
  alignment with project's decisions log, (5) hedging discipline,
  (6) anticipated PI questions tied to project context.
- `adoption_evaluator` enumerates: (1) missing-dep surface,
  (2) assumed-knowledge gaps, (3) hardcoded paths, (4) interactive
  prompts, (5) sequence pitfalls, (6) permission/path issues,
  (7) recovery paths.
- `publication_guideline_compliance` enumerates: `fig_dpi`,
  `fig_font_min`, `fig_color_blind_safe`, `fig_color_count`,
  `fig_panel_label_convention`, `fig_axis_treatment`, `fig_color_space`,
  `fig_text_on_background`, `fig_palette_avoidance`.

## Output format

Every role outputs JSON-only (no free-text drift). Enforced by
`test_role_output_format_specifies_json` in
`tests/test_vaultlab_roles/test_meta_agent_roles.py`.

`journal_reviewer` uses the eLife evidence vocabulary
(exceptional/compelling/convincing/solid/incomplete/inadequate);
`expert_reviewer` uses the eLife two-axis rubric (significance ×
evidence); `adoption_evaluator` has a `bounce_risk` verdict for severe
friction; `publication_guideline_compliance` returns a per-check list
with `pass | warn | fail` results plus a concrete `fix` string.

## Tests

`tests/test_vaultlab_roles/test_meta_agent_roles.py` (190 lines, 30+
parametrized cases) and `tests/test_vaultlab_roles/test_loader.py`
(both updated to include the 4 SPEC-B roles in `EXPECTED_ROLE_IDS`).
Coverage enforces:

- Each role loads cleanly via `load_role`
- Prompts are substantive (`>1000` chars per SPEC-B)
- `focus_areas` ≥ 4 (actual: 6–8)
- `evaluation_criteria` ≥ 4 (actual: 6)
- `output_format` mandates JSON
- Each role appears in `list_roles()`
- `journal_reviewer` uses eLife evidence axis vocabulary (≥5 of 6 terms)
- `expert_reviewer` exposes `would_signoff_for_grant` and
  `would_signoff_for_paper` flags + uses two-axis rubric
- `expert_reviewer` references PI/advisor/mentor archetype (gold
  standard)
- `expert_reviewer` scales beyond academic-PI (≥2 non-PI user types
  named)
- `adoption_evaluator` surfaces `what_they_see` per friction item +
  exposes `bounce_risk` verdict
- `publication_guideline_compliance` defines `fig_dpi`, `fig_font_min`,
  `fig_color_blind_safe` checks + references `journal_guidelines/`
  yaml bundle
- All 4 roles reference KB output routing per AGENTS.md

## Verification (this session, 2026-05-15)

```
$ pytest tests/test_vaultlab_roles/ -q
176 passed in 0.89s

$ pytest tests/test_vaultlab_invariants/ -q
8 passed in 1.52s
```

15-role catalog confirmed via `vaultlab.roles.list_roles()`. Each of
the 4 SPEC-B roles loads with the expected name, prompt size, and
focus/criteria counts. Working tree clean; no source edits needed.

## Sample-workflow integration (optional in task spec)

Not wired in this session. Followup candidate: invoke `journal_reviewer`
as an optional post-step on `manuscript/polish` output (read the polished
section, return a JSON verdict). The role is callable via
`vaultlab.runner` today; only the workflow stitch is missing.

## Commits (historical)

- `c746aaa` — `feat(roles): SPEC-B — 4 meta-agent audit roles ship`
- `4a53d55` — `test(roles): update loader tests for 4 new SPEC-B roles`
- `e501560` — `feat(roles): wire SPEC-B for usable Python API`
- `59d0bf8` — `refactor(roles): rename pi_evaluator to expert_reviewer
  (audience-neutral)`
- `613e528` — `refactor(roles): expert_reviewer adopts PI / advisor as
  gold-standard archetype`

Released as part of `e9b5053` — `release: v0.0.3`.
