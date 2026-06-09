"""Phase 4 QA gate — final deliverable + bug-reports + clusters.

Run:
    /opt/anaconda3/bin/python -m pytest tests/test_phase4.py -v
"""

from __future__ import annotations

import json
import re
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
DELIVERABLE = KB / "Output" / "vaultlab-stress-test-2026-05-26.md"
BUG_REPORTS = RUN / "bug-reports.jsonl"
RUBRIC = RUN / "rubric-scores.json"
AUDIT_ROWS = RUN / "audit-rows.jsonl"
GROUND_TRUTH = KB / "ground-truth-fig4.md"

SEVERITY_ENUM = {"critical", "major", "minor"}
FAILURE_MODE_ENUM = {"hallucination", "retrieval", "provenance-break", "prompt-ambiguity"}

SECTION_RE = [
    re.compile(r"^##\s*1\.\s*Did vaultlab arrive at the same conclusion", re.MULTILINE),
    re.compile(r"^##\s*2\.\s*Per-audit-lane results", re.MULTILINE),
    re.compile(r"^##\s*3\.\s*Overclaims", re.MULTILINE),
    re.compile(r"^##\s*4\.\s*Citation failures", re.MULTILINE),
    re.compile(r"^##\s*5\.\s*Figure", re.MULTILINE),
    re.compile(r"^##\s*6\.\s*Failure-mode clusters", re.MULTILINE),
    re.compile(r"^##\s*7\.\s*Ground-truth reference", re.MULTILINE),
    re.compile(r"^##\s*8\.\s*Reproducer", re.MULTILINE),
]


def _read_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def _deliverable_text() -> str:
    return DELIVERABLE.read_text(encoding="utf-8")


def _section(text: str, n: int) -> str:
    """Return the text of section N (between ## N. and ## N+1. or EOF)."""
    pattern = rf"^##\s*{n}\.\s.+?(?=^##\s*{n + 1}\.\s|\Z)"
    m = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return m.group(0) if m else ""


# ---------------------------------------------------------------------------
# Test 1 — deliverable path exact
# ---------------------------------------------------------------------------


def test_deliverable_path_exact() -> None:
    assert DELIVERABLE.exists(), f"missing deliverable: {DELIVERABLE}"
    assert DELIVERABLE.is_file()
    assert str(DELIVERABLE) == "/Users/arnav/vaultlab-kb/elife-91157-stress/Output/vaultlab-stress-test-2026-05-26.md"


# ---------------------------------------------------------------------------
# Test 2 — 8 sections in order
# ---------------------------------------------------------------------------


def test_deliverable_sections_present() -> None:
    text = _deliverable_text()
    last_end = -1
    for i, regex in enumerate(SECTION_RE, 1):
        m = regex.search(text)
        assert m, f"section {i} header missing"
        assert m.start() > last_end, f"section {i} appears out of order"
        last_end = m.start()


# ---------------------------------------------------------------------------
# Test 3 — verdict matches rubric
# ---------------------------------------------------------------------------


def test_verdict_matches_rubric() -> None:
    rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
    verdict = rubric["conclusion_match"]["verdict"]
    section1 = _section(_deliverable_text(), 1)
    assert f"**Verdict: {verdict}**" in section1, (
        f"section 1 missing 'Verdict: {verdict}' line"
    )


# ---------------------------------------------------------------------------
# Test 4 — lane table matches rubric
# ---------------------------------------------------------------------------


def test_lane_table_matches_rubric() -> None:
    rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
    section2 = _section(_deliverable_text(), 2)
    lanes = [
        ("rigor_auditor", rubric["per_lane"]["rigor"]),
        ("methods_critic", rubric["per_lane"]["methods_critic"]),
        ("cite_audit", rubric["per_lane"]["cite"]),
        ("figure faithfulness", rubric["per_lane"]["figure"]),
    ]
    for name, data in lanes:
        # Row starts with `| <name> | <verdict> |`
        assert f"| {name} | {data['verdict']} |" in section2, (
            f"lane row missing or verdict mismatch for {name!r}: "
            f"expected verdict={data['verdict']!r}"
        )


# ---------------------------------------------------------------------------
# Test 5 — empty sections explicit
# ---------------------------------------------------------------------------


def test_empty_sections_explicit() -> None:
    text = _deliverable_text()
    for n in (3, 4, 5):
        sec = _section(text, n)
        assert sec, f"section {n} not found"
        body = sec.split("\n", 1)[1] if "\n" in sec else ""
        has_bullet = bool(re.search(r"^-\s", body, re.MULTILINE))
        has_none = "None detected" in body
        assert has_bullet or has_none, (
            f"section {n} is empty without 'None detected'"
        )


# ---------------------------------------------------------------------------
# Test 6 — bug↔audit bijection
# ---------------------------------------------------------------------------


def _is_bug_row(row: dict) -> bool:
    lane = row["lane"]
    if lane == "rigor":
        if row.get("issue") == "no_rigor_issues_detected":
            return False
        return row.get("severity") in ("blocker", "high", "medium")
    if lane == "methods_critic":
        return row.get("verdict") in ("overclaim", "unsupported")
    if lane == "cite":
        if row.get("cite_audit_verdict") == "no_citations_present":
            return False
        return (
            row.get("independent_resolves") is False
            or row.get("independent_title_match") is False
            or row.get("independent_supports_surrounding_claim") is False
        )
    if lane == "figure":
        return row.get("agreement") != "all_three_agree"
    return False


