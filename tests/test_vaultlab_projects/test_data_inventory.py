from __future__ import annotations

from vaultlab.projects.data_inventory import (
    AccessStatus,
    DataInventory,
    DataInventoryAudit,
    DataInventoryProblem,
    DatasetRecord,
    InventorySummary,
)


def _dataset(dataset_id: str, access: AccessStatus) -> DatasetRecord:
    return DatasetRecord(
        dataset_id=dataset_id,
        modality="synthetic-imaging",
        scale="region",
        unit_coverage=["D1", "D2", "R1", "R2"],
        replication_unit="donor",
        location=f"datasets/{dataset_id}.csv",
        fmt="csv",
        size_bytes=128,
        processing_stage="normalized",
        access=access,
        caveats=[],
    )


def test_data_inventory_summarizes_available_staged_and_needs_collection() -> None:
    inventory = DataInventory(
        datasets=[
            _dataset("DS1", AccessStatus.AVAILABLE),
            _dataset("DS2", AccessStatus.STAGED),
            _dataset("DS3", AccessStatus.NEEDS_COLLECTION),
            _dataset("DS4", AccessStatus.RESTRICTED),
        ]
    )

    summary = inventory.summarize()

    assert inventory.validate() == []
    assert summary.available_or_staged == ["DS1", "DS2"]
    assert summary.needs_collection == ["DS3"]
    assert summary.restricted == ["DS4"]
    assert DataInventory.from_dict(inventory.to_dict()) == inventory
    assert InventorySummary.from_dict(summary.to_dict()) == summary


def test_data_inventory_validate_flags_missing_required_fields_and_duplicate_ids() -> None:
    broken = DatasetRecord(
        dataset_id="",
        modality="",
        scale="region",
        unit_coverage=[],
        replication_unit="",
        location="",
        fmt="",
        size_bytes=-1,
        processing_stage="",
        access=AccessStatus.AVAILABLE,
        caveats=[],
    )
    inventory = DataInventory(datasets=[broken, _dataset("DS1", AccessStatus.AVAILABLE), _dataset("DS1", AccessStatus.STAGED)])

    messages = inventory.validate()

    assert "dataset <missing> missing required field: dataset_id" in messages
    assert "dataset <missing> missing required field: modality" in messages
    assert "dataset <missing> missing required field: replication_unit" in messages
    assert "dataset <missing> missing required field: location" in messages
    assert "dataset <missing> missing required field: fmt" in messages
    assert "dataset <missing> missing required field: processing_stage" in messages
    assert "dataset <missing> size_bytes must be non-negative" in messages
    assert "duplicate dataset_id: DS1" in messages
    assert inventory.audit().ok() is False


def test_data_inventory_record_and_audit_round_trip() -> None:
    record = _dataset("DS1", AccessStatus.AVAILABLE)
    problem = DataInventoryProblem("warn", "synthetic warning", field="dataset_id")
    audit = DataInventoryAudit("warn", [problem])

    assert DatasetRecord.from_dict(record.to_dict()) == record
    assert DataInventoryProblem.from_dict(problem.to_dict()) == problem
    assert DataInventoryAudit.from_dict(audit.to_dict()) == audit

