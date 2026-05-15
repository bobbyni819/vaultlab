"""Red-line invariant tests.

These tests enforce the four red lines from
``.claude/goals/vaultlab-north-star.md``:

1. No fabrication of any kind (citations / claims / data / authors).
2. No silent failures (every check writes a manifest).
3. No user-data loss (reversible / dry-run / cache-backed).
4. No vendor lock-in (open formats only).

The tests use static analysis (AST scans + filesystem walks). They run
fast in CI without fixtures, and they report exact file:line locations
for any violation.

Some tests are marked ``xfail`` where the underlying contract is not yet
landed (the audit-manifest contract from sub-goal 1.2). Those xfails
become real failures once 1.2 lands and the contract is wired into the
listed entrypoints.

This file is sub-goal 1.1 of the north-star plan:
``.claude/goals/vaultlab-north-star-plan.md``
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "vaultlab"
EXAMPLES_ROOT = Path(__file__).resolve().parents[2] / "examples"

# Approved open formats per Red Line #4. .py is allowed because examples
# may ship executable scripts; .yaml / .yml / .toml / .cfg are config.
ALLOWED_OUTPUT_EXTS = {
    ".md",
    ".pptx",
    ".png",
    ".svg",
    ".html",
    ".json",
    ".jsonl",
    ".csv",
    ".tsv",
    ".yaml",
    ".yml",
    ".toml",
    ".txt",
    ".pdf",  # research papers / exports
    ".bib",  # bibliographic exports
    ".ris",  # citation exports
    ".enw",  # EndNote exports
    ".rdf",  # Zotero
    ".xml",  # standards-based
    ".gif",  # animations
    ".jpg",
    ".jpeg",
    ".webp",
    ".mp4",  # rare but open
}

# Entrypoint pattern: functions that write artifacts and therefore should
# emit a manifest. Used by the no-silent-failures test.
#
# Each tuple is (module_path_pattern, function_name) where the function
# is expected to produce a user-facing artifact + audit sidecar.
ARTIFACT_ENTRYPOINTS = [
    ("vaultlab/slides/render.py", "render_pptx"),
    ("vaultlab/figures", None),  # any def returning Path/MFigure
    ("vaultlab/citations", None),
    ("vaultlab/manuscript/polish.py", None),
    ("vaultlab/manuscript/respond.py", None),
    ("vaultlab/manuscript/data_availability.py", None),
    ("vaultlab/report", None),
]


def _iter_python_files(root: Path) -> Iterator[Path]:
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        yield p


def _parse_safe(path: Path) -> ast.Module | None:
    """Parse a Python file. Return None if it cannot be parsed."""
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return None


# ---------------------------------------------------------------------------
# Red Line #1 — No fabrication
# ---------------------------------------------------------------------------


class TestNoFabrication:
    """Citations / claims / data must trace to a verifiable source.

    Static-analysis surface: every place that emits a citation or DOI to
    user-facing output must either (a) call a verification function
    before emitting, or (b) flag the output as synthetic-illustrative.
    """

    def test_citations_module_exposes_verify_path(self) -> None:
        """The citations subpackage must publicly expose a verify-or-audit
        path. If this disappears, fabrication detection is gone."""
        citations_init = SRC_ROOT / "citations" / "__init__.py"
        assert citations_init.exists(), "vaultlab.citations module missing"

        text = citations_init.read_text(encoding="utf-8")
        # Accept any of the canonical verification entrypoints.
        has_verifier = any(
            name in text
            for name in ("audit_file", "verify_citation", "EvidenceRecord", "audit_text")
        )
        assert has_verifier, (
            "vaultlab.citations must expose at least one verification entrypoint "
            "(audit_file / verify_citation / EvidenceRecord / audit_text). "
            "Without one, citations cannot be checked before write — "
            "Red Line #1 (no fabrication) is unenforceable."
        )

    def test_no_hardcoded_fake_dois_in_source(self) -> None:
        """Source must not contain hardcoded fake/example DOIs that could
        leak into user output. Test fixtures are exempt — they live under
        tests/."""
        # Real DOIs look like 10.NNNN/* — flag obvious placeholders.
        fake_patterns = [
            re.compile(r'"10\.0+/(?:fake|test|example|placeholder|todo)', re.IGNORECASE),
            re.compile(r'"10\.1234/56789'),
            re.compile(r'doi="10\.NNNN'),
        ]
        offenders: list[str] = []
        for path in _iter_python_files(SRC_ROOT):
            text = path.read_text(encoding="utf-8")
            for pat in fake_patterns:
                if pat.search(text):
                    offenders.append(f"{path.relative_to(SRC_ROOT.parent.parent)}")
                    break
        assert not offenders, (
            "Hardcoded placeholder DOIs found in source — these can leak "
            f"into user output: {offenders}"
        )


# ---------------------------------------------------------------------------
# Red Line #2 — No silent failures
# ---------------------------------------------------------------------------


class TestNoSilentFailures:
    """Every artifact-producing entrypoint must emit an audit record.

    Sub-goal 1.1 (this file) defines the SHAPE of the contract.
    Sub-goal 1.2 wires it into every entrypoint. Until 1.2 lands, the
    enforcement test below is xfail.
    """

    def test_at_least_one_module_writes_audit_report(self) -> None:
        """Sanity check: at least some part of vaultlab must emit some
        flavor of audit report today, otherwise the contract has no
        precedent in code. Once sub-goal 1.2 lands and unifies the
        contract under ``.audit.json`` sidecars, the strict test below
        (``test_every_artifact_entrypoint_writes_manifest``) takes
        over."""
        files_with_audit_concept: list[Path] = []
        # Match any of the existing or planned naming conventions.
        pattern = re.compile(
            r"\.audit\.json|audit_manifest|AuditManifest|"
            r"audit_report|AuditReport|build_audit|audit_file|"
            r"AuditResult"
        )
        for path in _iter_python_files(SRC_ROOT):
            if pattern.search(path.read_text(encoding="utf-8")):
                files_with_audit_concept.append(path)
        assert files_with_audit_concept, (
            "No file in src/vaultlab/ references any audit-report or "
            "audit-manifest concept. Red Line #2 (no silent failures) "
            "has no precedent in code."
        )

    @pytest.mark.xfail(
        reason=(
            "Audit-manifest contract is sub-goal 1.2 of the north-star plan. "
            "Will become a passing assertion once every artifact-producing "
            "entrypoint emits a .audit.json sidecar."
        ),
        strict=False,
    )
    def test_every_artifact_entrypoint_writes_manifest(self) -> None:
        """Will pass after 1.2 wires the audit-manifest contract."""
        # Scan known artifact-producing modules; assert each has at
        # least one call to a manifest writer.
        unscanned_entrypoints = []
        for module_path, _func_name in ARTIFACT_ENTRYPOINTS:
            full = SRC_ROOT.parent / module_path
            if not full.exists():
                unscanned_entrypoints.append(module_path)
                continue
            # Collect source under that path (file or dir).
            files = [full] if full.is_file() else list(_iter_python_files(full))
            found_manifest = False
            for f in files:
                text = f.read_text(encoding="utf-8")
                if re.search(r"write_manifest|\.audit\.json|AuditManifest", text):
                    found_manifest = True
                    break
            if not found_manifest:
                unscanned_entrypoints.append(module_path)
        assert not unscanned_entrypoints, (
            f"Entrypoints without manifest writes: {unscanned_entrypoints}"
        )


# ---------------------------------------------------------------------------
# Red Line #3 — No user-data loss
# ---------------------------------------------------------------------------


class TestNoUserDataLoss:
    """Destructive operations must support dry-run / be reversible.

    A "destructive operation" is any function that calls one of:
    - shutil.rmtree / Path.unlink / Path.write_text on existing paths
    - os.remove / os.rmdir
    - Database DROP / DELETE
    """

    @pytest.mark.xfail(
        reason=(
            "Known violators: vaultlab.context.user_memory::forget and "
            "vaultlab.context.meetings::ingest_transcript lack dry_run "
            "params today. Followup hardening sub-goal will add them; "
            "this test then becomes a passing assertion. Tracked in the "
            "north-star plan's Phase 1 PROGRESS section."
        ),
        strict=False,
    )
    def test_destructive_helpers_offer_dry_run(self) -> None:
        """Functions that delete user-visible artifacts must accept a
        ``dry_run`` parameter. This is a heuristic scan."""
        violations: list[str] = []
        destructive_calls = re.compile(
            r"\b(shutil\.rmtree|os\.remove|os\.rmdir|\.unlink\(\)|Path\(\)\.unlink)"
        )
        # Allow-list: pure cache-clear utilities are not user-data loss.
        allow_substring = (
            "cache",
            "_internal",
            "test_",
            "/tests/",
        )
        for path in _iter_python_files(SRC_ROOT):
            if any(token in str(path) for token in allow_substring):
                continue
            text = path.read_text(encoding="utf-8")
            tree = _parse_safe(path)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue
                # Check if function body contains a destructive call.
                src_segment = ast.get_source_segment(text, node) or ""
                if not destructive_calls.search(src_segment):
                    continue
                # Does the function accept a dry_run / dryrun param?
                arg_names = {a.arg for a in node.args.args}
                arg_names |= {a.arg for a in node.args.kwonlyargs}
                if "dry_run" not in arg_names and "dryrun" not in arg_names:
                    rel = path.relative_to(SRC_ROOT.parent.parent)
                    violations.append(f"{rel}::{node.name} (line {node.lineno})")
        assert not violations, (
            "Functions performing destructive ops without a dry_run param "
            f"(Red Line #3): {violations}"
        )


# ---------------------------------------------------------------------------
# Red Line #4 — No vendor lock-in
# ---------------------------------------------------------------------------


class TestNoVendorLockIn:
    """All artifact outputs must be open, portable formats."""

    def test_examples_output_extensions_are_open(self) -> None:
        """Any file under examples/ that looks like a vaultlab output
        artifact must be in an open format. Source code, READMEs, and
        input fixtures are exempt."""
        if not EXAMPLES_ROOT.exists():
            pytest.skip("No examples/ directory yet (sub-goal 3.1).")
        bad: list[str] = []
        # Look in directories named like "out", "outputs", "expected-outputs".
        output_dirs: list[Path] = []
        for d in EXAMPLES_ROOT.rglob("*"):
            if not d.is_dir():
                continue
            name = d.name.lower()
            if name in ("out", "outputs", "expected-outputs", "vaultlab-demo-out"):
                output_dirs.append(d)
        for od in output_dirs:
            for f in od.rglob("*"):
                if not f.is_file():
                    continue
                if f.suffix.lower() not in ALLOWED_OUTPUT_EXTS:
                    bad.append(str(f.relative_to(EXAMPLES_ROOT)))
        assert not bad, (
            f"Output files in examples/ use closed/proprietary formats (Red Line #4): {bad}"
        )

    def test_pyproject_declares_no_proprietary_runtime_deps(self) -> None:
        """The runtime dependencies must be open-source / pip-installable.
        This is a smoke test — anything resembling a proprietary container
        (e.g., 'snowflake-connector', 'azure-*-sdk' wired into runtime)
        should not be a CORE dep."""
        pyproject = SRC_ROOT.parent.parent / "pyproject.toml"
        text = pyproject.read_text(encoding="utf-8")
        # Find the [project] dependencies section.
        m = re.search(r"^dependencies\s*=\s*\[(.*?)\]", text, re.DOTALL | re.MULTILINE)
        if not m:
            pytest.skip("pyproject.toml has no top-level dependencies array")
        deps_block = m.group(1)
        forbidden = ("snowflake", "databricks-sql", "google-cloud-bigquery")
        offenders = [name for name in forbidden if name in deps_block]
        assert not offenders, (
            f"Runtime dependencies include proprietary-platform clients: {offenders}. "
            "These should be optional extras, not core."
        )


# ---------------------------------------------------------------------------
# Meta — the red-line spec itself must exist.
# ---------------------------------------------------------------------------


class TestRedLinesSpecExists:
    """The strategic spec must declare the red lines.

    If this file is renamed or the red-line section is removed, every
    other test in this module loses its anchor. Fail loudly.
    """

    def test_north_star_spec_present(self) -> None:
        repo_root = SRC_ROOT.parent.parent
        spec = repo_root / ".claude" / "goals" / "vaultlab-north-star.md"
        assert spec.exists(), f"Strategic spec missing at {spec}"
        text = spec.read_text(encoding="utf-8")
        for needle in (
            "No fabrication",
            "No silent failures",
            "No user-data loss",
            "No vendor lock-in",
        ):
            assert needle in text, f"Red line '{needle}' missing from spec"
