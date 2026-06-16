Inline citation watchdog for Phase 6 (research-write). Prevents hallucinated citations from being written by verifying each citation at the moment it is composed, before it reaches the manuscript draft.

This is NOT a separate phase or post-hoc audit. It runs WITHIN Phase 6 as an inline check on every citation, acting as a real-time gate that catches bad references before they exist in the text.

## How It Integrates with /research-write

During Phase 6 (Step 3b: "Draft the text"), every time a citation is about to be written into a manuscript section, run the cite-watch check BEFORE committing the text. This means:

1. The writing agent composes a sentence with a citation
2. BEFORE writing that sentence to the output file, run cite-watch
3. Only write the sentence if the citation passes
4. If it fails, fix it inline (find alternative or remove citation) before continuing

## Cite-Watch Check (per citation)

```python
from bobby_research import ResearchClient
import json, os

client = ResearchClient()

def cite_watch(doi, claim_text, kb_dir):
    """
    Returns (pass: bool, reason: str, suggestion: str or None)
    """
    # Step 1: Check evidence index (fast path)
    evidence_index_path = os.path.join(kb_dir, "Sources", ".evidence_index.json")
    if os.path.exists(evidence_index_path):
        with open(evidence_index_path) as f:
            evidence = json.load(f)
        if doi in evidence:
            return (True, "DOI in evidence index (pre-verified by /cite audit)", None)

    # Step 2: Verify paper exists
    result = client.verify_exists(doi)
    if not result or not result.found:
        return (False, f"Paper not found: {doi}", "FIND_ALTERNATIVE")

    # Step 3: Check claim alignment (lightweight)
    # Compare the claim text against the paper's title/abstract
    # This is a quick heuristic, not a full /cite audit
    if result.title and result.abstract:
        # Flag obvious mismatches (wrong topic, wrong organism, etc.)
        # but don't block on subtle mismatches — those are for Phase 7 review
        pass

    return (True, f"Paper exists: {result.title} ({result.year})", None)
```

## Decision Tree

For every citation written during Phase 6:

```
1. Extract DOI from the citation being written
   |
2. Is this DOI in Sources/.evidence_index.json?
   |-- YES --> PASS (skip verification, already audited by /cite audit)
   |-- NO --> continue to step 3
   |
3. Run bobby_research.verify_exists(doi)
   |-- Paper found --> PASS (note: will be fully audited in Phase 7)
   |-- Paper NOT found --> FAIL --> step 4
   |
4. CITATION BLOCKED:
   a. Log: "BLOCKED: {doi} not found — cannot cite"
   b. Ask the writing agent to find an alternative:
      - Search for a real paper that supports the same claim
      - Use bobby_research.search() with the claim text as query
      - If a verified paper is found, substitute it
      - If no paper found, rewrite the sentence without a citation
         (use "evidence suggests" or similar hedging, and flag for Bobby)
   c. Continue writing with the fix applied
   |
5. After Phase 6 completes, produce a cite-watch summary:
   - Total citations written: N
   - Pre-verified (in evidence index): M
   - Verified inline: K
   - Blocked and replaced: J
   - Blocked and removed: L
   - Flagged for Phase 7 review: P (papers found but claim match uncertain)
```

## Output

Cite-watch does NOT produce its own output file. Instead, it:

1. **Annotates the manuscript section frontmatter** (already written by /research-write):
   ```yaml
   citations_verified: 12        # pre-verified via evidence index
   citations_inline_verified: 3  # verified by cite-watch during writing
   citations_blocked: 1          # blocked and replaced/removed
   citations_flagged: 2          # exist but claim match needs Phase 7 review
   ```

2. **Adds a cite-watch log** at the bottom of the Phase 6 pipeline summary (`pipeline-phase-6-write.md`):
   ```markdown
   ## Cite-Watch Log
   - [PASS] 10.1083/jcb.200407073 — in evidence index
   - [PASS] 10.1016/j.cell.2023.01.002 — verified inline (exists)
   - [BLOCKED] 10.9999/fake.2024.001 — not found, replaced with 10.1016/j.cell.2022.08.015
   - [FLAGGED] 10.1038/s41586-023-06112-2 — exists but claim match uncertain
   ```

## Rules

- NEVER skip cite-watch — every citation in Phase 6 must pass through it
- NEVER write a citation that fails verification — block and fix inline
- NEVER silently remove a citation — log every block with the reason
- Prefer substitution (find a real paper) over removal (rewrite without citation)
- When substituting, verify the replacement paper also supports the claim
- Do NOT run a full /cite audit here — that is Phase 5's job. Cite-watch is a fast guard rail
- If the evidence index does not exist (Phase 5 was skipped), verify ALL citations inline
- Cite-watch adds ~1-2 seconds per citation — this is acceptable for manuscript quality

## What Cite-Watch Does NOT Do

- Does NOT replace `/cite audit` (Phase 5) — that is a thorough, deep audit with claim matching
- Does NOT replace Phase 7 review — flagged citations still need human review
- Does NOT verify claim-paper alignment in depth — it only checks that the paper exists
- Does NOT modify the evidence index — it only reads from it
- Does NOT run as a standalone command — it is a hook within `/research-write`
