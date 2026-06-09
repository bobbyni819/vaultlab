"""Phase 2 QA gate for the vaultlab stress-test audit.

8 tests. All must pass before Phase 3.

Run:
    /opt/anaconda3/bin/python -m pytest tests/test_phase2.py -v
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import pytest

KB = Path("/Users/arnav/vaultlab-kb/elife-91157-stress")

# Skip this eLife-91157 stress-test QA gate when its fixture is absent (it lives on Arnav's
# local machine). Keeps CI green off-fixture; the gate still runs where the data exists.
pytestmark = pytest.mark.skipif(
    not KB.exists(),
    reason="eLife-91157 stress-test fixture not present (Arnav Dhar's local KB)",
)
RUN = KB / "Output" / "run-2026-05-26"
LANES = RUN / "lanes"
MERGED = RUN / "audit-rows.jsonl"
GROUND_TRUTH = KB / "ground-truth-fig4.md"
MANIFEST = RUN / "run-manifest.json"

LANE_NAMES = ("rigor", "methods_critic", "cite", "figure")
PANELS = ("4A", "4B", "4C", "4D", "4E", "4F", "4G", "4H", "4I")

REQUIRED_KEYS = {
    "rigor": (
        "lane", "artifact", "finding_id", "issue", "severity", "quote",
        "rule_violated",
    ),
    "methods_critic": (
        "lane", "artifact", "finding_id", "claim_quote", "claim_type",
        "verdict", "evidence_quote", "notes",
    ),
    "cite": (
        "lane", "artifact", "finding_id", "citation_id", "claimed_title",
        "claimed_authors", "claimed_year", "cite_audit_verdict",
        "independent_resolves", "independent_title_match",
        "independent_supports_surrounding_claim", "evidence_quote", "notes",
    ),
    "figure": (
        "lane", "artifact", "finding_id", "panel", "vaultlab_conclusion",
        "ground_truth_conclusion", "recomputed_direction",
        "recomputed_p_lt_0_05", "agreement", "evidence_quote",
        "ground_truth_quote", "notes",
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_jsonl(p: Path) -> list[dict]:
    rows: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def _merged_by_lane() -> dict[str, list[dict]]:
    rows = _load_jsonl(MERGED)
    out: dict[str, list[dict]] = {ln: [] for ln in LANE_NAMES}
    for r in rows:
        out.setdefault(r.get("lane", ""), []).append(r)
    return out


# ---------------------------------------------------------------------------
# Test 1 — all four lanes present
# ---------------------------------------------------------------------------


def test_all_four_lanes_present() -> None:
    assert MERGED.exists(), f"missing merged file: {MERGED}"
    by_lane = _merged_by_lane()
    empty = [ln for ln in LANE_NAMES if not by_lane.get(ln)]
    assert not empty, (
        f"empty lane(s) in audit-rows.jsonl: {empty} "
        f"— structural-gap rows (no_claims_present/no_citations_present) "
        f"should count as participation; this means a lane wrote zero rows"
    )


# ---------------------------------------------------------------------------
# Test 2 — JSONL well-formed (required keys per lane)
# ---------------------------------------------------------------------------


def test_jsonl_well_formed() -> None:
    # Each lanes/<lane>.jsonl parses and has required keys
    for lane in LANE_NAMES:
        p = LANES / f"{lane}.jsonl"
        rows = _load_jsonl(p)
        assert rows, f"empty file: {p}"
        required = REQUIRED_KEYS[lane]
        for i, r in enumerate(rows, 1):
            missing = [k for k in required if k not in r]
            assert not missing, (
                f"{lane}.jsonl line {i}: missing keys {missing}"
            )
            assert r["lane"] == lane, (
                f"{lane}.jsonl line {i}: lane field is {r['lane']!r}"
            )
    # Merged file is JSONL and parses
    merged = _load_jsonl(MERGED)
    assert merged, "audit-rows.jsonl is empty"


# ---------------------------------------------------------------------------
# Test 3 — no prose leaked (every non-blank line parses as a JSON object)
# ---------------------------------------------------------------------------


def test_no_prose_leaked() -> None:
    for lane in LANE_NAMES:
        p = LANES / f"{lane}.jsonl"
        for i, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            line = raw.rstrip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise AssertionError(
                    f"{lane}.jsonl line {i} is not valid JSON: {e}"
                )
            assert isinstance(obj, dict), (
                f"{lane}.jsonl line {i} is not a JSON object: {type(obj).__name__}"
            )


# ---------------------------------------------------------------------------
# Test 4 — citation inventory complete
# ---------------------------------------------------------------------------


def _grep_dois_pmids() -> set[str]:
    """Independent regex grep for DOIs / PMIDs across the run dir."""
    doi_re = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
    pmid_re = re.compile(r"\bPMID:?\s*(\d{4,10})\b", re.IGNORECASE)
    found: set[str] = set()
    for f in RUN.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() == ".png":
            continue
        if f.name == "run-manifest.json":
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for m in doi_re.finditer(text):
            found.add(m.group(0).rstrip(".,);"))
        for m in pmid_re.finditer(text):
            found.add(f"PMID:{m.group(1)}")
    return found


def test_citation_inventory_complete() -> None:
    by_lane = _merged_by_lane()
    cite_rows = by_lane["cite"]
    listed_ids = {r["citation_id"] for r in cite_rows if r.get("citation_id")}
    actual_ids = _grep_dois_pmids()
    assert listed_ids == actual_ids, (
        f"citation inventory mismatch: Lane C lists {sorted(listed_ids)} "
        f"vs independent grep found {sorted(actual_ids)}"
    )


# ---------------------------------------------------------------------------
# Test 5 — figure inventory complete
# ---------------------------------------------------------------------------


def _panels_in_ground_truth() -> set[str]:
    text = GROUND_TRUTH.read_text(encoding="utf-8")
    return {m.group(0) for m in re.finditer(r"4[A-I]\b", text)}


def _figure_pngs_in_manifest() -> set[str]:
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {e["path"] for e in entries if e["path"].endswith(".png")}


def test_figure_inventory_complete() -> None:
    by_lane = _merged_by_lane()
    figure_rows = by_lane["figure"]
    panels_in_lane = sorted(r["panel"] for r in figure_rows)
    assert panels_in_lane == sorted(PANELS), (
        f"Lane D panels {panels_in_lane} != expected {sorted(PANELS)}"
    )
    # Every panel from ground truth appears in Lane D
    gt_panels = _panels_in_ground_truth()
    missing_from_lane = gt_panels - set(panels_in_lane)
    assert not missing_from_lane, (
        f"panels referenced in ground-truth-fig4.md but missing from Lane D: "
        f"{sorted(missing_from_lane)}"
    )
    # Every figure PNG in the manifest is referenced by some Lane D row
    artifact_paths = {r["artifact"] for r in figure_rows}
    manifest_pngs = _figure_pngs_in_manifest()
    missing_artifacts = manifest_pngs - artifact_paths
    assert not missing_artifacts, (
        f"manifest PNGs not referenced by any Lane D row: "
        f"{sorted(missing_artifacts)}"
    )


# ---------------------------------------------------------------------------
# Test 6 — independent cross-check done
# ---------------------------------------------------------------------------


def test_independent_cross_check_done() -> None:
    by_lane = _merged_by_lane()
    for r in by_lane["cite"]:
        if r.get("cite_audit_verdict") == "no_citations_present":
            # Structural-gap row — independent_resolves allowed to be null
            continue
        if r.get("citation_id") in (None, ""):
            continue
        assert r.get("independent_resolves") is not None, (
            f"Lane C row {r.get('finding_id')} has citation_id "
            f"{r.get('citation_id')!r} but independent_resolves is null — "
            f"the Crossref/PubMed lookup did not run"
        )


# ---------------------------------------------------------------------------
# Test 7 — three-way compare done
# ---------------------------------------------------------------------------


def test_three_way_compare_done() -> None:
    by_lane = _merged_by_lane()
    valid_directions = {"up", "down", "null"}
    for r in by_lane["figure"]:
        fid = r.get("finding_id")
        vlc = r.get("vaultlab_conclusion")
        gtc = r.get("ground_truth_conclusion")
        rdir = r.get("recomputed_direction")
        assert isinstance(vlc, str) and vlc.strip(), (
            f"{fid}: vaultlab_conclusion empty/null"
        )
        assert isinstance(gtc, str) and gtc.strip(), (
            f"{fid}: ground_truth_conclusion empty/null"
        )
        assert rdir in valid_directions, (
            f"{fid}: recomputed_direction is {rdir!r}, "
            f"must be one of {valid_directions}"
        )


# ---------------------------------------------------------------------------
# Test 8 — evidence quote invariant
# ---------------------------------------------------------------------------


GAP_VERDICTS = {"no_claims_present", "no_citations_present"}
SILENT_AGREEMENTS = {
    "vaultlab_silent_paper_data_agree",
    "vaultlab_silent_paper_data_disagree",
}


def test_evidence_quote_invariant() -> None:
    by_lane = _merged_by_lane()
    # Lane B: rows with verdict NOT in gap-verdicts must have evidence_quote
    for r in by_lane["methods_critic"]:
        if r.get("verdict") in GAP_VERDICTS:
            continue
        assert r.get("evidence_quote", "").strip(), (
            f"methods_critic {r.get('finding_id')}: "
            f"verdict={r.get('verdict')!r} requires non-empty evidence_quote"
        )
    # Lane C: rows with cite_audit_verdict NOT in gap-verdicts and that
    # claim support (independent_supports_surrounding_claim is True or
    # False) must have evidence_quote.
    for r in by_lane["cite"]:
        if r.get("cite_audit_verdict") in GAP_VERDICTS:
            continue
        if r.get("independent_supports_surrounding_claim") is None:
            continue
        assert r.get("evidence_quote", "").strip(), (
            f"cite {r.get('finding_id')}: requires non-empty evidence_quote"
        )
    # Lane D: rows whose agreement is NOT a silent_* class must have
    # evidence_quote (the vaultlab-side reference sentence).
    for r in by_lane["figure"]:
        if r.get("agreement") in SILENT_AGREEMENTS:
            continue
        assert r.get("evidence_quote", "").strip(), (
            f"figure {r.get('finding_id')}: agreement={r.get('agreement')!r} "
            f"requires non-empty evidence_quote"
        )
    # Lane A: rigor findings with severity != 'low' should have a quote
    for r in by_lane["rigor"]:
        if r.get("severity") == "low":
            continue
        assert r.get("quote", "").strip(), (
            f"rigor {r.get('finding_id')}: severity={r.get('severity')!r} "
            f"requires non-empty quote"
        )
