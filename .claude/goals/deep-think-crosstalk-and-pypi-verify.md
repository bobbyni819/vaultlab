# /goal: deep-think crosstalk wiring + v0.0.5 PyPI verification

_Created: 2026-05-15_
_Working dir: `C:/Users/bobby/Downloads/vaultlab`_

## CONTEXT

Bundled followups from the SPEC-E crosstalk-policy work (`70098fb`) and
the v0.0.5 release (`246635d`):

- **Item 1 — Deep-think crosstalk wiring.** Sub-goal 2.4 wired
  `should_invoke` into 3 call sites (`lineage.run_lit_arc` picker,
  `lineage.run_lit_arc` arc, `slides.deck.build_deck_from_lineage_result`)
  but deferred deep-think because the builders return `WorkflowPlan`
  objects rather than firing the round-table at runtime. This goal
  closes that gap.
- **Item 2 — PyPI verification.** Tag `v0.0.5` was pushed at commit
  `246635d`. Confirm the Trusted Publisher pipeline actually built and
  uploaded the wheel.

## SUCCESS CRITERIA

1. ✅ `should_invoke` gate wired into the deep-think workflow at all
   three natural recording points (plan_deep_think_round,
   plan_deep_think_with_ensemble_critic, run_deep_think_with_ensemble_critic).
2. ✅ Each firing point records `crosstalk_invoked`, `crosstalk_skip_reason`,
   and `crosstalk_task_kind` in its provenance manifest (via the
   workflow `Provenance.tags` + `notes` fields — workflow provenance has
   no separate `params` dict, mirroring how the lineage / deck-plan
   sites encode the decision).
3. ✅ Recording is **idempotent** — calling the stamp at plan-time AND
   runtime does not pile up duplicate tags or notes.
4. ✅ New tests in `tests/test_vaultlab_workflows/test_deep_think_crosstalk_wiring.py`
   exercise all three points with a stub `agent_fn`.
5. ✅ Existing workflow test suite stays green.
6. ✅ Verify whether `vaultlab==0.0.5` is live on PyPI; document install
   URL or, if missing, the failure mode + manual workaround.

## PROGRESS

### Item 1 — Deep-think crosstalk wiring — DONE

**File modified:** `src/vaultlab/workflows/deep_think.py` (+95 lines)

- New import block pulls `CrosstalkContext`, `should_invoke`, `skip_reason`
  from `vaultlab.workflows.crosstalk_policy`.
- New helper `_record_crosstalk_decision(prov, ctx)` — stamps the policy
  decision onto a `Provenance` instance via:
  - `tags`: `crosstalk_invoked={true|false}` + `crosstalk_task_kind={kind}`
    (machine-greppable)
  - `notes`: appended structured summary (`crosstalk_invoked=True;
    crosstalk_task_kind=deep_think[; crosstalk_skip_reason=…]`)
  - **Idempotent**: duplicate calls (plan-time + runtime) dedupe both tags
    and notes so the same record never piles up.
- `plan_deep_think_round` — stamps a `CrosstalkContext(task_kind="deep_think")`
  on the returned WorkflowPlan's provenance. The classic round-table
  (Analyst → Expert → Critic → Synthesizer) IS the crosstalk by structure.
- `plan_deep_think_with_ensemble_critic` — iterates `bundle.all_plans`
  (pre_critic + N critics + meta_review + synthesis) and stamps every
  phase. Each phase output file's frontmatter records the decision.
- `run_deep_think_with_ensemble_critic` — re-stamps every phase at the
  runtime firing point so hand-built bundles (that bypassed the planner)
  still record the decision. Pattern matches `lineage.run_lit_arc` and
  `slides.deck.build_deck_from_lineage_result`: gate is **instrumentation**,
  not flow-control — the round-table always fires (the v0.0.4
  `feedback_pipeline_run_through_tier_b` rule: crosstalk is part of the
  pipeline by default, not a gated luxury).

**Why provenance.tags + notes rather than `params`:**
Workflow provenance (`vaultlab.workflows._provenance.Provenance`) has no
`params` dict — only `tags: list[str]` and `notes: str`. The project-wide
`vaultlab.provenance.ProvenanceRecord` DOES carry a `params` dict (which
is what `lineage.run_lit_arc` uses at line 2754), but the workflow
runner sits on the older frontmatter-form receipt. Encoding the
decision into the existing tags + notes fields keeps changes additive
and isolates this followup to a single module.

