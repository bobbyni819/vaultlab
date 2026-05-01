"""Regression tests for the per-DOI PDF-acquisition trace (Gap 2, evening-5).

The decisions log used to claim "PDFs acquired: N" with no per-DOI
breakdown. ``acquire_pdf`` now stamps ``tried`` / ``tier_errors`` /
``wall_time_ms`` onto :class:`AcquisitionResult`, and the lineage
orchestrator emits a ``pdf-acquisition-trace.json`` sidecar (in
``run_dir`` if available, otherwise under ``Sources/Notes/``).
"""

from __future__ import annotations

import json
from pathlib import Path

from vaultlab.research.acquisition import AcquisitionResult


class TestPdfTraceSidecar:
    def test_writes_full_per_doi_breakdown_to_run_dir(
        self, tmp_path: Path
    ) -> None:
        """When ``run_dir`` is supplied, the sidecar lands inside it
        (matching the spec ``Output/<slug>/runs/<run_id>/`` convention)."""
        from vaultlab.research import lineage

        kb_root = tmp_path / "kb"
        kb_root.mkdir()
        run_dir = (
            kb_root
            / "Output"
            / "codex-cn"
            / "runs"
            / "2026-04-30T23-00-00"
        )

        # Simulated acquisition results: one PMC win, one paywalled fail.
        ok_pdf = run_dir.parent.parent.parent / "Sources" / "Papers" / "10-1_a.pdf"
        # We don't actually need the file to exist — the trace is metadata
        # about what was tried; the result_path string is just recorded.
        results = {
            "10.1/a": AcquisitionResult(
                doi="10.1/a",
                pdf_path=ok_pdf,
                source="pmc",
                license="pmc-oa",
                tried=("unpaywall", "pmc"),
                tier_errors={"unpaywall": "no OA location with url_for_pdf"},
                wall_time_ms=842,
            ),
            "10.2/b": AcquisitionResult(
                doi="10.2/b",
                pdf_path=None,
                source="failed",
                license=None,
                error="paywalled",
                tried=("unpaywall", "pmc", "biorxiv", "springer", "elsevier"),
                tier_errors={
                    "unpaywall": "no OA location with url_for_pdf",
                    "pmc": "no PMCID for DOI",
                    "biorxiv": "DOI not in 10.1101 prefix",
                    "springer": "OA only at meta tier or 403",
                    "elsevier": "key missing",
                },
                wall_time_ms=2100,
            ),
        }

        path = lineage._write_pdf_acquisition_trace(
            acq_results=results,
            run_dir=run_dir,
            kb_root=kb_root,
            topic="codex test",
            date_str="2026-04-30",
        )
        assert path is not None
        assert path == run_dir / "pdf-acquisition-trace.json"
        assert path.exists()

        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["run_id"] == "2026-04-30T23-00-00"
        assert data["summary"]["total_dois"] == 2
        assert data["summary"]["succeeded"] == 1
        assert data["summary"]["failed"] == 1
        assert data["summary"]["fail_reasons"] == {"paywalled": 1}

        # Per-DOI shape: succeeded carries the tier name, errors maps
        # tier → reason, wall_time_ms is the integer we recorded.
        a = data["per_doi"]["10.1/a"]
        assert a["succeeded"] == "pmc"
        assert a["tried"] == ["unpaywall", "pmc"]
        assert a["errors"] == {"unpaywall": "no OA location with url_for_pdf"}
        assert a["result_path"] is not None
        assert a["wall_time_ms"] == 842

        b = data["per_doi"]["10.2/b"]
        assert b["succeeded"] is None
        assert b["result_path"] is None
        assert b["tried"][0] == "unpaywall"
        assert "elsevier" in b["errors"]

    def test_falls_back_to_sources_notes_without_run_dir(
        self, tmp_path: Path
    ) -> None:
        """No ``run_dir`` → sidecar lands under
        ``Sources/Notes/pdf-acquisition-trace-<slug>-<date>.json`` so
        ad-hoc ``run_lit_arc`` calls still emit the trace."""
        from vaultlab.research import lineage

        kb_root = tmp_path / "kb"
        kb_root.mkdir()
        results = {
            "10.1/a": AcquisitionResult(
                doi="10.1/a",
                pdf_path=Path("/tmp/a.pdf"),
                source="unpaywall",
                license="cc-by",
                tried=("unpaywall",),
                tier_errors={},
                wall_time_ms=300,
            )
        }
        path = lineage._write_pdf_acquisition_trace(
            acq_results=results,
            run_dir=None,
            kb_root=kb_root,
            topic="codex multiplexed imaging",
            date_str="2026-04-30",
        )
        assert path is not None
        assert path.parent == kb_root / "Sources" / "Notes"
        assert path.name.startswith("pdf-acquisition-trace-")
        assert path.name.endswith("-2026-04-30.json")
        # Slug should be present in the filename.
        assert "codex-multiplexed-imaging" in path.name

    def test_empty_results_returns_none(self, tmp_path: Path) -> None:
        from vaultlab.research import lineage

        path = lineage._write_pdf_acquisition_trace(
            acq_results={},
            run_dir=None,
            kb_root=tmp_path,
            topic="x",
            date_str="2026-04-30",
        )
        assert path is None


class TestAcquisitionResultTraceFields:
    def test_default_trace_fields(self) -> None:
        """Constructing an ``AcquisitionResult`` with only required fields
        still works — new trace fields default to empty (back-compat
        for tests that pre-date evening-5)."""
        r = AcquisitionResult(
            doi="10.1/a",
            pdf_path=None,
            source="failed",
            license=None,
        )
        assert r.tried == ()
        assert r.tier_errors == {}
        assert r.wall_time_ms == 0

    def test_trace_fields_preserved(self) -> None:
        r = AcquisitionResult(
            doi="10.1/a",
            pdf_path=None,
            source="failed",
            license=None,
            error="boom",
            tried=("unpaywall", "pmc"),
            tier_errors={"unpaywall": "404"},
            wall_time_ms=500,
        )
        assert r.tried == ("unpaywall", "pmc")
        assert r.tier_errors == {"unpaywall": "404"}
        assert r.wall_time_ms == 500
