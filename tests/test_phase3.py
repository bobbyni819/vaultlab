"""Phase 3 QA gate — deterministic rubric aggregation.

8 tests. Run:
    /opt/anaconda3/bin/python -m pytest tests/test_phase3.py -v
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

KB = Path("/Users/arnav/vaultlab-kb/elife-91157-stress")

import pytest

# Skip this eLife-91157 stress-test QA gate when its fixture is absent (it lives on Arnav's
# local machine). Keeps CI green off-fixture; the gate still runs where the data exists.
pytestmark = pytest.mark.skipif(
    not KB.exists(),
    reason="eLife-91157 stress-test fixture not present (Arnav Dhar's local KB)",
)
RUN = KB / "Output" / "run-2026-05-26"
RUBRIC = RUN / "rubric-scores.json"
AGGREGATE_PY = RUN / "aggregate.py"
AUDIT_ROWS = RUN / "audit-rows.jsonl"

LANES = ("rigor", "methods_critic", "cite", "figure")
VERDICTS = {"pass", "warn", "fail"}
CONCLUSION_VERDICTS = {"yes", "hedged", "no"}


def _rubric() -> dict:
    return json.loads(RUBRIC.read_text(encoding="utf-8"))


def _audit_by_lane() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {ln: [] for ln in LANES}
    for line in AUDIT_ROWS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        out.setdefault(r.get("lane", ""), []).append(r)
    return out


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Test 1 — verdict enum
# ---------------------------------------------------------------------------


def test_verdict_enum() -> None:
    r = _rubric()
    assert r["conclusion_match"]["verdict"] in CONCLUSION_VERDICTS, (
        f"conclusion_match.verdict invalid: {r['conclusion_match']['verdict']!r}"
    )
    for lane in LANES:
        v = r["per_lane"][lane]["verdict"]
        assert v in VERDICTS, f"per_lane.{lane}.verdict invalid: {v!r}"


# ---------------------------------------------------------------------------
# Test 2 — lane counts consistent
# ---------------------------------------------------------------------------


def test_lane_counts_consistent() -> None:
    r = _rubric()
    by_lane = _audit_by_lane()

    rigor = r["per_lane"]["rigor"]
    expected_high = sum(
        1 for x in by_lane["rigor"] if x.get("severity") in ("high", "blocker")
    )
    expected_blocker = sum(1 for x in by_lane["rigor"] if x.get("severity") == "blocker")
    expected_medium = sum(1 for x in by_lane["rigor"] if x.get("severity") == "medium")
    expected_low = sum(1 for x in by_lane["rigor"] if x.get("severity") == "low")
    assert rigor["high"] == expected_high, f"rigor.high {rigor['high']} != {expected_high}"
    assert rigor["blocker"] == expected_blocker, f"rigor.blocker {rigor['blocker']} != {expected_blocker}"
    assert rigor["medium"] == expected_medium, f"rigor.medium {rigor['medium']} != {expected_medium}"
    assert rigor["low"] == expected_low, f"rigor.low {rigor['low']} != {expected_low}"

    mc = r["per_lane"]["methods_critic"]
    assert mc["overclaim"] == sum(
        1 for x in by_lane["methods_critic"] if x.get("verdict") == "overclaim"
    )
    assert mc["unsupported"] == sum(
        1 for x in by_lane["methods_critic"] if x.get("verdict") == "unsupported"
    )

    cite = r["per_lane"]["cite"]
    assert cite["unresolved"] == sum(
        1 for x in by_lane["cite"] if x.get("independent_resolves") is False
    )
    assert cite["wrong_paper"] == sum(
        1 for x in by_lane["cite"] if x.get("independent_title_match") is False
    )
    assert cite["claim_unsupported"] == sum(
        1 for x in by_lane["cite"] if x.get("independent_supports_surrounding_claim") is False
    )

    fig = r["per_lane"]["figure"]
    paper_set = {"vaultlab_disagrees_with_paper", "all_three_disagree", "paper_disagrees_with_data"}
    data_set = {"vaultlab_disagrees_with_data", "all_three_disagree"}
    assert fig["disagree_with_paper"] == sum(
        1 for x in by_lane["figure"] if x.get("agreement") in paper_set
    )
    assert fig["disagree_with_data"] == sum(
        1 for x in by_lane["figure"] if x.get("agreement") in data_set
    )


# ---------------------------------------------------------------------------
# Test 3 — conclusion evidence traceable
# ---------------------------------------------------------------------------


def test_conclusion_evidence_traceable() -> None:
    r = _rubric()
    by_lane = _audit_by_lane()
    all_ids = {x["finding_id"] for rows in by_lane.values() for x in rows}
    for fid in r["conclusion_match"]["evidence"]:
        assert fid in all_ids, (
            f"conclusion_match.evidence references unknown finding_id {fid!r}"
        )


# ---------------------------------------------------------------------------
# Test 4 — overclaim evidence quoted
# ---------------------------------------------------------------------------


def test_overclaim_evidence_quoted() -> None:
    r = _rubric()
    for entry in r["overclaim_instances"]:
        quote = entry.get("quote", "")
        assert quote.strip(), f"overclaim entry has empty quote: {entry}"
        artifact = KB / entry["artifact"]
        assert artifact.exists(), f"overclaim artifact missing: {artifact}"
        text = artifact.read_text(encoding="utf-8")
        assert quote in text, (
            f"overclaim quote not verbatim in artifact: artifact={artifact}, "
            f"quote={quote!r}"
        )


# ---------------------------------------------------------------------------
# Test 5 — citation failure inventory
# ---------------------------------------------------------------------------


def test_citation_failure_inventory() -> None:
    r = _rubric()
    cite = r["per_lane"]["cite"]
    expected = cite["unresolved"] + cite["wrong_paper"] + cite["claim_unsupported"]
    actual = len(r["citation_failures"])
    assert actual == expected, (
        f"citation_failures length {actual} != "
        f"unresolved+wrong_paper+claim_unsupported={expected}"
    )


# ---------------------------------------------------------------------------
# Test 6 — mismatch inventory
# ---------------------------------------------------------------------------


def test_mismatch_inventory() -> None:
    r = _rubric()
    methods_text = (RUN / "methods.md").read_text(encoding="utf-8") if (RUN / "methods.md").exists() else ""
    by_lane = _audit_by_lane()
    figure_rows = {row["panel"]: row for row in by_lane["figure"]}
    for m in r["figure_methods_mismatches"]:
        figure_claim = m.get("figure_claim", "")
        methods_claim = m.get("methods_claim", "")
        assert figure_claim.strip(), f"empty figure_claim in mismatch: {m}"
        assert methods_claim.strip(), f"empty methods_claim in mismatch: {m}"
        # methods_claim must appear in methods.md
        assert methods_claim in methods_text, (
            f"mismatch methods_claim not in methods.md: {methods_claim!r}"
        )
        # figure_claim must appear in the corresponding Lane D row's
        # vaultlab_conclusion or evidence_quote.
        panel_name = Path(m["figure"]).stem.split("_")[0]  # "Fig4A"
        panel_key = panel_name.replace("Fig", "")  # "4A"
        row = figure_rows.get(panel_key)
        assert row is not None, f"no Lane D row for panel {panel_key}"
        hay = (row.get("vaultlab_conclusion", "") + "\n" + row.get("evidence_quote", ""))
        assert figure_claim in hay, (
            f"figure_claim not in Lane D row vaultlab_conclusion/evidence_quote "
            f"for panel {panel_key}: {figure_claim!r}"
        )


# ---------------------------------------------------------------------------
# Test 7 — reproducible
# ---------------------------------------------------------------------------


def test_reproducible() -> None:
    first = _sha256(RUBRIC)
    result = subprocess.run(
        [sys.executable, str(AGGREGATE_PY)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"aggregate.py exited nonzero: {result.stderr}"
    second = _sha256(RUBRIC)
    assert first == second, (
        f"non-reproducible: first sha256={first}, second={second}"
    )


# ---------------------------------------------------------------------------
# Test 8 — no LLM / network in aggregator
# ---------------------------------------------------------------------------


ALLOWED_STDLIB = {
    "json", "re", "hashlib", "pathlib", "math", "dataclasses", "typing",
    "collections", "sys", "os", "__future__",
}
ALLOWED_THIRD_PARTY = {"pandas"}
FORBIDDEN_NAMES = re.compile(
    r"\b(anthropic|openai|requests|urllib|httpx|aiohttp|websocket)\b",
    re.IGNORECASE,
)


def test_no_llm_in_aggregation() -> None:
    src = AGGREGATE_PY.read_text(encoding="utf-8")
    # AST-level check — only inspect real imports, not docstrings.
    tree = ast.parse(src)
    illegal: list[str] = []
    forbidden_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                top = n.name.split(".")[0]
                if FORBIDDEN_NAMES.search(top) or top == "subprocess":
                    forbidden_imports.append(n.name)
                elif top not in ALLOWED_STDLIB and top not in ALLOWED_THIRD_PARTY:
                    illegal.append(n.name)
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            if FORBIDDEN_NAMES.search(top) or top == "subprocess":
                forbidden_imports.append(node.module or "<empty>")
            elif top and top not in ALLOWED_STDLIB and top not in ALLOWED_THIRD_PARTY:
                illegal.append(node.module or "<empty>")
    assert not forbidden_imports, (
        f"forbidden (LLM/network/subprocess) imports in aggregate.py: {forbidden_imports}"
    )
    assert not illegal, f"illegal imports in aggregate.py: {illegal}"
