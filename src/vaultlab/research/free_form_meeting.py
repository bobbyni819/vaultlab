"""Free-form crosstalk meeting — Analyst + Critic + Synthesizer over
Bobby's own files (CSV / PDF / MD / JSON / XLSX / PPTX), with no
literature corpus required.

This is the ``/lit-arc``-style adversarial crosstalk machinery rewired
for the case where the user already has the data + a question and just
wants the multi-agent reasoning. See
``G:/My Drive/Knowledge/vaultlab/Sources/Notes/crosstalk-no-litsearch-design-2026-05-01.md``
for the design rationale.

Status: STUB — function signatures + docstrings only. No implementation.
The matching slash command lives at ``.claude/commands/think.md``.

Reused from elsewhere in vaultlab (NOT to be reimplemented):

* :func:`vaultlab.workflows.crosstalk._run_adversarial_meeting`
  (round loop + timeout + JSON extraction)
* :func:`vaultlab.workflows.crosstalk.write_crosstalk_artifacts`
  (transcript + per-turn writer)
* :func:`vaultlab.runner.meetings.build_meeting` and
  :func:`vaultlab.runner.meetings.wrap_context`
* :func:`vaultlab.research.pdf.extract_text` (pdfplumber/pypdf)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from vaultlab.runner.models import Agenda, Meeting
    from vaultlab.workflows.crosstalk import CrosstalkResult, RunnerCallback


__all__ = [
    "FreeFormMeetingResult",
    "IngestedFile",
    "ingest_files",
    "build_free_form_agenda",
    "build_free_form_meeting",
    "run_free_form_meeting",
]


# ---------------------------------------------------------------------------
# Result + ingest types
# ---------------------------------------------------------------------------


@dataclass
class IngestedFile:
    """One file's worth of content lifted into a meeting context block.

    ``label`` is the wrap-context tag (e.g. ``"csv-data"``, ``"pdf-text"``)
    that gets passed to :func:`vaultlab.runner.meetings.wrap_context`.

    ``content`` is the rendered string the meeting context will see. For
    CSVs / Excel this is "first 50 rows + ``df.describe()``"; for PDFs
    it's the pdfplumber text, possibly truncated.

    ``truncated`` is True iff the file was larger than the per-format
    cap (default 50 KB extracted text) and we kept only the head.
    """

    path: Path
    label: str
    content: str
    truncated: bool = False
    error: str = ""


@dataclass
class FreeFormMeetingResult:
    """Outcome of a free-form crosstalk meeting.

    Attributes:
        crosstalk_result: The underlying
            :class:`vaultlab.workflows.crosstalk.CrosstalkResult` from
            ``_run_adversarial_meeting``.
        ingested: One :class:`IngestedFile` per requested input path
            (including ones that errored — caller can surface them).
        agenda: The :class:`vaultlab.runner.models.Agenda` actually used.
        run_dir: Where transcript + per-turn files were written.
    """

    crosstalk_result: "CrosstalkResult"
    ingested: list[IngestedFile] = field(default_factory=list)
    agenda: "Agenda | None" = None
    run_dir: Path | None = None


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


def ingest_files(
    paths: list[Path | str],
    *,
    max_bytes_per_file: int = 50_000,
    csv_head_rows: int = 50,
) -> list[IngestedFile]:
    """Load a heterogeneous list of files into meeting-context blocks.

    Per-extension handlers (see design doc § File-ingestion pattern):

    * ``.csv`` / ``.tsv`` — first ``csv_head_rows`` rows + ``df.describe()``
      via pandas. Label: ``csv-data``.
    * ``.pdf`` — :func:`vaultlab.research.pdf.extract_text`.
      Label: ``pdf-text``.
    * ``.md`` / ``.txt`` — read as text. Label: ``notes``.
    * ``.json`` — load + ``json.dumps(indent=2)``, truncated to
      ``max_bytes_per_file``. Label: ``json-data``.
    * ``.xlsx`` — first sheet via openpyxl, first ``csv_head_rows``
      rows. Label: ``excel-data``.
    * ``.pptx`` — slide-by-slide text via python-pptx. Label:
      ``slides-text``.
    * Other extensions <50KB — read as text with label ``unknown``;
      otherwise skipped with ``error`` populated.

    Files that error during read get an :class:`IngestedFile` with
    empty ``content`` and a populated ``error`` field — they're still
    visible to the caller (the slash command surfaces them so the user
    knows the file was attempted).

    Args:
        paths: Input file paths (absolute preferred).
        max_bytes_per_file: Cap on extracted text per file. PDFs / JSON
            / generic text exceeding this get ``truncated=True``.
        csv_head_rows: How many rows of CSV / Excel data to embed.

    Returns:
        List of :class:`IngestedFile`, in the same order as ``paths``.
    """
    # TODO: implement per-extension handlers. Use vaultlab.research.pdf.extract_text
    # for PDFs. pandas/openpyxl/python-pptx are already transitively available.
    raise NotImplementedError("free_form_meeting.ingest_files: not yet implemented")


def _render_files_block(ingested: list[IngestedFile]) -> str:
    """Render the ingested files into a single CONTEXT string.

    Each non-errored file becomes a wrapped block via
    :func:`vaultlab.runner.meetings.wrap_context` with its label, indexed
    contiguously from 1. The block is preceded by a "FILES IN SCOPE"
    header listing original paths so the agents can cite them.

    Errored files appear in the FILES IN SCOPE list with an ``[error]``
    marker but contribute no wrap-block.
    """
    # TODO: implement using vaultlab.runner.meetings.wrap_contexts
    raise NotImplementedError(
        "free_form_meeting._render_files_block: not yet implemented"
    )


# ---------------------------------------------------------------------------
# Agenda + Meeting builders
# ---------------------------------------------------------------------------


def build_free_form_agenda(
    *,
    question: str,
    has_preliminary_analysis: bool,
    extra_questions: list[str] | None = None,
    extra_rules: list[str] | None = None,
) -> "Agenda":
    """Build the :class:`Agenda` for a free-form crosstalk meeting.

    The canonical agenda for free-form meetings is:

    * statement = ``question``
    * questions:
        1. What do the files actually show (exact values + paths)?
        2. Does the evidence support the user's question?
        3. What alternative interpretations exist?
        4. What concrete next steps would distinguish them?

      ``extra_questions`` get appended after the canonical four.

    * rules (always present):
        - Cite only paths + rows in FILES IN SCOPE; flag any external
          claim as ``[unverified]``.
        - Compare every numerical claim to a null baseline.
        - Synthesizer MUST return JSON. Default schema:
          ``{verdict, confidence, alternatives, next_steps}``.

      ``extra_rules`` get appended after the canonical three.

    * investigation_mode is :data:`InvestigationMode.DIRECTED` if a
      preliminary analysis was supplied (we're stress-testing it),
      otherwise :data:`InvestigationMode.EXPLORATORY`.
    """
    # TODO: implement. See vaultlab.runner.models.Agenda + InvestigationMode.
    raise NotImplementedError(
        "free_form_meeting.build_free_form_agenda: not yet implemented"
    )


def build_free_form_meeting(
    *,
    question: str,
    ingested: list[IngestedFile],
    preliminary_analysis: str = "",
    mode: Literal["adversarial", "critiqued"] = "adversarial",
    agenda: "Agenda | None" = None,
) -> "Meeting":
    """Build the :class:`Meeting` (NOT yet executed).

    Roles for ``mode="adversarial"`` (default): ``data_analyst`` →
    ``methods_critic`` → ``synthesizer`` (data_analysis variant from the
    role catalog — explicitly NOT the literature_* variants).

    For ``mode="critiqued"``: ``[data_analyst, methods_critic]`` — the
    virtual-lab single-role-with-always-on-critic shape, two passes.

    The session_context is built from:

    1. ``_render_files_block(ingested)`` (the FILES IN SCOPE preamble +
       wrap-blocks per file).
    2. If ``preliminary_analysis`` is non-empty, a single
       ``preliminary-analysis`` wrap-block is appended.

    The agenda defaults to :func:`build_free_form_agenda(question=...,
    has_preliminary_analysis=bool(preliminary_analysis))` if ``agenda``
    is None.
    """
    # TODO: implement using vaultlab.runner.meetings.build_meeting
    # with meeting_type="reasoning" (adversarial) or "critiqued_reasoning"
    # (critiqued), Mode.DATA_ANALYSIS.
    raise NotImplementedError(
        "free_form_meeting.build_free_form_meeting: not yet implemented"
    )


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def run_free_form_meeting(
    *,
    question: str,
    files: list[Path | str] | None = None,
    preliminary_analysis_path: Path | str | None = None,
    mode: Literal["adversarial", "critiqued"] = "adversarial",
    n_rounds: int = 3,
    timeout_seconds: int = 600,
    runner_callback: "RunnerCallback | None" = None,
    run_dir: Path | None = None,
    write_artifacts: bool = True,
    extra_questions: list[str] | None = None,
    extra_rules: list[str] | None = None,
) -> FreeFormMeetingResult:
    """Top-level entry point — ingest files, run crosstalk, return result.

    Mirrors the shape of :func:`vaultlab.workflows.crosstalk.adversarial_picker_meeting`
    but without any paper / corpus dependency.

    Pipeline:

    1. ``files`` (each path) and ``preliminary_analysis_path`` are
       resolved + read via :func:`ingest_files`. Errored files are
       included in the result for surface-up; they don't abort the run.
    2. The :class:`Meeting` is built via :func:`build_free_form_meeting`.
    3. Execution goes through
       :func:`vaultlab.workflows.crosstalk._run_adversarial_meeting`
       (reused unchanged) with ``purpose="free_form"``.
    4. If ``write_artifacts`` is True and ``run_dir`` is supplied,
       :func:`vaultlab.workflows.crosstalk.write_crosstalk_artifacts`
       writes the transcript + per-turn files. ``run_dir`` defaults to
       ``<resolve_kb_root()>/Output/think-<slug>-<date>/`` if None.
    5. Returns :class:`FreeFormMeetingResult` packaging the ingest log,
       agenda, and crosstalk result.

    The slash command (`/think`) wires this with ``runner_callback``
    pointing at the in-session Claude Code agent — same pattern as
    ``/lit-arc``'s ``crosstalk_runner``.

    Args:
        question: The free-form question driving the meeting.
        files: Paths to data / notes / slides / PDFs in scope.
        preliminary_analysis_path: Optional path to existing analysis
            content (markdown, ideally) to stress-test.
        mode: ``"adversarial"`` (3 roles, n_rounds) or ``"critiqued"``
            (2 roles, single two-pass exchange).
        n_rounds: Adversarial round count (capped at MAX_N_ROUNDS = 5).
        timeout_seconds: Per-meeting wall-clock cap.
        runner_callback: The LLM. ``None`` produces a
            ``"fallback (callback failed)"`` result — the slash command
            always supplies this.
        run_dir: Where to write transcript artifacts.
        write_artifacts: Skip the artifact writer for dry-run callers.
        extra_questions: Appended to the canonical agenda questions.
        extra_rules: Appended to the canonical agenda rules.

    Returns:
        :class:`FreeFormMeetingResult`. The synthesizer's parsed JSON
        is at ``result.crosstalk_result.final_output``.
    """
    # TODO: implement.
    # Suggested order of operations:
    #   1. ingested = ingest_files(files or [])
    #   2. preliminary = read_text(preliminary_analysis_path) if path else ""
    #   3. agenda = build_free_form_agenda(...)
    #   4. meeting = build_free_form_meeting(..., agenda=agenda)
    #   5. from vaultlab.workflows.crosstalk import _run_adversarial_meeting
    #      crosstalk_result = _run_adversarial_meeting(
    #          meeting=meeting,
    #          runner_callback=runner_callback,
    #          n_rounds=n_rounds,
    #          timeout_seconds=timeout_seconds,
    #          purpose="free_form",
    #      )
    #   6. if write_artifacts and run_dir:
    #          write_crosstalk_artifacts(crosstalk_result, run_dir=run_dir)
    #   7. return FreeFormMeetingResult(...)
    raise NotImplementedError(
        "free_form_meeting.run_free_form_meeting: not yet implemented"
    )
