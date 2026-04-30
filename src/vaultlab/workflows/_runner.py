"""Workflow runners — execute a ``WorkflowPlan`` end to end.

* :func:`run_workflow` — straight-line execution of every step
* :func:`run_workflow_with_reflection` — wrap the final step (or selected
  steps) in a reflection loop that lets the role refine its own draft

Both runners expect ``agent_fn(prompt, tools_list) -> str``: in-session
slash commands pass a closure that spawns the Agent tool; scripts may
pass a LocalRunner-style API caller; tests pass a deterministic stub.

Lifted from ``bobby_ailab.workflows`` (``run_workflow``,
``run_workflow_with_reflection``, ``_step_provenance``,
``_read_existing_output``).
"""

from __future__ import annotations

import os
from typing import Optional

from vaultlab.workflows._models import WorkflowPlan
from vaultlab.workflows._provenance import Provenance, write_with_provenance


def run_workflow(
    wp: WorkflowPlan,
    agent_fn,
    write_canonical: bool = True,
    resume: bool = False,
    force_steps: Optional[list[int]] = None,
) -> WorkflowPlan:
    """Execute a ``WorkflowPlan`` end-to-end.

    For each step: calls ``agent_fn(prompt, tools_list)``, fills the turn's
    output, writes the output file with provenance frontmatter, re-renders
    later prompts via ``inject_prior_outputs``.

    ``agent_fn`` signature: ``(prompt: str, tools: list[str]) -> str``.
    Slash commands pass a closure that spawns the Agent tool; scripts can
    pass a LocalRunner-style API caller or a test stub.

    When ``write_canonical`` is True and the plan has a ``canonical_output_path``,
    the last step's output is also written to that path (used for
    ``synthesis-{date}.md``, ``figure-plan.md``, per-finding Wiki pages, etc.).

    Resumability:

    * ``resume=True``: for each step, if ``step.output_path`` already exists
      on disk with real content, the file's body is used as that step's
      output instead of calling ``agent_fn``. Useful when a long-running
      round crashed partway through — rerun with ``resume=True`` and only
      the missing steps are re-executed. Steps in ``force_steps`` (0-indexed)
      always re-run even when ``resume=True``.
    * ``resume=False`` (default): every step runs ``agent_fn``.

    Returns the same ``WorkflowPlan`` with turns filled. ``wp.notes``
    accumulates a message per resumed step for diagnostic output.
    """
    force = set(force_steps or [])
    n_steps = len(wp.plan.steps)
    for i in range(n_steps):
        # Re-read each iteration because inject_prior_outputs rebuilds the plan.
        step = wp.plan.steps[i]
        existing = (
            _read_existing_output(step.output_path)
            if resume and i not in force
            else None
        )
        if existing is not None:
            response = existing
            wp.plan.turns[i].output = response
            wp.notes.append(
                f"step {i} ({step.role_id}): resumed from {os.path.basename(step.output_path)}"
            )
        else:
            response = agent_fn(step.prompt, list(step.tools))
            wp.plan.turns[i].output = response
            step_prov = _step_provenance(wp, step)
            write_with_provenance(step.output_path, response, step_prov)
        # Inject real outputs into later steps' prompts (rebuilds wp.plan)
        wp.plan = wp.plan.inject_prior_outputs(wp.plan.turns)

    if write_canonical and wp.canonical_output_path:
        # The canonical file gets the final (most integrated) step's output.
        last_output = wp.plan.turns[-1].output
        # Don't overwrite canonical file if resume and it already exists —
        # it was written in the original run.
        if not (resume and os.path.isfile(wp.canonical_output_path)):
            write_with_provenance(wp.canonical_output_path, last_output, wp.provenance)

    return wp