### Item 1 — Tests — DONE

**File added:** `tests/test_vaultlab_workflows/test_deep_think_crosstalk_wiring.py`
(8 tests)

```
tests/test_vaultlab_workflows/test_deep_think_crosstalk_wiring.py
  test_plan_deep_think_round_records_crosstalk_decision_in_tags          PASSED
  test_plan_deep_think_round_records_decision_in_notes                   PASSED
  test_plan_deep_think_round_decision_lands_in_step_output_provenance    PASSED
  test_plan_ensemble_bundle_records_decision_on_every_phase              PASSED
  test_plan_ensemble_bundle_synthesis_notes_carry_decision               PASSED
  test_run_ensemble_runtime_stamps_hand_built_bundles                    PASSED
  test_run_ensemble_runtime_stamp_is_idempotent                          PASSED
  test_run_ensemble_writes_decision_into_synthesis_canonical_file        PASSED
```

Coverage:
- Plan-time stamping (tags + notes) on `plan_deep_think_round`.
- Per-step output file frontmatter inherits the decision (verified via
  `read_provenance`).
- Every phase of an ensemble bundle gets stamped (pre/critics/meta/synth).
- Runtime re-stamping on a manually-cleared bundle (simulates a hand-built
  bundle that skipped the planner).
- Idempotency: double-stamp (plan + runtime) produces exactly one of each
  marker.
- Canonical synthesis output file's frontmatter carries the decision.

### Item 2 — PyPI verification — DONE

**v0.0.5 IS LIVE on PyPI** (verified 2026-05-15).

- API check: `https://pypi.org/pypi/vaultlab/json` reports
  `releases = ['0.0.1', '0.0.2', '0.0.3', '0.0.5']` (`0.0.4` was skipped,
  consistent with the v0.0.5 release notes).
- Upload metadata: both wheel + sdist uploaded at `2026-05-15T16:05:47Z`:
  - `vaultlab-0.0.5-py3-none-any.whl`
  - `vaultlab-0.0.5.tar.gz`
- Isolated install confirmed: `python -m venv` + `pip install vaultlab==0.0.5`
  succeeded and `import vaultlab; vaultlab.__version__ == "0.0.5"`.
- Install URL: <https://pypi.org/project/vaultlab/0.0.5/>
- `latest` pointer: PyPI's `info.version` already points to `0.0.5`, so
  `pip install vaultlab` (no version pin) pulls the new release.

**Trusted Publisher pipeline is working.** Future tag pushes will
auto-publish; Bobby does not need to run `python -m build && twine upload`
manually for this release.

## EVIDENCE

```
$ python -m pytest tests/test_vaultlab_workflows/test_deep_think_crosstalk_wiring.py -v
8 passed in 0.26s

$ python -m pytest tests/test_vaultlab_workflows/ -v
149 passed in 1.01s

$ curl -s https://pypi.org/pypi/vaultlab/json | python -c "
> import json,sys; d=json.load(sys.stdin); print(sorted(d['releases'].keys()))"
['0.0.1', '0.0.2', '0.0.3', '0.0.5']

$ python -m venv /tmp/vaultlab-pypi-test
$ /tmp/vaultlab-pypi-test/Scripts/pip install vaultlab==0.0.5
$ /tmp/vaultlab-pypi-test/Scripts/python -c "import vaultlab; print(vaultlab.__version__)"
0.0.5
```

## FOLLOW-UPS

- Consider promoting workflow `Provenance` to carry an optional `params:
  dict[str, Any]` field, so deep-think / parallel / ensemble can record
  structured policy decisions the same way the project-wide
  `ProvenanceRecord` does in `lineage.run_lit_arc`. Would unify the two
  receipt forms instead of relying on the tags + notes shim.
- `0.0.4` is permanently skipped on PyPI (yanked or never published).
  If anything in the wild references `==0.0.4`, surface that to Bobby —
  but the v0.0.5 release notes already document the gap, so this is just
  a sanity-check note.
