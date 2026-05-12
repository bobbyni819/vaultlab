---
name: audit-html
description: Render any vaultlab audit result as an HTML report. Supports deck audits (rigor_audit), lit-arc narratives, reasoning-chain transcripts (CrosstalkResult), citation audits, and project dossiers. Pick the consumer that matches your input; emit single-file HTML.
arguments: <input-path> [--kind deck|litarc|reasoning|citation|dossier] [--out <path>]
---

# /audit-html <input-path>

> *"Turn whatever audit / arc / dossier you just ran into a browser-
> openable HTML you can read on phone, share as one file, or print."*

Universal dispatcher for vaultlab's HTML consumers:

| `--kind` | Renderer | Input shape |
|---|---|---|
| `deck` | `vaultlab.slides.audit_html` | `{plan, audit}` dict or two files |
| `litarc` | `vaultlab.research.litarc_html` | `{topic, narrative, papers, ...}` |
| `reasoning` | `vaultlab.workflows.reasoning_html` | `CrosstalkResult` (dict or dataclass) |
| `citation` | `vaultlab.citations.report_html` | `AuditReport` (dict or dataclass) |
| `dossier` | `vaultlab.kb.dossier_html` | `Dossier` (dict or dataclass) |

If `--kind` is omitted, the dispatcher inspects the input shape:

- Has `slides` + `passed` → `deck`
- Has `narrative` + `papers` → `litarc`
- Has `rounds` + `final_output` → `reasoning`
- Has `citations` + `by_status` → `citation`
- Has `project_slug` + `sections` → `dossier`

## Pre-flight

1. Read input (JSON or YAML)
2. Detect kind (or use `--kind`)
3. Resolve `--out` (default: same dir, `.html` suffix)

## Execution

```python
import json
from pathlib import Path

data = json.loads(Path("<input-path>").read_text(encoding="utf-8"))
kind = "<kind>" or _detect_kind(data)

if kind == "deck":
    from vaultlab.slides.audit_html import write_audit_report
    write_audit_report("<out>", data["plan"], data["audit"])
elif kind == "litarc":
    from vaultlab.research.litarc_html import write_litarc_report
    write_litarc_report("<out>", **data)
elif kind == "reasoning":
    from vaultlab.workflows.reasoning_html import write_reasoning_report
    write_reasoning_report("<out>", data)
elif kind == "citation":
    from vaultlab.citations.report_html import write_citation_audit_html
    write_citation_audit_html("<out>", data)
elif kind == "dossier":
    from vaultlab.kb.dossier_html import write_dossier_report
    write_dossier_report("<out>", data)
else:
    raise ValueError(f"Unknown kind: {kind}")

print(f"wrote {out}")
print(f"to open: bobby-kb open {out}")
```

## When to use

- After running an audit / lit-arc / dossier compile, before opening the
  MD output. The HTML is faster to scan, mobile-friendly, and includes
  filters that the MD doesn't.
- Before sharing an artifact with a collaborator — one .html file
  archives cleanly and opens in any browser.

## Related

- `vaultlab.report` — the underlying HTML primitive (15 components)
- The 6 specific consumers (linked above)
- `Wiki/Concepts/html-output-system.md` — full concept article
