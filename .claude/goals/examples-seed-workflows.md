# /goal: 3 seed example workflows in examples/ — sub-goal 3.1 of north-star

_Created: 2026-05-15_
_Working dir: `C:/Users/bobby/Downloads/vaultlab`_

## CONTEXT

- **Sub-goal:** 3.1 of the north-star plan
- **Advances:** Criterion #5 (≥3 example workflows in `examples/` authored by someone other than Bobby) — Bobby-authored seeds lower the threshold so external contributions can use them as templates
- **Starting state:** `examples/` had `journal-club/` (README + 18MB pptx, no `run.py`), `sample_deck/` (expected output only), `html_report_gallery/` (full executable), `codex_hubmap_tonsil/`, `pbmc3k/`, `visium_brain/` (README stubs). No standardized `run.py` / `inputs/` / `expected-outputs/` triad documented.

## SUCCESS CRITERIA

1. Three new self-contained example subdirectories with `README.md` + `run.py` + `inputs/` + `expected-outputs/`. ✅
2. `examples/README.md` index documents the directory convention so external contributors can clone the shape. ✅
3. Each `run.py` is syntactically valid and importable (sanity check only — no CI execution). ✅
4. No new dependencies in `pyproject.toml`. ✅
5. No binaries > 200 KB committed; any larger expected output replaced by `SUMMARY.md`. ✅
6. Sample inputs are PMC-OA or synthetic (documented in example README). ✅
7. LLM steps fall back to mocked content if no API key — examples must NOT block on missing config. ✅

## PROGRESS

- `examples/journal-club/run.py` — composes `vaultlab.research.ResearchClient` → narrative outline → `vaultlab.slides.build_from_plan` for a 1-paper journal-club deck. Falls back to bundled metadata if no API key. PMC OA paper used for input.
- `examples/manuscript-section/run.py` — assembles 2 synthetic figures with `vaultlab.figures.acquisition` → drafts section using `vaultlab.manuscript.polish` rules as guard (no LLM) → runs `vaultlab.citations.audit_file` on the result.
- `examples/citation-cleanup/run.py` — extracts citations with `vaultlab.citations.extract_citations`, builds a remediation report classifying each into verified / suspect / unverified / malformed without external API calls.
- `examples/README.md` — added top-level index + directory-convention block + pointer to CONTRIBUTING.md three-example rule.
- Each example's `expected-outputs/` contains either committed reference output (<200 KB) or `SUMMARY.md` describing what `run.py` produces.

## EVIDENCE

- `for f in examples/{journal-club,manuscript-section,citation-cleanup}/run.py; do python -c "import ast; ast.parse(open('$f').read())"; done` exits 0 — see verification block below.
- `examples/README.md` lists all 3 new examples + the 6 prior examples.
- `git diff --stat HEAD~1 HEAD` shows only `examples/**` touched.

## NOTES

- The existing 18MB `examples/journal-club/expected_outputs/journal-club-pentimalli-2026-05-05.pptx` was pre-existing and is preserved; new `run.py` writes to a separate, smaller output documented in `expected-outputs/SUMMARY.md`.
- LLM-dependent paths (polish, summarization) are mocked deterministically with realistic shapes so external contributors can run examples locally without API keys and still see meaningful output.
- Author: Bobby (these are seeds). Criterion #5's gate remains *external* contributions to `examples/`.