def test_bug_audit_bijection() -> None:
    audit = _read_jsonl(AUDIT_ROWS)
    bugs = _read_jsonl(BUG_REPORTS)
    audit_ids = {row["finding_id"] for row in audit if _is_bug_row(row)}
    bug_ids = {b["finding_id"] for b in bugs}
    # Cite rows may yield multiple bugs (one citation, multiple failures) —
    # but in this audit cite has zero failures, so the sets must match.
    only_in_audit = audit_ids - bug_ids
    only_in_bugs = bug_ids - audit_ids
    assert not only_in_audit, f"audit rows missing from bug-reports: {only_in_audit}"
    assert not only_in_bugs, f"bug-reports references unknown finding_ids: {only_in_bugs}"


# ---------------------------------------------------------------------------
# Test 7 — severity, failure_mode, producing_role
# ---------------------------------------------------------------------------


def test_severity_enum() -> None:
    bugs = _read_jsonl(BUG_REPORTS)
    for b in bugs:
        assert b["severity"] in SEVERITY_ENUM, (
            f"bug {b['id']} severity invalid: {b['severity']!r}"
        )


def test_failure_mode_enum() -> None:
    bugs = _read_jsonl(BUG_REPORTS)
    for b in bugs:
        assert b["failure_mode"] in FAILURE_MODE_ENUM, (
            f"bug {b['id']} failure_mode invalid: {b['failure_mode']!r}"
        )


def test_producing_role_resolved() -> None:
    bugs = _read_jsonl(BUG_REPORTS)
    for b in bugs:
        pr = b.get("producing_role", "")
        assert isinstance(pr, str) and pr.strip(), (
            f"bug {b['id']} producing_role empty"
        )


# ---------------------------------------------------------------------------
# Test 8 — clusters partition (sum to total bug count)
# ---------------------------------------------------------------------------


CLUSTER_TABLE_ROW_RE = re.compile(
    r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*`([^`]+)`\s*\|\s*(\d+)\s*\|$",
    re.MULTILINE,
)


def test_clusters_partition() -> None:
    bugs = _read_jsonl(BUG_REPORTS)
    sec6 = _section(_deliverable_text(), 6)
    matches = CLUSTER_TABLE_ROW_RE.findall(sec6)
    assert matches, "no cluster table rows found in section 6"
    total_in_table = sum(int(c) for *_, c in matches)
    assert total_in_table == len(bugs), (
        f"cluster table sum {total_in_table} != total bugs {len(bugs)}"
    )


# ---------------------------------------------------------------------------
# Test 9 — prompt-ambiguity ceiling
# ---------------------------------------------------------------------------


def test_prompt_ambiguity_ceiling() -> None:
    bugs = _read_jsonl(BUG_REPORTS)
    pa = sum(1 for b in bugs if b["failure_mode"] == "prompt-ambiguity")
    total = len(bugs)
    if total == 0:
        return
    if pa / total > 0.20:
        sec6 = _section(_deliverable_text(), 6)
        assert "human review required" in sec6.lower(), (
            f"prompt-ambiguity is {pa}/{total} > 20% but section 6 lacks "
            "'human review required' marker"
        )


# ---------------------------------------------------------------------------
# Test 10 — top 3 clusters have hypotheses
# ---------------------------------------------------------------------------


def test_top_clusters_have_hypotheses() -> None:
    text = _deliverable_text()
    sec6 = _section(text, 6)
    # Find each "Cluster N — `(...)` ×" prose paragraph
    cluster_prose_re = re.compile(
        r"\*\*Cluster\s+\d+\s+—\s+`\([^)]+\)`\s+×\s+\d+\.\*\*\s+(.+?)(?=\n\n|\*\*Cluster\s+\d+|\Z)",
        re.DOTALL,
    )
    prose_blocks = cluster_prose_re.findall(sec6)
    assert len(prose_blocks) >= 3, (
        f"expected ≥3 cluster prose blocks in section 6, found {len(prose_blocks)}"
    )
    for i, block in enumerate(prose_blocks[:3], 1):
        # ≥3 sentences (split on `. ` and require 3+ non-empty pieces)
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", block.strip()) if s.strip()]
        assert len(sentences) >= 3, (
            f"cluster {i} prose has only {len(sentences)} sentence(s); need ≥3"
        )
        # backticked code path containing `/`
        has_code_path = bool(re.search(r"`[^`]*/[^`]*`", block))
        assert has_code_path, (
            f"cluster {i} prose lacks a backticked code path containing '/'"
        )


# ---------------------------------------------------------------------------
# Test 11 — ground-truth quoted
# ---------------------------------------------------------------------------


def test_ground_truth_quoted() -> None:
    gt = GROUND_TRUTH.read_text(encoding="utf-8")
    m = re.search(
        r"^##\s*Headline finding\s*\n+(.+?)(?=\n##|\Z)",
        gt,
        re.MULTILINE | re.DOTALL,
    )
    assert m, "ground-truth-fig4.md missing '## Headline finding' section"
    headline = m.group(1).strip()
    assert headline, "headline finding section is empty"
    # Pick a contiguous ≥30-char substring (after stripping markdown noise)
    # — search for any 30+ char prefix of any sentence.
    # The deliverable is expected to embed the first paragraph verbatim.
    sec7 = _section(_deliverable_text(), 7)
    # The deliverable formats headline as a blockquote with "> " prefix per line.
    # Strip those prefixes from sec7 before substring search.
    sec7_unquoted = re.sub(r"^>\s?", "", sec7, flags=re.MULTILINE)
    # Try the first 30 chars of the first paragraph
    first_para = headline.split("\n\n")[0].strip()
    snippet = first_para[:30] if len(first_para) >= 30 else first_para
    assert len(snippet) >= 30, (
        f"headline first paragraph too short to test ({len(snippet)} chars)"
    )
    assert snippet in sec7_unquoted, (
        f"section 7 does not contain a verbatim ≥30-char substring of the "
        f"headline finding (looked for {snippet!r})"
    )
