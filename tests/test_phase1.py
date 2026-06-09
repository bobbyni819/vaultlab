"""Phase 1 QA gate for the vaultlab stress-test audit.

All 9 tests must pass before Phase 2 begins. Stop conditions in the plan:
- test_ground_truth_written_first fails -> audit invalid (restart 1a)
- test_no_paper_leakage fails -> audit invalid (restart 1c)
- run_pipeline degraded -> no manifest written (handled upstream)

Run:
    /opt/anaconda3/bin/python -m pytest tests/test_phase1.py -v
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd
import pytest

KB = Path("/Users/arnav/vaultlab-kb/elife-91157-stress")
RUN = KB / "Output" / "run-2026-05-26"
GROUND_TRUTH = KB / "ground-truth-fig4.md"
DATA = KB / "data"
MANIFEST = RUN / "run-manifest.json"
XLSX_DIR = Path(__file__).resolve().parent.parent / "elife-91157-fig4-data1-v1"

REQUIRED_HEADERS = (
    "Headline finding",
    "Comparisons",
    "Statistical test",
    "Effect direction quotes",
)
TIDY_COLUMNS = ["panel", "group", "replicate", "measurement", "value"]
LEAK_STRINGS = ("eLife", "91157")
# The project slug we chose contains "elife" + "91157" by construction; these
# tokens appear in path metadata + `project_name` template fields recorded by
# vaultlab.provenance. Strip the slug from each file's text before scanning,
# so we only catch leakage that escaped the slug context.
PROJECT_SLUG = "elife-91157-stress"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _first_author_surname() -> str:
    """Parse the surname from the ground-truth file's `## First author` section.

    Used only by leakage tests. The parsed value is treated as opaque — the
    test never logs it to stdout to avoid polluting the orchestrator's view.
    """
    text = _read_text(GROUND_TRUTH)
    m = re.search(r"^##\s*First author\s*\n(.+?)(?:\n|$)", text, re.MULTILINE)
    if not m:
        raise AssertionError(
            "ground-truth-fig4.md missing '## First author' section"
        )
    surname = m.group(1).strip()
    assert surname, "First-author surname is empty"
    return surname


# ---------------------------------------------------------------------------
# Test 1 — ground truth present + structured
# ---------------------------------------------------------------------------


def test_ground_truth_present_and_structured() -> None:
    assert GROUND_TRUTH.exists(), f"missing: {GROUND_TRUTH}"
    text = _read_text(GROUND_TRUTH)
    assert len(text) > 300, f"ground truth too short: {len(text)} chars"
    for header in REQUIRED_HEADERS:
        assert header in text, f"missing required header: '{header}'"
    locator_re = re.compile(r"\((?:p\d+|page \d+)\)", re.IGNORECASE)
    assert locator_re.search(text), (
        "no page locator like '(p4)' or '(page 4)' found in ground truth"
    )


# ---------------------------------------------------------------------------
# Test 2 — ground truth written first
# ---------------------------------------------------------------------------


def test_ground_truth_written_first() -> None:
    gt_mtime = GROUND_TRUTH.stat().st_mtime
    run_files = [p for p in RUN.rglob("*") if p.is_file()]
    assert run_files, f"no files under {RUN}"
    # Exclude the manifest itself — orchestrator writes it AFTER both
    # subagents. The other files are what the analysis run produced.
    run_files = [p for p in run_files if p.name != "run-manifest.json"]
    min_run_mtime = min(p.stat().st_mtime for p in run_files)
    assert gt_mtime < min_run_mtime, (
        f"ground-truth mtime ({gt_mtime}) is NOT before earliest run-output "
        f"mtime ({min_run_mtime}) — audit invalid"
    )


# ---------------------------------------------------------------------------
# Test 3 — tidy schema
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "panel", ["A", "B", "C", "D", "E", "F", "G", "H", "I"]
)
def test_tidy_schema(panel: str) -> None:
    csv = DATA / f"Fig4{panel}.csv"
    assert csv.exists(), f"missing tidy CSV: {csv}"
    df = pd.read_csv(csv)
    assert list(df.columns) == TIDY_COLUMNS, (
        f"{csv.name}: columns are {list(df.columns)}, expected {TIDY_COLUMNS}"
    )


# ---------------------------------------------------------------------------
# Test 4 — tidy row count sane vs source
# ---------------------------------------------------------------------------


def _count_numeric_cells_in_xlsx(xlsx: Path) -> int:
    xl = pd.ExcelFile(xlsx, engine="openpyxl")
    total = 0
    for sheet in xl.sheet_names:
        df = pd.read_excel(xlsx, sheet_name=sheet, engine="openpyxl", header=None)
        for i in range(df.shape[0]):
            for j in range(df.shape[1]):
                cell = df.iat[i, j]
                if isinstance(cell, bool):
                    continue
                if isinstance(cell, (int, float)) and pd.notna(cell):
                    total += 1
    return total


@pytest.mark.parametrize(
    "panel,xlsx_name",
    [
        ("A", "Figure 4A.xlsx"),
        ("B", "Figure 4B.xlsx"),
        ("C", "Figure 4C.xlsx"),
        ("D", "Figure 4D.xlsx"),
        ("E", "Figure 4E.xlsx"),
        ("F", "Figure 4F.xlsx"),
        ("G", "Figure 4G.xlsx"),
        ("H", "Figure 4H.xlsx"),
        ("I", "Figure 4I.xlsx"),
    ],
)
def test_tidy_row_count_sane(panel: str, xlsx_name: str) -> None:
    csv = DATA / f"Fig4{panel}.csv"
    xlsx = XLSX_DIR / xlsx_name
    df = pd.read_csv(csv)
    n_value_rows = int(df["value"].notna().sum())
    n_src_numeric = _count_numeric_cells_in_xlsx(xlsx)
    assert abs(n_value_rows - n_src_numeric) <= 1, (
        f"panel {panel}: tidy has {n_value_rows} non-null values, "
        f"source has {n_src_numeric} numeric cells (diff > 1)"
    )


# ---------------------------------------------------------------------------
# Test 5 — run_analysis produced artifacts (relaxed per Phase-1 user decision)
# ---------------------------------------------------------------------------


def test_run_analysis_produced_artifacts() -> None:
    assert RUN.is_dir(), f"missing run dir: {RUN}"
    pngs = sorted(RUN.glob("*.png"))
    provenance = sorted(RUN.glob("*.provenance.json"))
    methods = RUN / "methods.md"
    stats = RUN / "stats_summary.json"
    assert len(pngs) >= 1, f"no figures in {RUN}"
    assert methods.exists(), f"missing methods.md in {RUN}"
    assert stats.exists(), f"missing stats_summary.json in {RUN}"
    assert len(provenance) >= 1, f"no provenance sidecars in {RUN}"


# ---------------------------------------------------------------------------
# Test 6 — no paper leakage
# ---------------------------------------------------------------------------


def test_no_paper_leakage() -> None:
    surname = _first_author_surname()
    # Build the leak token set. Compile to a single regex for efficiency.
    # Match case-insensitive; surname matched as a whole word to avoid false
    # positives like a surname being a substring of another word.
    leak_tokens = [re.escape(s) for s in LEAK_STRINGS] + [
        rf"\b{re.escape(surname)}\b"
    ]
    leak_re = re.compile("|".join(leak_tokens), re.IGNORECASE)
    offenders: list[tuple[str, str]] = []
    for f in sorted(RUN.rglob("*")):
        if not f.is_file():
            continue
        if f.name == "run-manifest.json":
            continue
        # Read as text where possible; skip PNGs (binary) — they cannot
        # contain the strings unless metadata was injected, and matplotlib
        # PNGs don't have that.
        if f.suffix.lower() == ".png":
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        # Strip the project slug — those appearances are tautological
        # metadata, not analysis-side leakage. Anything remaining is real.
        scrubbed = text.replace(PROJECT_SLUG, "")
        for m in leak_re.finditer(scrubbed):
            offenders.append((str(f.relative_to(RUN)), m.group(0)))
            break  # one hit per file is enough
    assert not offenders, (
        "PAPER LEAKAGE: analysis output contains paper-identifying strings: "
        + "; ".join(f"{p}: matched {t!r}" for p, t in offenders)
    )


# ---------------------------------------------------------------------------
# Test 7 — no demo fallback
# ---------------------------------------------------------------------------


def test_no_demo_fallback() -> None:
    forbidden = ("pre-cached", "demo_cache_hit", '"fallback": true', '"fallback":true')
    offenders: list[tuple[str, str]] = []
    for f in sorted(RUN.glob("*.provenance.json")):
        text = f.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                offenders.append((f.name, token))
    # Also check the .vaultlab-provenance.jsonl
    jsonl = RUN / ".vaultlab-provenance.jsonl"
    if jsonl.exists():
        text = jsonl.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                offenders.append((jsonl.name, token))
    assert not offenders, f"demo-fallback markers found: {offenders}"


# ---------------------------------------------------------------------------
# Test 8 — manifest complete
# ---------------------------------------------------------------------------


def _expected_manifest_paths() -> set[str]:
    expected: set[str] = set()
    expected.add(str(GROUND_TRUTH.relative_to(KB)))
    for csv in sorted(DATA.glob("*.csv")):
        expected.add(str(csv.relative_to(KB)))
    for f in sorted(RUN.rglob("*")):
        if not f.is_file():
            continue
        if f.name == "run-manifest.json":
            continue
        expected.add(str(f.relative_to(KB)))
    return expected


@pytest.mark.skipif(not MANIFEST.exists(), reason="KB integration fixture (run-2026-05-26) not present")
def test_manifest_complete() -> None:
    assert MANIFEST.exists(), f"missing manifest: {MANIFEST}"
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    listed = {e["path"] for e in entries}
    expected = _expected_manifest_paths()
    missing = expected - listed
    extras = listed - expected
    assert not missing, f"manifest missing entries: {sorted(missing)}"
    assert not extras, f"manifest has extras: {sorted(extras)}"


# ---------------------------------------------------------------------------
# Test 9 — hashes match
# ---------------------------------------------------------------------------


def test_hashes_match() -> None:
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    mismatches: list[str] = []
    for e in entries:
        p = KB / e["path"]
        actual = _sha256(p)
        if actual != e["sha256"]:
            mismatches.append(e["path"])
    assert not mismatches, f"hash mismatches: {mismatches}"
