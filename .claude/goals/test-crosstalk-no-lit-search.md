# /goal: Test crosstalk system without literature-search context (task #117)

_Created: 2026-05-15_
_Working dir: `C:/Users/bobby/Downloads/vaultlab`_
_Task list ref: global task #117_

## CONTEXT

The crosstalk multi-agent system (analyst → critics → synthesizer) is
the round-table firing point used by ``/lit-arc``, ``/build-deck``,
``/deep-think``, ``/synthesize``, etc. Most of the existing tests
exercise it with a backing lit-arc seeded (corpus, summaries, picker
output). Task #117 verifies the path also works when invoked WITHOUT a
prior literature search context — the "freshly-instantiated crosstalk"
case.

Target workflows that need this:

* Journal-club discussion crosstalk — agenda + topic, no corpus.
* Deep-think on a single concept — no upstream corpus needed.
* Response-letter argument synthesis — single reviewer block, no corpus.

## SUCCESS CRITERIA

1. ✅ Crosstalk-invocation policy fires for
   ``CrosstalkContext(task_kind="deep_think", n_evidence_sources=0)``.
2. ✅ ``plan_deep_think_round`` builds a valid plan with no
   ``lineage_result`` argument passed in.
3. ✅ A no-arc deep-think plan runs end-to-end (per-step files +
   canonical synthesis path written with provenance frontmatter).
4. ✅ Provenance records the no-arc state via the existing
   ``crosstalk_invoked=true`` / ``crosstalk_task_kind=deep_think`` tags
   + notes summary.
5. ✅ Crosstalk synthesis output composes with
   ``manuscript.polish.write_polish_report`` and
   ``manuscript.respond.write_response_letter`` without any lit-arc
   detour.

## TESTS ADDED

`tests/test_vaultlab_workflows/test_crosstalk_no_lit_search.py` — 12
tests, grouped by criterion:

| Group | Test | What it checks |
|-------|------|----------------|
| (1) Policy | test_policy_fires_for_no_arc_deep_think | `should_invoke` returns True with n_evidence_sources=0 |
| (1) Policy | test_policy_fires_for_no_arc_journal_club | journal_club is FIRE_KINDS |
| (1) Policy | test_policy_fires_for_no_arc_synthesis | synthesis is FIRE_KINDS |
| (2) Planner | test_plan_deep_think_round_works_without_lineage_result | builder has no lineage_result arg + plan well-formed |
| (2) Planner | test_plan_deep_think_ensemble_works_without_lineage_result | ensemble bundle planner works no-arc |
| (3) Execute | test_deep_think_round_executes_end_to_end_without_lit_arc | per-step files + provenance written |
| (3) Execute | test_ensemble_bundle_executes_end_to_end_without_lit_arc | canonical synthesis path written |
| (3) Execute | test_synthesis_only_executes_without_findings_or_arc | Synthesizer-only path also no-arc-safe |
| (4) Provenance | test_deep_think_round_records_no_arc_state_in_provenance | notes carry crosstalk_invoked=True |
| (4) Provenance | test_crosstalk_meeting_wrapper_fires_without_arc | adversarial_arc_meeting with summaries={} |
| (5) Compose | test_crosstalk_synthesis_composes_with_manuscript_polish | synthesis output → polish report |
| (5) Compose | test_crosstalk_synthesis_composes_with_manuscript_respond | synthesis prose → response letter |

All 12 pass with a deterministic mock runner-callback / agent — no LLM
required, CI-safe.

## METHODOLOGY

* **Mock runner-callback** (`_mock_runner_callback`) — returns
  arc-shaped JSON from the synthesizer role and filler from
  analyst/critic. Matches the `RunnerCallback` shape from
  `vaultlab.workflows.crosstalk`.
* **Mock agent function** (`_mock_agent`) — returns a deterministic
  tagged string for `agent_fn(prompt, tools)`. Matches the
  `run_workflow` contract.
* **Empty `ProjectConfig`** — temp KB with just `Output/`, `Sources/`,
  `Wiki/Concepts/` subdirs. No findings, no branch summaries, no
  pre-loaded corpus. This is the "no-arc state".

## SOURCE-LEVEL FINDINGS

None — the no-arc path works correctly. Specifically:

* `plan_deep_think_round` has no `lineage_result` parameter; the builder
  is intrinsically no-arc-friendly.
* `plan_deep_think_with_ensemble_critic` likewise.
* `plan_synthesis` is also no-arc-safe (it gracefully handles empty
  `_session_summary_if_exists` and `_branch_summaries`).
* `adversarial_arc_meeting` accepts `summaries={}` and runs to
  completion when a runner_callback is supplied — the round-table fires
  regardless of corpus size.
* The provenance recording (`_record_crosstalk_decision`) is uniformly
  applied at plan time and runtime.

The 4-role round (data_analyst, domain_expert, methods_critic,
synthesizer) instantiates correctly from `build_meeting(meeting_type=
"deep_think", mode=Mode.DATA_ANALYSIS)` whether or not upstream context
is provided. The agent reading the canonical synthesis file sees its
own crosstalk decision in the YAML frontmatter.

## CONSTRAINTS HONORED

* No source code modified — tests only.
* No git hooks skipped.
* Stayed out of `src/vaultlab/workflows/deep_think.py` and
  `src/vaultlab/slides/self_review.py` (other agent's work area).
* The other agent's uncommitted edits to `_provenance.py`,
  `deep_think.py`, `test_self_review.py`, and
  `test_deep_think_crosstalk_wiring.py` were left untouched — only the
  new test file + this goal doc were staged.

## VERIFICATION

```
pytest tests/test_vaultlab_workflows/test_crosstalk_no_lit_search.py -v
  → 12 passed
pytest tests/test_vaultlab_workflows/ -q
  → 167 passed (no regression)
pytest tests/test_vaultlab_invariants/ -q
  → 8 passed (invariants unchanged)
```
