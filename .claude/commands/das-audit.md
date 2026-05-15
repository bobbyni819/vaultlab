---
name: das-audit
description: Audit a Data Availability Statement (DAS) for Nature-family / Cell / eLife submissions. Runs the FAIR checklist, checks repository identifiers, flags vague "reasonable request" without contact info, missing identifiers, unrestricted human data, and other common DAS failures.
arguments: <das-text-or-manuscript-path> [--scenario public_deposit|restricted_human|on_request|...] [--datasets <comma-separated-ids>]
---

# /das-audit <das-text-or-manuscript-path>

> *"Make every result-supporting dataset resolve to a citable accession with explicit access conditions — before the editor flags it."*

Drives `vaultlab.manuscript.data_availability`. Three checks:

1. **Heuristic auditor** — flags vague "reasonable request" without
   contact, human data without restriction clause, no persistent
   identifiers, unfalsifiable "all data available" with no destination.
2. **Repository identifier match** — for each provided dataset accession,
   validates the format against the registered repo regex (GEO, SRA,
   PRIDE, PDB, EMPIAR, EGA, dbGaP, Dryad, Zenodo, OSF, GitHub, +6 more).
3. **FAIR checklist** — 14 items across Findable / Accessible / Interoperable / Reusable.

## Pre-flight

1. Read the DAS text (either passed directly or extracted from a
   manuscript file's "Data Availability" section)
2. Resolve `--scenario` (defaults to `public_deposit`)
3. If `--datasets` given, parse the comma-separated identifiers

## Execution

### Step 1 — Heuristic auditor

```python
from vaultlab.manuscript.data_availability import (
    audit_statement, REPOSITORIES, FAIR_CHECKLIST,
    statement_template, DAScenario,
    write_data_availability_statement,
)

text = Path("<das-path>").read_text() if Path("<das-path>").exists() else "<das-text>"
findings = audit_statement(text)

# v0.0.5 one-call writer — writes the statement + audit findings as a
# markdown file with Red Line #2 provenance receipts. Use this when you
# want the audited DAS persisted (not just the in-memory findings list).
write_data_availability_statement(
    "das-statement.md",
    text,
    scenario=DAScenario.PUBLIC_DEPOSIT,  # or whatever --scenario resolved to
    inputs=["<das-path>"],
)
```

Findings come back as `StatementAuditFinding(severity, message)` —
`blocker` / `major` / `minor`.

### Step 2 — Validate provided dataset identifiers

```python
import re
if "<datasets>":
    for accession in "<datasets>".split(","):
        accession = accession.strip()
        matched = []
        for slug, repo in REPOSITORIES.items():
            if re.match(repo.identifier_format, accession):
                matched.append(slug)
        if not matched:
            print(f"WARNING: {accession} does not match any registered repo format")
        else:
            print(f"OK: {accession} matches {matched}")
```

### Step 3 — Suggest the template for the chosen scenario

```python
template = statement_template(DAScenario(scenario))
```

### Step 4 — FAIR self-assessment

Walk each of the 14 FAIR items. For each one, mark Y / N / TODO. Items
marked TODO get explicit guidance.

### Step 5 — Render as HTML audit

```python
from vaultlab.report import write_report
from vaultlab.report import components as c

sections = [
    c.tldr_box([
        f"{len(blockers)} blocker / {len(majors)} major / {len(minors)} minor",
        f"FAIR: {fair_pass}/14 pass; {len(todo)} TODO",
        f"Scenario: {scenario}",
    ]),
    c.section("Heuristic audit findings", ...),
    c.section("Repository identifier matches", ...),
    c.section("FAIR checklist", ...),
    c.section("Suggested DAS template", ...),
]
write_report("das-audit.html", title="DAS audit", sections=sections)
```

## Common findings + remediation

| Finding | Severity | Fix |
|---|---|---|
| "reasonable request" without contact | blocker | Add corresponding-author email or DAC contact |
| Human data without restriction clause | major | Move to controlled-access (EGA/dbGaP) or describe consent + anonymization |
| No persistent identifier | major | Deposit in mandated repo; add the accession |
| "All data available" without destination | minor | Name the supplementary file or repository |
| P-value or n missing for stats claim | minor | Include in DAS or point to statistical methods |
| No code archived | minor | Archive on GitHub + Zenodo DOI |

## Output package

- `das-audit.html` — interactive audit (filter by severity, click-to-fix actions)
- `das-audit.md` — plain markdown summary
- `das-revised.md` — suggested revised DAS prose using the appropriate scenario template

## Related

- `vaultlab.manuscript.data_availability` — underlying registry +
  checklist + auditor
- nature-data skill at `nature-skills/skills/nature-data/` — upstream
  source
- `/cite audit` — citation verification (often paired with DAS audit
  before submission)
