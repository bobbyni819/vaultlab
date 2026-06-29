from __future__ import annotations

from vaultlab.projects.compute_plan import (
    ComputePlan,
    ComputePlanAudit,
    ComputePlanProblem,
    ComputeTarget,
    ResourceHints,
    classify_compute_target,
)


def test_classify_compute_target_prefers_prior_peak_ram_and_round_trips() -> None:
    hints = ResourceHints(
        n_rows=1_000,
        n_units=2,
        input_bytes=1_000,
        per_row_bytes=8.0,
        prior_peak_ram_gb=64.0,
        prior_runtime_min=12.0,
    )

    plan = classify_compute_target(hints, local_ram_gb=16.0, local_runtime_min=30.0)

    assert plan.target is ComputeTarget.REMOTE_CLUSTER
    assert plan.est_ram_gb == 64.0
    assert plan.est_walltime_min == 12.0
    assert ResourceHints.from_dict(hints.to_dict()) == hints
    assert ComputePlan.from_dict(plan.to_dict()) == plan


def test_compute_plan_validate_flags_remote_cluster_without_smoke_or_checkpoint() -> None:
    plan = ComputePlan(
        analysis_id="analysis-A",
        target=ComputeTarget.REMOTE_CLUSTER,
        est_ram_gb=32.0,
        est_walltime_min=45.0,
        checkpoint_strategy=None,
        smoke_run_cmd=None,
        full_run_cmd="python analysis_A.py --full",
    )

    problems = plan.validate()

    assert "compute plan analysis-A remote target missing smoke_run_cmd" in problems
    assert "compute plan analysis-A remote target missing checkpoint_strategy" in problems
    assert plan.audit().ok() is False


def test_compute_plan_success_path_and_record_audit_round_trip() -> None:
    plan = ComputePlan(
        analysis_id="analysis-B",
        target=ComputeTarget.LOCAL,
        est_ram_gb=4.0,
        est_walltime_min=10.0,
        cpu=2,
        gpu=0,
        checkpoint_strategy="write intermediate table",
        smoke_run_cmd="python analysis_B.py --smoke",
        full_run_cmd="python analysis_B.py --full",
        sync_back=False,
    )
    problem = ComputePlanProblem("warn", "synthetic warning", field="cpu")
    audit = ComputePlanAudit("warn", [problem])

    assert plan.validate() == []
    assert plan.audit().ok() is True
    assert ComputePlan.from_dict(plan.to_dict()) == plan
    assert ComputePlanProblem.from_dict(problem.to_dict()) == problem
    assert ComputePlanAudit.from_dict(audit.to_dict()) == audit


def test_compute_plan_flags_invalid_resource_hints_and_undecided_when_insufficient() -> None:
    hints = ResourceHints(n_rows=-1, n_units=-2, input_bytes=-5, per_row_bytes=-2.0)

    assert "resource hints n_rows must be non-negative" in hints.validate()
    assert "resource hints n_units must be non-negative" in hints.validate()
    assert "resource hints input_bytes must be non-negative" in hints.validate()
    assert "resource hints per_row_bytes must be non-negative" in hints.validate()

    plan = classify_compute_target(ResourceHints())

    assert plan.target is ComputeTarget.UNDECIDED
    assert plan.est_ram_gb is None
    assert plan.est_walltime_min is None


def test_classify_compute_target_branches_and_honors_analysis_id() -> None:
    # LOCAL: both estimates known and under budget.
    local = classify_compute_target(
        ResourceHints(prior_peak_ram_gb=4.0, prior_runtime_min=10.0),
        analysis_id="job-A",
        local_ram_gb=16.0,
        local_runtime_min=30.0,
    )
    assert local.target is ComputeTarget.LOCAL
    assert local.analysis_id == "job-A"  # caller-supplied id is honored, not the sentinel

    # REMOTE on walltime alone (RAM under budget).
    remote_walltime = classify_compute_target(
        ResourceHints(prior_peak_ram_gb=2.0, prior_runtime_min=120.0),
        local_ram_gb=16.0,
        local_runtime_min=30.0,
    )
    assert remote_walltime.target is ComputeTarget.REMOTE_CLUSTER

    # REMOTE on RAM alone even when walltime is unknown.
    remote_ram_only = classify_compute_target(
        ResourceHints(prior_peak_ram_gb=64.0),
        local_ram_gb=16.0,
    )
    assert remote_ram_only.target is ComputeTarget.REMOTE_CLUSTER

    # UNDECIDED: under budget on RAM but walltime unknown -> cannot confirm local.
    undecided = classify_compute_target(ResourceHints(prior_peak_ram_gb=2.0), local_ram_gb=16.0)
    assert undecided.target is ComputeTarget.UNDECIDED
