"""Tests for vaultlab.provenance — sidecar writers, reader, index filters.

Adapted from ``bobby-tools/tests/test_bobby_ailab/test_provenance_and_mode.py``.
The vaultlab API differs: it writes ``<output>.provenance.json`` +
``<output>.method.md`` sidecars per AGENTS.md Reproducibility receipts, rather
than YAML frontmatter prepended to the output file. The JSONL audit index
behavior is preserved.
"""

from __future__ import annotations

import json
from pathlib import Path

from vaultlab.provenance import (
    PROVENANCE_INDEX,
    ProvenanceRecord,
    filter_index,
    hash_inputs,
    load_provenance_index,
    read_receipt,
    write_receipts,
)


# ---------------------------------------------------------------------------
# ProvenanceRecord — data model
# ---------------------------------------------------------------------------


class TestProvenanceRecord:
    def test_auto_fills_timestamp(self) -> None:
        r = ProvenanceRecord(generated_by="figure-gen")
        assert r.generated_at  # auto-filled
        assert "T" in r.generated_at  # ISO8601-ish

    def test_explicit_timestamp_preserved(self) -> None:
        r = ProvenanceRecord(generated_by="x", generated_at="2026-01-01T00:00:00")
        assert r.generated_at == "2026-01-01T00:00:00"

    def test_to_dict_omits_empty_optional_fields(self) -> None:
        d = ProvenanceRecord(generated_by="x").to_dict()
        assert "generated_by" in d
        assert "topic" not in d
        assert "round" not in d
        assert "params" not in d

    def test_to_dict_round_trip(self) -> None:
        r = ProvenanceRecord(
            generated_by="synth",
            project="p",
            round=2,
            inputs=["a.md"],
            tags=["x"],
            params={"n": 5},
            seed=42,
            model="claude-sonnet",
        )
        r2 = ProvenanceRecord.from_dict(r.to_dict())
        assert r2.generated_by == "synth"
        assert r2.round == 2
        assert r2.inputs == ["a.md"]
        assert r2.params == {"n": 5}
        assert r2.seed == 42
        assert r2.model == "claude-sonnet"


# ---------------------------------------------------------------------------
# write_receipts — sidecar emission
# ---------------------------------------------------------------------------


class TestWriteReceipts:
    def test_writes_both_sidecars(self, tmp_path: Path) -> None:
        out = tmp_path / "fig1.png"
        record = ProvenanceRecord(generated_by="figure-gen", kind="figure")
        json_path, method_path = write_receipts(out, record)

        assert json_path.is_file()
        assert method_path.is_file()
        assert json_path.name == "fig1.png.provenance.json"
        assert method_path.name == "fig1.png.method.md"
        # Sidecars sit next to the output, not nested
        assert json_path.parent == tmp_path
        assert method_path.parent == tmp_path

    def test_output_file_need_not_exist(self, tmp_path: Path) -> None:
        # Receipts should be writable before the output is materialized.
        out = tmp_path / "not_yet_built.png"
        record = ProvenanceRecord(generated_by="x")
        json_path, _ = write_receipts(out, record)
        assert not out.exists()
        assert json_path.is_file()

    def test_provenance_json_is_valid_json(self, tmp_path: Path) -> None:
        out = tmp_path / "x.md"
        record = ProvenanceRecord(
            generated_by="deep-think",
            project="CODEX",
            topic="LPI",
            tags=["metabolism"],
            finding_ids=["F001"],
            params={"alpha": 0.05},
            seed=7,
        )
        json_path, _ = write_receipts(out, record)
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["generated_by"] == "deep-think"
        assert data["project"] == "CODEX"
        assert data["finding_ids"] == ["F001"]
        assert data["seed"] == 7
        assert data["params"] == {"alpha": 0.05}
        # The output anchor field is included
        assert data["output"].endswith("x.md")

    def test_method_md_has_expected_sections(self, tmp_path: Path) -> None:
        out = tmp_path / "fig1.png"
        record = ProvenanceRecord(
            generated_by="figure-gen",
            kind="figure",
            project="CODEX",
            topic="LPI",
            inputs=["data/corr.csv"],
            params={"clusters": 8},
            related_outputs=["fig1.svg"],
            finding_ids=["F001"],
            tags=["metabolism"],
            notes="Generated for round 2 review.",
            seed=42,
            model="claude-sonnet-4-7",
            code_version="abc123",
        )
        _, method_path = write_receipts(out, record)
        text = method_path.read_text(encoding="utf-8")

        assert text.startswith("# Method — fig1.png")
        assert "## Generation" in text
        assert "`figure-gen`" in text
        assert "## Context" in text
        assert "Project: CODEX" in text
        assert "## Inputs" in text
        assert "data/corr.csv" in text
        assert "## Parameters" in text
        assert "clusters" in text
        assert "## Related outputs" in text
        assert "fig1.svg" in text
        assert "## Classification" in text
        assert "F001" in text
        assert "## Notes" in text
        assert "Generated for round 2 review." in text

    def test_method_md_omits_empty_sections(self, tmp_path: Path) -> None:
        out = tmp_path / "x.png"
        # Only required field set — most sections should be absent.
        record = ProvenanceRecord(generated_by="x")
        _, method_path = write_receipts(out, record)
        text = method_path.read_text(encoding="utf-8")
        assert "## Generation" in text  # always shown
        assert "## Context" not in text
        assert "## Inputs" not in text
        assert "## Parameters" not in text
        assert "## Related outputs" not in text
        assert "## Notes" not in text


