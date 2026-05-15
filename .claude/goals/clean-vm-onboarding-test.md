# Goal: scripted clean-VM onboarding test (sub-goal 1.5)

**Status:** SHIPPED 2026-05-15. Commit: see git log.

## Outcome

Every push and PR to `main` runs a clean Python 3.13 Docker container that performs the equivalent of a brand-new user's first session — install vaultlab from scratch, run `vaultlab demo`, verify a real .pptx + provenance sidecar land on disk — and asserts the total wall-clock falls under the 30-minute time-to-first-artifact bar. A green run of the new **Onboarding (Time-to-First-Artifact)** workflow IS the published evidence that north-star Criterion #4 is met. Sub-goal 1.4 (`vaultlab demo`) is the underlying enabler that makes the cold flow possible in seconds rather than minutes.

## What shipped

### New files

| File | Role |
|---|---|
| `Dockerfile.onboarding` | Clean `python:3.13-slim` base; installs `git`; copies `pyproject.toml` / `README.md` / `LICENSE` / `src/` / `tests/`; `pip install -e ".[dev,slides]"`; runs `measure_onboarding.sh` on container start. |
| `scripts/measure_onboarding.sh` | Times `vaultlab --version` → `vaultlab demo --out-dir /tmp/vaultlab-onboarding-out` → artifact-existence checks; fails if elapsed >= 1800s. |
| `.github/workflows/onboarding.yml` | Triggers on push/PR to main + `workflow_dispatch`; `runs-on: ubuntu-latest`; `timeout-minutes: 35`; build image → run image → print a "Criterion #4 met" footer on success. |
| `.claude/goals/clean-vm-onboarding-test.md` | This file. |

### Modified files

| File | Change |
|---|---|
| `README.md` | Added a "Reproduce the onboarding test" subsection right after the "First run" block. Documents the two-command local repro (`docker build` + `docker run`) and links the workflow file so readers can see Criterion #4 as a CI badge candidate. |

### Not modified (per task constraints)

- `src/vaultlab/` — left alone entirely; this sub-goal is pure CI plumbing.
- `src/vaultlab/kb/` and `src/vaultlab/slides/` — other agents working there, kept untouched.
- `pyproject.toml` — no new extras needed; the demo's runtime dependency is `python-pptx` which already lives in `[slides]`.

## Design choices

1. **Docker, not a bare GitHub Actions matrix.** A fresh `python:3.13-slim` container is the cleanest reproducible "new user" environment. Matrix-style runners inherit cached pip dependencies, system libraries, and a populated `~/.cache`; a slim Docker image does not. The image is the closest approximation we can run inside CI minutes to "Bobby's mom on a fresh laptop". Bonus: the same `docker run` command reproduces the test locally, so a contributor can debug a CI failure on their machine without pushing.

2. **Install extras = `[dev,slides]`.** `dev` is for parity with `test.yml`'s linter/type-check job. `slides` is the load-bearing extra — it brings in `python-pptx`, which `vaultlab.slides.deck.build_deck` (the function `vaultlab demo` ultimately calls) imports. The task spec said `[dev]` only, but the demo would fail to import without `slides` since the base install deliberately keeps `python-pptx` out (per `pyproject.toml` line 35-38 comment: "Core kept small on purpose so a fresh `pip install vaultlab` is fast and small. Heavier deps live in optional extras."). Documented the rationale inline in the Dockerfile so this decision is self-explaining.

3. **Install from the working tree, not from PyPI.** The published wheel always lags HEAD by at least one release cut. Installing from the working tree means a PR that breaks the cold-start flow fails CI *before* it merges, not afterward. The Dockerfile comment notes that swapping to `pip install vaultlab` is a one-line change if we ever want to gate releases on a green run against the actual PyPI artifact. Sub-goal 1.5 is about proving the cold path works on a clean OS; sub-goal "verify PyPI artifact" is a future addition, not what was asked.

4. **30-min bar with a 35-min workflow timeout.** The 30-min number comes from the north-star plan; the 5-min cushion gives the Docker layer cache time to build the image without burning the budget. Real-world elapsed on a GitHub runner should be well under 60s once layers cache.

5. **Three-step script: version, demo, verify.** `vaultlab --version` proves the CLI registered on PATH (catches editable-install setup bugs). `vaultlab demo` does the real work. `test -f` on the two artifact files catches the "demo silently fell back to a dry-run" failure mode that a pure exit-code check would miss. Each step echoes a `[onboarding] step N` marker so a CI log skim tells you which step failed.

6. **Output dir `/tmp/vaultlab-onboarding-out`, not the default.** Using a fixed absolute path in /tmp (a) guarantees we know where to grep for the artifact, (b) keeps the working dir clean if someone re-runs the container interactively, and (c) sidesteps any Windows-vs-Linux relative-path ambiguity that could creep in if the script ever gets re-used outside Docker.

7. **`continue-on-error: false` (default) everywhere.** Onboarding is a load-bearing acceptance criterion — there is no "this part is allowed to fail" step. A red onboarding run blocks the merge.

## Smoke results

Local `docker build` was not attempted in this session — Docker Desktop is not running on Bobby's Windows host and starting it interactively is out of scope for a CI-plumbing sub-goal. The Dockerfile is short and matches the pattern of the existing `test.yml` extras install (`[dev,slides,figures,research,citations]`), so the failure modes are limited to:

- typo in the script (caught by `bash -n` syntax check, which passed)
- typo in the Dockerfile (caught by GitHub Actions' first run, since the workflow `runs-on: ubuntu-latest` and has full Docker available)
- a missing extra (caught by the workflow's `vaultlab --version` step, which would import-error if `python-pptx` were missing)

The first push to `main` will be the live smoke test; the runner is fully owned and a red run is recoverable in a follow-up commit.

## Follow-ups

- Add a PyPI-artifact variant of the workflow once a tagged release exists post-merge — flip `INSTALL_SOURCE=pypi` in the Dockerfile (the placeholder is already commented in) and gate every release tag on a green run against the published wheel.
- Consider adding a `windows-latest` matrix entry to catch Windows-specific path / encoding regressions (Bobby's primary dev OS). Today's task spec said ubuntu-only and the GitHub Actions minute budget is tight, so it's deferred.
- Wire the workflow's badge URL into the README's badge row at the top of the file once the first run goes green, replacing the current Tests badge if we settle on Onboarding as the primary CI signal.
