# Goal: `vaultlab demo` command + bundled sample data (sub-goal 1.4)

**Status:** SHIPPED 2026-05-15. Commit: see git log.

## Outcome

A fresh user runs `pip install vaultlab && vaultlab demo` and lands on a real audit-clean .pptx + provenance sidecars in ~1-2 seconds, with zero API keys, zero network calls, and zero configuration. This is the load-bearing enabler for north-star Criterion #4 (<30 min time-to-first-artifact); sub-goal 1.5 (scripted clean-VM onboarding test) builds directly on top of it.

## What shipped

### New files

| File | Role |
|---|---|
| `src/vaultlab/cli/demo.py` | Implementation. `run_demo(out_dir)` + argparse `main(argv)`. |
| `src/vaultlab/cli/demo.md` | Subcommand docs (matches the per-cmd `.md` convention). |
| `src/vaultlab/data/demo/__init__.py` | Package marker for bundled-data namespace. |
| `src/vaultlab/data/demo/paper.json` | Bibliographic metadata + abstract + key claims + discussion questions for one real PMC-OA paper (Bhate et al. 2022, Cell Systems). Only factual citation data — no copyrighted creative content. |
| `src/vaultlab/data/demo/_generate_demo_figures.py` | matplotlib script that produces the synthetic figures. Re-run to refresh. |
| `src/vaultlab/data/demo/figures/fig1_neighborhoods.png` | Synthetic CODEX-style cellular-neighborhood scatter. 32 KB. |
| `src/vaultlab/data/demo/figures/fig2_motif_frequencies.png` | Synthetic motif-frequency bar chart (normal vs tumor). 24 KB. |
| `tests/test_vaultlab_cli/test_demo.py` | 13 tests pinning the contract. |

### Modified files

| File | Change |
|---|---|
| `src/vaultlab/cli/__init__.py` | Added `demo` subcommand dispatch + advertised it in the usage banner. |
| `README.md` | New "First run — produce a real artifact in under 5 minutes" section right under the Quickstart, above-the-fold. |

### Not modified (per task constraints)

- `src/vaultlab/roles/` — left alone (other agent working there)
- `src/vaultlab/workflows/` — left alone (other agent working there)
- `pyproject.toml` — the existing `vaultlab = "vaultlab.cli:main"` entry already covers `vaultlab demo` via subcommand dispatch; no new script entry needed. The Hatch wheel target already auto-includes `src/vaultlab/**`, so the bundled PNGs ship without extra config.

## Design choices

1. **Subcommand pattern, not a new script entry.** The existing `vaultlab` console script (registered as `vaultlab.cli:main`) already takes an argv-style subcommand. Adding `demo` there matches the project's "one file per subcommand + sibling .md" convention from `AGENTS.md` and avoids polluting `[project.scripts]`.

2. **No LLM, no network.** The deck plan is composed deterministically in Python from `paper.json`. A `socket.socket`-blocking pytest sentinel confirms zero TCP/UDP attempts during `run_demo`. This means the demo doubles as a CI smoke test and works on a fresh machine before any `vaultlab init` / `claude-setup` run.

3. **Real audit-clean output, not a mock.** The demo uses the production `vaultlab.slides.deck.build_deck` + `vaultlab.provenance.write_receipts` — the .pptx and the sidecars are indistinguishable in shape from what a `/build-deck` run produces. This is what makes the demo "audit-clean" rather than "looks like a demo".

4. **Theme = `default`, not `hickey_lab`.** The Hickey Lab theme bundles a .pptx template that may or may not be present in a wheel install. `theme="default"` falls back to a vanilla 16:9 presentation that always works.

5. **Inputs are copied to `<out>/inputs/`.** Users who run `vaultlab demo` and want to remix it can edit `inputs/paper.json` and re-run — the demo reads the local copy, not the bundled one. The bundled originals stay untouched.

6. **Idempotent.** Running twice into the same output dir overwrites cleanly (`build_deck` accepts an existing path; `shutil.copy` overwrites; `write_receipts` overwrites the sidecar files).

7. **Sample paper choice — Bhate et al. 2022 Cell Systems.** A real PMC OA Subset paper aligned with Bobby's research topic (multiplexed tissue imaging, cellular neighborhoods). Only the factual bibliographic data is bundled (title/authors/DOI/abstract/key-claims) — this is citation-grade data that databases (PubMed, CrossRef, OpenAlex) redistribute freely. The two figures shipped with the demo are synthetic illustrations produced by matplotlib, **not** reproduced from the source paper.

## Tests

- `tests/test_vaultlab_cli/test_demo.py` — 13 tests, all green.
- `tests/test_vaultlab_invariants/` — still 8/8 green (no regression).
- `tests/test_vaultlab_slides/` — still 275/275 green (no regression from touching the slide composer's caller surface).

## Smoke results on this laptop

```
$ time vaultlab demo --out-dir /tmp/vaultlab-demo-top
[vaultlab demo] artifact: ...\deck.pptx
[vaultlab demo] elapsed:  1.1s
real    0m1.391s
```

7 slides, valid python-pptx load, valid provenance JSON, valid `.method.md`.

## Follow-ups (for sub-goal 1.5 and beyond)

- Wire a scripted clean-VM onboarding test that pip-installs vaultlab and runs `vaultlab demo` end-to-end with a wall-clock budget check (<5 min total).
- Consider adding `--variant figures-only` or `--variant lit-search-mock` flags so the demo can showcase the literature pipeline shape too (still offline, with stubbed search results bundled).
- Once the demo is featured at the top of the README, watch GitHub stars/PyPI downloads for a step change — it's the most-removable friction point for a first-time user.
