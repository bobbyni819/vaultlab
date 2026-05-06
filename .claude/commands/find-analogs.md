---
name: find-analogs
description: Find structural analogs of a concept across all KBs the user maintains. Cross-project pattern recognition. Lifts the multi-agent meeting pattern from virtual-lab (Swanson Nature 2025).
arguments: <concept-name-or-description>
---

# /find-analogs <concept>

> "In the metabolism project I noticed a phospholipid-sphingolipid axis. Has my equities project, my flu project, or my thesis project surfaced anything analogous?"

This command discovers structural analogs of a concept across **every KB the user maintains**, not just the current project. Output: a 1-page "Cross-project analogs of `<concept>`" doc with citations + `[[wikilinks]]` to each project's concept doc.

## Lineage

Lifts the multi-agent-meeting pattern (analyst → critic → synthesizer with bounded loops + structured-JSON-only output) from **virtual-lab** (Swanson et al., *Nature* 2025; Zou group, Stanford). The cross-project KB walk follows **Karpathy's LLM Wiki gist** — wiki grows with work, retrieval is keyword-anchored over the wiki itself.

## Pre-flight checklist (per READ_FIRST.md commitments #6 + #7)

1. Resolve KB root: `from vaultlab.context import resolve_kb_root` → `kb_root`
2. Read project state: `<kb_root>/<current-project>/START_HERE.md` + `decisions-log.md`
3. State-aware preflight: glob `<kb_root>/<current-project>/Output/cross-project-analog-*.md` — has the user already searched for this concept? If yes, mode `--query-existing` (read prior analog doc); if no, fresh search.

## Execution

### Step 1 — Concept normalization

Take the user's input string and produce a 1-2 sentence canonical description of the concept. Example:

```
Input:  "phospholipid-sphingolipid axis"
Canonical: "A dichotomy in lipid biology where phospholipid abundance and
            sphingolipid abundance vary inversely across cell types or
            tissue compartments, suggesting reciprocal metabolic
            specialization."
```

### Step 2 — Cross-KB scan

Glob ALL siblings under `kb_root.parent`:

```python
from pathlib import Path
vault_root = kb_root.parent
all_kbs = [p for p in vault_root.iterdir() if p.is_dir() and not p.name.startswith(".")]
all_concept_docs = []
for kb in all_kbs:
    concepts_dir = kb / "Wiki" / "Concepts"
    if concepts_dir.exists():
        all_concept_docs.extend(concepts_dir.glob("*.md"))
```

For each concept doc, read its frontmatter + first 200 words. **Batch all of them** into a single LLM call (per the batched-reader pattern from `vaultlab.research.batched_reader`) and ask: *"Which of these concept docs is structurally analogous to `<canonical>`? For each match, explain the structural analogy in 2-3 sentences."*

### Step 3 — Structured response

Expected output schema (Claude Code returns this as JSON, then we render to markdown):

```json
{
  "matches": [
    {
      "kb": "flu",
      "doc_path": "Wiki/Concepts/na-ha-receptor-binding-axis.md",
      "structural_analogy": "Like phospholipid-sphingolipid: NA and HA expression vary inversely across viral subtypes; reciprocal binding-domain specialization.",
      "evidence_excerpt": "...quote from the concept doc..."
    },
    {
      "kb": "metabolism",
      "doc_path": "Wiki/Concepts/lpi-gpr55-signaling.md",
      "structural_analogy": "Same dichotomy at a different scale — LPI receptor expression varies inversely with phosphoinositide metabolism.",
      "evidence_excerpt": "..."
    }
  ],
  "no_match_reasoning": "Equities and dcp KBs have no structural analog — they're financial/operational, not metabolic."
}
```

### Step 4 — Render output

Write to `<kb_root>/<current-project>/Output/cross-project-analog-<concept-slug>-<date>.md`:

```markdown
# Cross-project analogs of <concept>

Canonical description: <canonical>

## Matches found (N)

### 1. [[../../<kb>/Wiki/Concepts/<doc>|<concept-name>]] (KB: `<kb>`)

**Structural analogy:** <2-3 sentences>

**Evidence:** > <quoted excerpt>

[Full concept doc](../../<kb>/Wiki/Concepts/<doc>.md)

---

(repeat per match)

## KBs with no analog: <list>
<reasoning>
```

### Step 5 — Surface to user

Reply with: *"Found N analogs across <list of KBs with matches>. Top match: <name>. Full doc: `bobby-kb open ...`"*

## Outputs

- `<kb_root>/<current-project>/Output/cross-project-analog-<concept-slug>-<date>.md` (the analog doc)
- Provenance receipt: `<>.provenance.json` recording the concept-doc inventory + per-match rationale

## When NOT to invoke

- The user is asking about THIS project's concept (use `/research-status` instead — same-project query)
- The user gives a vague topic with no clear structure (ask them to refine first)

## Follow-up actions

After running, surface to the user: *"Want me to write a short briefing tying these analogs together?"* — that triggers a `plan_deep_think_round` over the analog matches.
