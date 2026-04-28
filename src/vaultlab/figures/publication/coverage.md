---
module: vaultlab.figures.publication.coverage
purpose: CoverageManifest dataclass for /figure-audit verdict integration
status: placeholder for P0.2 (full impl lands in commit 3)
---

# Coverage — CoverageManifest dataclass (P0.2 placeholder)

## What this provides (currently)

A minimal `CoverageManifest` dataclass that captures the spec from `figure-audit-capability-spec.md` §3.1. The fields are wired up but the JSON I/O, validation, and `/figure-audit` integration land in the P0.2 commit.

## Full spec (to land in P0.2)

```python
@dataclass
class CoverageManifest:
    figure_id: str
    script_path: str
    timestamp: str
    vaultlab_version: str

    regions_included: list[str]
    regions_excluded: list[str]
    donors_included: list[str]
    cell_types_included: list[str]
    cell_types_excluded: list[str]

    exclusions: list[str]
    exclusion_reasons: dict[str, str]
    exclusion_justifications: dict[str, str]   # NEW in P0.2 — proof for /figure-audit

    analysis_params: dict[str, Any]

    visual_audit: VisualAuditResult | None     # NEW (Rule 15)

    def to_json(self) -> dict: ...
    def to_footer_text(self) -> str: ...
    def verdict(self, auditor: CoverageAuditor) -> AuditVerdict: ...
```

Plus:

- `load_manifest(path)` — read sidecar
- `save_manifest(manifest, path)` — write sidecar
- `attach_to_figure(fig, manifest)` — add footer text to a matplotlib figure

## Why this is locked as a placeholder

P0 sequencing:
- P0.1 (this commit) — port figure helpers + provide CoverageManifest skeleton
- P0.2 (commit 3) — flesh out the dataclass with JSON I/O + footer integration
- P0.3 — wire `/figure-audit` slash command + `CoverageAuditor` role

## Invariants for the full impl (lock now, enforce in P0.2)

Per AGENTS.md (Figure-audit invariants 1-4):

1. Every figure script MUST emit a `CoverageManifest` sidecar
2. In-figure footer MUST read from the manifest (no hardcoding)
3. `CoverageAuditor` role MUST NOT fabricate — only report what's verifiable
4. `/research-figures` MUST gate on audit verdict (no silent reuse of `PARTIAL_UNJUSTIFIED`)

## See also

- `figure-audit-capability-spec.md` (in the KB) — the full spec
- `metabolism-patterns-to-lift-2026-04-22.md` — Pattern 3 + Pattern 5
- File 06 in the architecture grill — publication/ submodule rationale
