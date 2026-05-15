"""Tests for vaultlab.manuscript.data_availability."""

from __future__ import annotations

import json
import re
from pathlib import Path

from vaultlab.manuscript.data_availability import (
    FAIR_CHECKLIST,
    REPOSITORIES,
    DAScenario,
    audit_statement,
    statement_template,
    write_data_availability_statement,
)


def test_repositories_include_core_genomics():
    for slug in ("geo", "sra", "ena", "pride", "pdb", "empiar", "ega", "dbgap"):
        assert slug in REPOSITORIES
        repo = REPOSITORIES[slug]
        assert repo.name
        assert repo.identifier_format
        assert "{id}" in repo.url_template


def test_geo_identifier_regex():
    repo = REPOSITORIES["geo"]
    assert re.match(repo.identifier_format, "GSE123456")
    assert not re.match(repo.identifier_format, "PXD000123")


def test_pride_identifier_regex():
    repo = REPOSITORIES["pride"]
    assert re.match(repo.identifier_format, "PXD000123")
    assert not re.match(repo.identifier_format, "GSE12345")


def test_pdb_identifier_regex():
    repo = REPOSITORIES["pdb"]
    assert re.match(repo.identifier_format, "1ABC")
    assert re.match(repo.identifier_format, "8XYZ")
    assert not re.match(repo.identifier_format, "ABCD")  # must start with digit


def test_fair_checklist_has_14_items():
    assert len(FAIR_CHECKLIST) == 14
    principles = {item.principle for item in FAIR_CHECKLIST}
    assert principles == {"findable", "accessible", "interoperable", "reusable"}


def test_fair_item_ids_unique():
    ids = [item.id for item in FAIR_CHECKLIST]
    assert len(ids) == len(set(ids))


def test_statement_template_public_deposit():
    t = statement_template(DAScenario.PUBLIC_DEPOSIT)
    assert "publicly available" in t


def test_statement_template_restricted_human():
    t = statement_template(DAScenario.RESTRICTED_HUMAN)
    assert "controlled-access" in t
    assert "Data Access Committee" in t


def test_statement_template_internal_only_flags_input_needed():
    t = statement_template(DAScenario.INTERNAL_ONLY)
    assert "AUTHOR INPUT NEEDED" in t


def test_statement_template_accepts_string():
    """The function accepts the scenario value as a string too."""
    assert "publicly available" in statement_template("public_deposit")


def test_audit_flags_reasonable_request_without_contact():
    findings = audit_statement(
        "All data are available from the corresponding author on reasonable request."
    )
    assert any("reasonable request" in f.message for f in findings)
    blockers = [f for f in findings if f.severity == "blocker"]
    assert blockers


def test_audit_does_not_flag_reasonable_request_with_contact():
    findings = audit_statement(
        "Data are available from the corresponding author (jane@example.org) on reasonable request."
    )
    msgs = [f.message for f in findings]
    assert not any("reasonable request" in m for m in msgs)


def test_audit_flags_human_data_without_restriction():
    findings = audit_statement(
        "Human participants were enrolled and sequenced. All data are available."
    )
    assert any("Human data" in f.message for f in findings)


def test_audit_flags_no_identifiers():
    findings = audit_statement("All data are available on request to the corresponding author.")
    assert any("persistent identifier" in f.message for f in findings)


def test_audit_clean_statement_passes():
    findings = audit_statement(
        "RNA-seq data are deposited at GEO under accession GSE123456. "
        "Source data are provided in the supplementary materials."
    )
    # May or may not have warnings, but no blocker should fire on this clean statement.
    blockers = [f for f in findings if f.severity == "blocker"]
    assert blockers == []


def test_write_data_availability_statement_emits_provenance(tmp_path: Path):
    """Writing a DAS must emit provenance receipts (red line #2)."""
    statement = (
        "RNA-seq data are deposited at GEO under accession GSE123456. "
        "Source data are provided in the supplementary materials."
    )
    out = tmp_path / "das.md"
    written = write_data_availability_statement(
        out,
        statement,
        scenario=DAScenario.PUBLIC_DEPOSIT,
    )
    assert Path(written) == out
    assert out.exists()
    body = out.read_text(encoding="utf-8")
    assert "Data Availability" in body
    assert "GSE123456" in body
    # Provenance sidecars
    prov_path = out.with_suffix(out.suffix + ".provenance.json")
    method_path = out.with_suffix(out.suffix + ".method.md")
    assert prov_path.exists()
    assert method_path.exists()
    record = json.loads(prov_path.read_text(encoding="utf-8"))
    assert record["kind"] == "manuscript_data_availability"
    assert (
        record["generated_by"]
        == "vaultlab.manuscript.data_availability.write_data_availability_statement"
    )
