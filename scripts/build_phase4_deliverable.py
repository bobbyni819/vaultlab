"""Phase-4 deliverable builder.

Reads:
    <kb>/elife-91157-stress/Output/run-2026-05-26/audit-rows.jsonl
    <kb>/elife-91157-stress/Output/run-2026-05-26/rubric-scores.json
    <kb>/elife-91157-stress/Output/run-2026-05-26/run-manifest.json
    <kb>/elife-91157-stress/ground-truth-fig4.md

Writes:
    <kb>/elife-91157-stress/Output/run-2026-05-26/bug-reports.jsonl
    <kb>/elife-91157-stress/Output/vaultlab-stress-test-2026-05-26.md

Deterministic. Pure stdlib + pathlib. No LLM, no network, no subprocess.

Run:
    /opt/anaconda3/bin/python scripts/build_phase4_deliverable.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

KB = Path("/Users/arnav/vaultlab-kb/elife-91157-stress")
RUN = KB / "Output" / "run-2026-05-26"
AUDIT_ROWS = RUN / "audit-rows.jsonl"
RUBRIC = RUN / "rubric-scores.json"
MANIFEST = RUN / "run-manifest.json"
GROUND_TRUTH = KB / "ground-truth-fig4.md"
BUG_REPORTS = RUN / "bug-reports.jsonl"
DELIVERABLE = KB / "Output" / "vaultlab-stress-test-2026-05-26.md"


# ---------------------------------------------------------------------------
# Bug derivation
# ---------------------------------------------------------------------------


SEVERITY_BY_LANE: dict[str, dict[str, str]] = {
    # Lane A: blocker→critical (locked decision), high→major, medium→minor
    "rigor": {"blocker": "critical", "high": "major", "medium": "minor"},
}

FAILURE_MODE_BY_RULE: dict[str, str] = {
    # Lane A rule_violated → failure_mode
    "claim_grounding": "provenance-break",
    "reference_completeness": "provenance-break",
    "page_marker_integrity": "provenance-break",
    "claim_vs_evidence_calibration": "hallucination",
}

SUGGESTED_FIX_BY_SUBCLUSTER: dict[str, str] = {
    "figure_silent_no_conclusion": (
        "Have run_pipeline call a per-figure interpretation primitive (or "
        "add hedge-tagged template prose) so each figure carries a conclusion."
    ),
    "claim_grounding": (
        "compose_methods_paragraph should emit hedge tokens for every "
        "comparative claim, or rigor_auditor should waive grounding for "
        "template-only producers."
    ),
    "reference_completeness": (
        "Emit a (possibly empty) References section so orphan-reference "
        "auditing has a real target."
    ),
    "page_marker_integrity": (
        "Strip or guard [pN] markers from the template — they don't apply "
        "to LLM-free output."
    ),
    "claim_vs_evidence_calibration": (
        "Tone down absolute language in the methods template; pair every "
        "directional claim with a hedge marker."
    ),
}


def _read_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def _producer_for_artifact(manifest: list[dict], artifact: str) -> str:
    for e in manifest:
        if e.get("path") == artifact:
            return e.get("producer", "")
    # Path-normalize fallback: search by basename match
    base = artifact.rsplit("/", 1)[-1]
    for e in manifest:
        if e.get("path", "").endswith("/" + base):
            return e.get("producer", "")
    return "run-analysis"  # documented default


def _classify_rigor(row: dict) -> tuple[str, str, str]:
    """Return (severity, failure_mode, sub_cluster) for a Lane A row."""
    sev = SEVERITY_BY_LANE["rigor"].get(row["severity"], "minor")
    rule = row.get("rule_violated", "")
    fm = FAILURE_MODE_BY_RULE.get(rule, "provenance-break")
    return sev, fm, rule or "claim_grounding"


def _classify_figure(row: dict) -> tuple[str, str, str]:
    """Return (severity, failure_mode, sub_cluster) for a Lane D row."""
    agr = row.get("agreement", "")
    if agr in ("vaultlab_disagrees_with_data", "all_three_disagree"):
        return "critical", "provenance-break", "figure_disagrees_with_data"
    if agr == "paper_disagrees_with_data":
        return "critical", "provenance-break", "paper_disagrees_with_data"
    if agr in ("vaultlab_disagrees_with_paper",):
        return "major", "provenance-break", "figure_disagrees_with_paper"
    if agr.startswith("vaultlab_silent_"):
        # All silent rows count as critical (contribute to conclusion_match=no)
        return "critical", "provenance-break", "figure_silent_no_conclusion"
    return "major", "provenance-break", "figure_other_disagreement"


def _classify_cite(row: dict) -> list[tuple[str, str, str, str]]:
    """Return list of (failure_label, severity, failure_mode, sub_cluster) — one citation row may yield multiple bugs."""
    out: list[tuple[str, str, str, str]] = []
    if row.get("independent_title_match") is False:
        out.append(("wrong_paper", "critical", "hallucination", "cite_wrong_paper"))
    if row.get("independent_resolves") is False:
        out.append(("unresolved", "major", "retrieval", "cite_unresolved"))
    if row.get("independent_supports_surrounding_claim") is False:
        out.append(("claim_unsupported", "minor", "hallucination", "cite_claim_unsupported"))
    return out


def derive_bugs(audit_rows: list[dict], manifest: list[dict]) -> list[dict]:
    bugs: list[dict] = []
    for row in audit_rows:
        lane = row["lane"]
        if lane == "rigor":
            if row.get("severity") not in ("blocker", "high", "medium"):
                continue
            if row.get("issue") == "no_rigor_issues_detected":
                continue
            sev, fm, sub = _classify_rigor(row)
            bugs.append(
                {
                    "lane": "rigor",
                    "finding_id": row["finding_id"],
                    "artifact": row["artifact"],
                    "what_failed": row.get("issue", ""),
                    "severity": sev,
                    "failure_mode": fm,
                    "sub_cluster": sub,
                    "producing_role": _producer_for_artifact(manifest, row["artifact"]),
                    "suggested_fix": SUGGESTED_FIX_BY_SUBCLUSTER.get(
                        sub, "Review the audit finding and tighten the rule."
                    ),
                    "quote": row.get("quote", ""),
                }
            )
        elif lane == "methods_critic":
            if row.get("verdict") not in ("overclaim", "unsupported"):
                continue
            sev = "critical" if row["verdict"] == "unsupported" else "major"
            bugs.append(
                {
                    "lane": "methods_critic",
                    "finding_id": row["finding_id"],
                    "artifact": row["artifact"],
                    "what_failed": row["verdict"],
                    "severity": sev,
                    "failure_mode": "hallucination",
                    "sub_cluster": f"mc_{row['verdict']}",
                    "producing_role": _producer_for_artifact(manifest, row["artifact"]),
                    "suggested_fix": SUGGESTED_FIX_BY_SUBCLUSTER.get(
                        f"mc_{row['verdict']}",
                        "Have a methods_critic round on every synthesis before shipping.",
                    ),
                    "quote": row.get("claim_quote", ""),
                }
            )
        elif lane == "cite":
            if row.get("cite_audit_verdict") == "no_citations_present":
                continue
            for label, sev, fm, sub in _classify_cite(row):
                bugs.append(
                    {
                        "lane": "cite",
                        "finding_id": row["finding_id"],
                        "artifact": row["artifact"],
                        "what_failed": label,
                        "severity": sev,
                        "failure_mode": fm,
                        "sub_cluster": sub,
                        "producing_role": _producer_for_artifact(manifest, row["artifact"]),
                        "suggested_fix": SUGGESTED_FIX_BY_SUBCLUSTER.get(
                            sub, "Tighten citation verification + lookup."
                        ),
                        "quote": row.get("evidence_quote", ""),
                    }
                )
        elif lane == "figure":
            if row.get("agreement") == "all_three_agree":
                continue
            sev, fm, sub = _classify_figure(row)
            bugs.append(
                {
                    "lane": "figure",
                    "finding_id": row["finding_id"],
                    "artifact": row["artifact"],
                    "what_failed": row.get("agreement", ""),
                    "severity": sev,
                    "failure_mode": fm,
                    "sub_cluster": sub,
                    "producing_role": _producer_for_artifact(manifest, row["artifact"]),
                    "suggested_fix": SUGGESTED_FIX_BY_SUBCLUSTER.get(
                        sub,
                        "Have run_pipeline call a per-figure interpretation primitive.",
                    ),
                    "quote": row.get("ground_truth_quote", ""),
                }
            )

    # Stable sort and assign IDs
    bugs.sort(key=lambda b: (b["lane"], b["finding_id"], b.get("what_failed", "")))
    for i, b in enumerate(bugs, 1):
        b["id"] = f"B{i:03d}"
    # Reorder keys for readability
    out: list[dict] = []
    for b in bugs:
        out.append(
            OrderedDict(
                [
                    ("id", b["id"]),
                    ("lane", b["lane"]),
                    ("finding_id", b["finding_id"]),
                    ("artifact", b["artifact"]),
                    ("what_failed", b["what_failed"]),
                    ("severity", b["severity"]),
                    ("failure_mode", b["failure_mode"]),
                    ("sub_cluster", b["sub_cluster"]),
                    ("producing_role", b["producing_role"]),
                    ("suggested_fix", b["suggested_fix"]),
                    ("quote", b["quote"]),
                ]
            )
        )
    return out


# ---------------------------------------------------------------------------
# Deliverable rendering
# ---------------------------------------------------------------------------


CLUSTER_PROSE: dict[str, str] = {
    "figure_silent_no_conclusion": (
        "`vaultlab.analysis.pipeline.run_pipeline` emits one figure PNG per "
        "`figures_config` entry plus a stats sidecar, then calls "
        "`compose_methods_paragraph` to draft the methods doc. That helper "
        "is template-only by design — the docstring at `src/vaultlab/analysis/methods.py` "
        "states *Template-based (no LLM call in this iteration per the SPEC-A brief).* "
        "No per-figure interpretation is ever authored, so Lane D has no "
        "vaultlab conclusion to compare against the paper, and `conclusion_match` "
        "collapses to `no`. **Code paths to inspect:** "
        "`src/vaultlab/analysis/methods.py:compose_methods_paragraph`, "
        "`src/vaultlab/analysis/pipeline.py:run_pipeline` (the loop that renders each figure but never invokes an interpretation primitive). "
        "**Fix direction:** invoke a synthesizer role (e.g. `src/vaultlab/roles/synthesizer/`) "
        "per figure with the stats summary + figure path, or have the methods "
        "template emit hedge-tagged comparative prose with a banner that flags it as template-only — interpretation pending."
    ),
    "claim_grounding": (
        "`rigor_auditor` (task 1 in `src/vaultlab/roles/rigor_auditor/prompt.md`) "
        "requires `[[<doi-slug>|...]]` wikilinks on every claim of the form "
        "*X showed Y*. `compose_methods_paragraph` has no input channel for "
        "literature — it never sees `Wiki/Summaries/` — so even non-controversial "
        "descriptive sentences (e.g. *the pipeline consumes tidy result tables*) "
        "get flagged as ungrounded. **Code paths to inspect:** "
        "`src/vaultlab/analysis/methods.py:compose_methods_paragraph`, "
        "`src/vaultlab/roles/rigor_auditor/prompt.md` (the grounding rule). "
        "**Fix direction:** either feed the methods composer a `Wiki/Summaries/` "
        "index so it can emit wikilinks where supported, or change rigor_auditor's "
        "contract to detect `provenance.json.producer == \"template-only\"` "
        "and waive task-1 grounding for those documents (replacing it with a softer hedge-tag requirement)."
    ),
    "reference_completeness": (
        "rigor_auditor task 3 expects a References / bibliography section so it "
        "can flag orphan references and body claims whose wikilink targets do "
        "not exist. The methods template emits no References section at all, "
        "so the rule fires at the document level (no section to validate). "
        "**Code paths to inspect:** "
        "`src/vaultlab/analysis/methods.py:compose_methods_paragraph` (no References emission), "
        "`src/vaultlab/roles/rigor_auditor/prompt.md` task 3. "
        "**Fix direction:** emit an explicit (possibly empty) References section "
        "in the template so the audit can confirm *intentionally empty*, and "
        "have rigor_auditor downgrade missing-references from blocker to medium "
        "when the producer field marks the doc as template-only."
    ),
}


def _extract_headline_finding(text: str) -> str:
    m = re.search(
        r"^##\s*Headline finding\s*\n+(.+?)(?=\n##|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not m:
        return ""
    return m.group(1).strip()


def render_deliverable(
    audit_rows: list[dict],
    rubric: dict,
    manifest: list[dict],
    bugs: list[dict],
    ground_truth_text: str,
) -> str:
    headline = _extract_headline_finding(ground_truth_text)
    # Take the first paragraph as the verbatim quote
    headline_first_para = headline.split("\n\n")[0].strip() if headline else ""

    # Section 1 verdict + evidence
    cm = rubric["conclusion_match"]
    cm_verdict = cm["verdict"]
    evidence = cm["evidence"]
    evidence_str = ", ".join(f"[{e}]" for e in evidence)

    # Per-lane info
    per_lane = rubric["per_lane"]
    rigor = per_lane["rigor"]
    mc = per_lane["methods_critic"]
    cite = per_lane["cite"]
    figure = per_lane["figure"]

    # Failure-mode aggregation: producing_role × failure_mode × sub_cluster
    cluster_counts = Counter(
        (b["producing_role"], b["failure_mode"], b["sub_cluster"]) for b in bugs
    )
    cluster_rows = sorted(
        cluster_counts.items(), key=lambda kv: (-kv[1], kv[0])
    )
    top3 = [k for k, _ in cluster_rows[:3]]
    total_bugs = len(bugs)
    pa_count = sum(1 for b in bugs if b["failure_mode"] == "prompt-ambiguity")
    pa_over_ceiling = total_bugs > 0 and (pa_count / total_bugs) > 0.20

    # Build the markdown
    lines: list[str] = []
    lines.append("# vaultlab stress test — eLife 91157 Figure 4 — 2026-05-26")
    lines.append("")
    # Section 1
    lines.append("## 1. Did vaultlab arrive at the same conclusion the paper does?")
    lines.append("")
    lines.append(f"**Verdict: {cm_verdict}**")
    lines.append("")
    lines.append(
        f"For all 9 Figure-4 panels {evidence_str}, vaultlab authored no "
        "interpretive conclusion — the `/run-analysis` pipeline produces a "
        "template methods.md (descriptive stats per CSV) and rendered figure "
        "PNGs, but never states a direction, magnitude, or significance for any "
        "panel. The paper's headline finding is supported by an independent "
        "Welch's t-test recompute on the source data (recomputed direction "
        "matched the paper's claim in every panel where the paper made a "
        "directional statement). Because vaultlab made no statement at all, "
        "the user's rule — *no = vaultlab concluded null where the paper "
        "concluded an effect* — fires. This is a structural template limitation, "
        "not a numerical disagreement; see section 6, cluster 1."
    )
    lines.append("")

    # Section 2
    lines.append("## 2. Per-audit-lane results")
    lines.append("")
    lines.append("| Lane | Verdict | High/Fail | Medium/Warn | Notes |")
    lines.append("|---|---|---|---|---|")
    lines.append(
        f"| rigor_auditor | {rigor['verdict']} | {rigor['high']} (incl. "
        f"{rigor['blocker']} blocker) | {rigor['medium']} | "
        f"{'structural gap (no findings)' if rigor['structural_gap'] else 'real findings — see section 6'} |"
    )
    lines.append(
        f"| methods_critic | {mc['verdict']} | {mc['unsupported']} | "
        f"{mc['overclaim']} | "
        f"{'structural gap — see section 6' if mc['structural_gap'] else 'real claims evaluated'} |"
    )
    lines.append(
        f"| cite_audit | {cite['verdict']} | "
        f"{cite['unresolved'] + cite['wrong_paper']} | "
        f"{cite['claim_unsupported']} | "
        f"{'structural gap — see section 6' if cite['structural_gap'] else 'real citations evaluated'} |"
    )
    lines.append(
        f"| figure faithfulness | {figure['verdict']} | "
        f"{figure['disagree_with_data']} | "
        f"{figure['disagree_with_paper']} | "
        f"{'structural gap — see section 6' if figure['structural_gap'] else 'real conclusions evaluated'} |"
    )
    lines.append("")
    lines.append("**Failure-mode bullets per non-pass lane:**")
    lines.append("")
    lines.append(
        f"- **rigor_auditor**: {rigor['high']} high+blocker / {rigor['medium']} medium findings against methods.md — the template emits ungrounded claims, lacks a References section, and contains stray `[pN]` page markers from the role-prompt grammar."
    )
    if not mc["structural_gap"]:
        lines.append("- **methods_critic**: real claims flagged — see Section 3.")
    else:
        lines.append("- **methods_critic**: structural gap — no novelty/ranking/comparative claims to evaluate (template-only methods.md).")
    if not cite["structural_gap"]:
        lines.append("- **cite_audit**: real citation failures — see Section 4.")
    else:
        lines.append("- **cite_audit**: structural gap — zero citations in the run output (template-only methods.md).")
    if not figure["structural_gap"]:
        lines.append("- **figure faithfulness**: real disagreements — see Section 5.")
    else:
        lines.append("- **figure faithfulness**: structural gap — vaultlab authored no per-figure conclusion to compare against; see cluster 1 in section 6.")
    lines.append("")

    # Section 3 — overclaims
    lines.append("## 3. Overclaims (unhedged comparisons)")
    lines.append("")
    overclaims = rubric.get("overclaim_instances", [])
    if not overclaims:
        lines.append("None detected.")
    else:
        for o in overclaims:
            lines.append(
                f"- **{o['artifact']}** — *{o['quote']}* — {o['why_overclaim']}"
            )
    lines.append("")

    # Section 4 — citation failures
    lines.append("## 4. Citation failures")
    lines.append("")
    cit_fails = rubric.get("citation_failures", [])
    if not cit_fails:
        lines.append("None detected.")
    else:
        for c in cit_fails:
            lines.append(
                f"- **{c['citation_id']}** ({c['failure']}) — {c['artifact']} — quote: *{c['quote']}*"
            )
    lines.append("")

    # Section 5 — figure ↔ methods mismatches
    lines.append("## 5. Figure ↔ methods disagreements")
    lines.append("")
    mismatches = rubric.get("figure_methods_mismatches", [])
    if not mismatches:
        lines.append("None detected.")
    else:
        for m in mismatches:
            lines.append(
                f"- **{m['figure']}** ({m['type']}) — figure: *{m['figure_claim']}* "
                f"vs methods: *{m['methods_claim']}*"
            )
    lines.append("")

    # Section 6 — failure-mode clusters
    lines.append("## 6. Failure-mode clusters (actionable)")
    lines.append("")
    lines.append("| producing_role | failure_mode | sub_cluster | count |")
    lines.append("|---|---|---|---|")
    for (role, fm, sub), cnt in cluster_rows:
        lines.append(f"| {role} | {fm} | `{sub}` | {cnt} |")
    lines.append("")
    if pa_over_ceiling:
        lines.append(
            "> ⚠️ prompt-ambiguity bugs exceed 20% of total — **human review required**."
        )
        lines.append("")
    # Top 3 hypotheses
    if top3:
        lines.append("### Top-3 cluster root-cause hypotheses")
        lines.append("")
        for i, key in enumerate(top3, 1):
            role, fm, sub = key
            prose = CLUSTER_PROSE.get(sub, (
                f"Cluster `{sub}` aggregates {cluster_counts[key]} bug(s) under "
                f"({role}, {fm}). Root cause needs hand-review. "
                f"Code path: `src/vaultlab/`."
            ))
            lines.append(f"**Cluster {i} — `({role}, {fm}, {sub})` × {cluster_counts[key]}.** {prose}")
            lines.append("")

    # Section 7 — ground truth reference
    lines.append("## 7. Ground-truth reference")
    lines.append("")
    lines.append(
        f"Independent ground truth extracted from the paper PDF in Phase 1 — "
        f"see [ground-truth-fig4.md](../ground-truth-fig4.md). The headline "
        f"finding, verbatim:"
    )
    lines.append("")
    lines.append("> " + headline_first_para.replace("\n", "\n> "))
    lines.append("")

    # Section 8 — reproducer
    lines.append("## 8. Reproducer")
    lines.append("")
    lines.append("- Phase 1 artifacts: `Output/run-2026-05-26/`")
    lines.append("- Audit rows: `Output/run-2026-05-26/audit-rows.jsonl`")
    lines.append("- Rubric: `Output/run-2026-05-26/rubric-scores.json`")
    lines.append("- Bug list: `Output/run-2026-05-26/bug-reports.jsonl`")
    lines.append("- All QA tests: `tests/test_phase{1,2,3,4}.py`")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    audit_rows = _read_jsonl(AUDIT_ROWS)
    rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ground_truth_text = GROUND_TRUTH.read_text(encoding="utf-8")

    bugs = derive_bugs(audit_rows, manifest)
    with BUG_REPORTS.open("w", encoding="utf-8") as f:
        for b in bugs:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")

    md = render_deliverable(audit_rows, rubric, manifest, bugs, ground_truth_text)
    DELIVERABLE.write_text(md, encoding="utf-8")

    # Summary to stdout
    sev = Counter(b["severity"] for b in bugs)
    fm = Counter(b["failure_mode"] for b in bugs)
    print(f"bugs: {len(bugs)} -> {BUG_REPORTS}")
    print(f"  severities: {dict(sev)}")
    print(f"  failure_modes: {dict(fm)}")
    print(f"deliverable: {DELIVERABLE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