# ---------------------------------------------------------------------------
# JSONL index
# ---------------------------------------------------------------------------


class TestProvenanceIndex:
    def test_appends_to_index(self, tmp_path: Path) -> None:
        write_receipts(
            tmp_path / "f1.md",
            ProvenanceRecord(generated_by="a", topic="t1", project="p"),
        )
        write_receipts(
            tmp_path / "f2.md",
            ProvenanceRecord(generated_by="b", topic="t2", project="p"),
        )
        index = load_provenance_index(tmp_path)
        assert len(index) == 2
        assert {r["generated_by"] for r in index} == {"a", "b"}

    def test_index_is_jsonl(self, tmp_path: Path) -> None:
        write_receipts(tmp_path / "a.md", ProvenanceRecord(generated_by="x"))
        index_path = tmp_path / PROVENANCE_INDEX
        for line in index_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                json.loads(line)

    def test_filename_is_dot_vaultlab_prefix(self) -> None:
        # Sanity check: the index file isn't named after the legacy bobby-tools
        # path, so vaultlab projects don't get cross-contaminated.
        assert PROVENANCE_INDEX == ".vaultlab-provenance.jsonl"

    def test_explicit_index_dir(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "outputs"
        index_dir = tmp_path / "audit"
        out_dir.mkdir()
        write_receipts(
            out_dir / "x.md",
            ProvenanceRecord(generated_by="x"),
            index_dir=index_dir,
        )
        # Index lives in the explicit index_dir, not next to the output.
        assert (index_dir / PROVENANCE_INDEX).is_file()
        assert not (out_dir / PROVENANCE_INDEX).exists()

    def test_filter_index_by_finding_id(self, tmp_path: Path) -> None:
        write_receipts(
            tmp_path / "a.md",
            ProvenanceRecord(generated_by="deep-think", finding_ids=["F001"], topic="t1"),
        )
        write_receipts(
            tmp_path / "b.md",
            ProvenanceRecord(generated_by="deep-think", finding_ids=["F002"], topic="t2"),
        )
        write_receipts(
            tmp_path / "c.md",
            ProvenanceRecord(generated_by="synth", finding_ids=["F001"], topic="t3"),
        )
        records = load_provenance_index(tmp_path)
        f001 = filter_index(records, finding_id="F001")
        assert len(f001) == 2
        deep_think_only = filter_index(records, generated_by="deep-think")
        assert len(deep_think_only) == 2
        both = filter_index(records, finding_id="F001", generated_by="deep-think")
        assert len(both) == 1

    def test_filter_index_by_tags_conjunctive(self, tmp_path: Path) -> None:
        write_receipts(
            tmp_path / "a.md",
            ProvenanceRecord(generated_by="x", tags=["metabolism", "directed"]),
        )
        write_receipts(
            tmp_path / "b.md",
            ProvenanceRecord(generated_by="x", tags=["metabolism"]),
        )
        records = load_provenance_index(tmp_path)
        both = filter_index(records, tags=["metabolism", "directed"])
        assert len(both) == 1


# ---------------------------------------------------------------------------
# Round-trip read
# ---------------------------------------------------------------------------


class TestReadReceipt:
    def test_round_trip(self, tmp_path: Path) -> None:
        out = tmp_path / "x.md"
        record = ProvenanceRecord(
            generated_by="deep-think",
            kind="synthesizer_output",
            finding_ids=["F001", "F002"],
        )
        write_receipts(out, record)
        loaded = read_receipt(out)
        assert loaded is not None
        assert loaded.generated_by == "deep-think"
        assert loaded.kind == "synthesizer_output"
        assert loaded.finding_ids == ["F001", "F002"]

    def test_returns_none_when_sidecar_missing(self, tmp_path: Path) -> None:
        assert read_receipt(tmp_path / "nope.png") is None

    def test_returns_none_on_corrupt_sidecar(self, tmp_path: Path) -> None:
        out = tmp_path / "y.md"
        sidecar = tmp_path / "y.md.provenance.json"
        sidecar.write_text("{not valid json", encoding="utf-8")
        assert read_receipt(out) is None


# ---------------------------------------------------------------------------
# hash_inputs — convenience hasher
# ---------------------------------------------------------------------------


class TestHashInputs:
    def test_hashes_existing_files(self, tmp_path: Path) -> None:
        a = tmp_path / "a.txt"
        a.write_text("hello", encoding="utf-8")
        digests = hash_inputs([a])
        assert str(a) in digests
        # SHA-256 hex digest is 64 chars
        assert len(digests[str(a)]) == 64

    def test_records_missing_for_nonexistent_paths(self, tmp_path: Path) -> None:
        ghost = tmp_path / "does-not-exist.bin"
        digests = hash_inputs([ghost])
        assert digests[str(ghost)] == "<missing>"

    def test_hash_is_deterministic(self, tmp_path: Path) -> None:
        f = tmp_path / "f.bin"
        f.write_bytes(b"vaultlab")
        h1 = hash_inputs([f])[str(f)]
        h2 = hash_inputs([f])[str(f)]
        assert h1 == h2