def run_workflow_with_reflection(
    wp: WorkflowPlan,
    agent_fn,
    max_reflections: int = 2,
    reflect_role_ids: Optional[list[str]] = None,
    resume: bool = False,
    force_steps: Optional[list[int]] = None,
) -> WorkflowPlan:
    """Run a workflow, wrapping the final (or selected) step in a reflection loop.

    Reflection = "draft → refine or say 'I am done' → repeat". Useful for
    synthesis-style steps where the first draft benefits from one or two
    self-critiques. Adopted from AI-Scientist's ``generate_ideas.py`` pattern.

    By default, reflection applies to the workflow's last step only — this
    matches the most common use case (synthesizer or narrator self-refining).
    Pass ``reflect_role_ids=["synthesizer", "narrator"]`` to reflect on
    multiple specific roles.

    ``max_reflections=0`` falls back to plain :func:`run_workflow` behavior.

    The ``resume`` and ``force_steps`` semantics mirror :func:`run_workflow`.
    """
    from vaultlab.runner.reflection import run_with_reflection

    if max_reflections <= 0:
        return run_workflow(
            wp, agent_fn=agent_fn, resume=resume, force_steps=force_steps,
        )

    # Which steps get the reflection treatment
    n_steps = len(wp.plan.steps)
    if reflect_role_ids is None:
        reflect_indices = {n_steps - 1}  # last step only
    else:
        reflect_indices = {
            i for i, step in enumerate(wp.plan.steps)
            if step.role_id in reflect_role_ids
        }

    force = set(force_steps or [])

    for i in range(n_steps):
        step = wp.plan.steps[i]
        existing = (
            _read_existing_output(step.output_path)
            if resume and i not in force
            else None
        )
        if existing is not None:
            wp.plan.turns[i].output = existing
            wp.notes.append(
                f"step {i} ({step.role_id}): resumed from {os.path.basename(step.output_path)}"
            )
        elif i in reflect_indices:
            # Reflection loop for this step
            reflection = run_with_reflection(
                agent_fn=agent_fn,
                initial_prompt=step.prompt,
                max_reflections=max_reflections,
                tools=list(step.tools),
            )
            wp.plan.turns[i].output = reflection.final
            wp.notes.append(
                f"step {i} ({step.role_id}): reflected {reflection.iterations_used} iters"
                + (" (early-exit)" if reflection.stopped_early else "")
            )
            step_prov = _step_provenance(wp, step)
            write_with_provenance(step.output_path, reflection.final, step_prov)
        else:
            response = agent_fn(step.prompt, list(step.tools))
            wp.plan.turns[i].output = response
            step_prov = _step_provenance(wp, step)
            write_with_provenance(step.output_path, response, step_prov)
        wp.plan = wp.plan.inject_prior_outputs(wp.plan.turns)

    if wp.canonical_output_path:
        last_output = wp.plan.turns[-1].output
        if not (resume and os.path.isfile(wp.canonical_output_path)):
            write_with_provenance(wp.canonical_output_path, last_output, wp.provenance)

    return wp


def _step_provenance(wp: WorkflowPlan, step) -> Provenance:
    """Build the per-step Provenance record from a WorkflowPlan's stub."""
    return Provenance(
        generated_by=wp.provenance.generated_by,
        generated_at=wp.provenance.generated_at,
        project=wp.provenance.project,
        meeting_mode=wp.provenance.meeting_mode,
        investigation_mode=wp.provenance.investigation_mode,
        topic=wp.provenance.topic,
        round=wp.provenance.round,
        inputs=list(wp.provenance.inputs),
        related_outputs=list(wp.provenance.related_outputs),
        kind=wp.provenance.kind or step.role_id,
        tags=list(wp.provenance.tags) + [step.role_id],
        finding_ids=list(wp.provenance.finding_ids),
        notes=f"Role: {step.role_name}",
    )


def _read_existing_output(path: str) -> Optional[str]:
    """Read a previously-written output file, stripping provenance frontmatter.

    Returns ``None`` if the file doesn't exist, is empty, or has only
    frontmatter. The output files are the ``run_workflow`` state — if a
    step's file exists and has real content, we can resume from it without
    calling the agent again.
    """
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return None
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            body = content[end + 4:].lstrip("\n")
            return body if body.strip() else None
    return content if content.strip() else None


__all__ = [
    "run_workflow",
    "run_workflow_with_reflection",
]
