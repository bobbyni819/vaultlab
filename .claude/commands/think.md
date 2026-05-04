---
name: think
purpose: Run a crosstalk-style multi-agent meeting (Analyst + Critic + Synthesizer) over files you already have — CSVs, PDFs, meeting notes, slide decks — without first running a literature search. Use this when you have data + a question and want adversarial reasoning, not a paper search.
arguments: <question> [--files path1 path2 ...] [--analysis path] [--rounds 3] [--mode adversarial|critiqued] [--out <run-dir>]
---

# /think

Run an Analyst → Critic → Synthesizer crosstalk meeting **without** a
literature corpus. Bring your own files (CSVs, PDFs, meeting notes,
slide decks) and a question; the meeting reasons over them.

This is the sibling of `/lit-arc`'s adversarial picker/arc meetings,
but with no paper search step. Use it when:

- You have experimental data + a hypothesis and want a critic to
  challenge your interpretation.
- You have meeting notes + a deck and want help synthesising next steps.
- You want pre-literature thinking before deciding whether to even
  spend the time on `/lit-search`.

For literature-driven workflows, use `/lit-arc` or `/lit-search` instead.

## Arguments

* `<question>` — the free-form question driving the meeting (positional,
  required). Quote it if it contains spaces.
* `--files <path>...` — list of files to put IN SCOPE for the meeting.
  Heterogeneous OK: CSV, TSV, PDF, MD, TXT, JSON, XLSX, PPTX. Each is
  rendered into a `[begin <kind> N] ... [end <kind> N]` context block.
* `--analysis <path>` — optional path to a preliminary analysis
  (markdown ideal). When present, the meeting runs in DIRECTED mode
  (stress-test the analysis); when absent, EXPLORATORY (survey the
  files and propose interpretations).
* `--rounds <N>` — adversarial round count. Default 3. Hard cap 5
  (`MAX_N_ROUNDS`).
* `--mode <adversarial|critiqued>` — `adversarial` (default) runs the
  3-role loop; `critiqued` runs a single Analyst + always-on Critic
  two-pass exchange (lighter; one round only).
* `--out <run-dir>` — where to write the transcript. Defaults to
  `<kb_root>/Output/think-<slug>-<date>/`.

## What this command produces

For question slug `<slug>` and today's date `<date>`:

- `<run-dir>/meeting-free_form-transcript.md` — combined transcript
- `<run-dir>/turn-<n>-<role>.md` — per-turn output files
- `<run-dir>/ingest-log.md` — list of files attempted, with truncation
  flags + read errors

The synthesizer's final JSON (default schema:
`{verdict, confidence, alternatives, next_steps}`) is on the last
synthesizer turn — the orchestrator extracts it as
`crosstalk_result.final_output`.

## How to execute

You (Claude Code) are the LLM via the `runner_callback`. The Python
pipeline does deterministic file ingestion (CSV/PDF/MD/JSON/XLSX/PPTX
→ wrapped context blocks) and meeting plumbing. You run the actual
agent turns.

### Step 1 — Parse arguments

```python
import shlex
from pathlib import Path

raw = shlex.split("$ARGUMENTS") if "$ARGUMENTS" else []
files: list[str] = []
analysis_path: str | None = None
rounds: int = 3
mode: str = "adversarial"
out_dir: str | None = None
positional: list[str] = []

i = 0
while i < len(raw):
    tok = raw[i]
    if tok == "--files":
        # consume until next flag
        i += 1
        while i < len(raw) and not raw[i].startswith("--"):
            files.append(raw[i])
            i += 1
    elif tok == "--analysis" and i + 1 < len(raw):
        analysis_path = raw[i + 1]; i += 2
    elif tok == "--rounds" and i + 1 < len(raw):
        rounds = int(raw[i + 1]); i += 2
    elif tok == "--mode" and i + 1 < len(raw):
        mode = raw[i + 1]; i += 2
    elif tok == "--out" and i + 1 < len(raw):
        out_dir = raw[i + 1]; i += 2
    else:
        positional.append(tok); i += 1

question = " ".join(positional).strip()
if not question:
    print("Usage: /think <question> [--files ...] [--analysis <path>] [--rounds N] [--mode adversarial|critiqued]")
    raise SystemExit(2)
```

### Step 2 — Resolve KB root + run dir

```python
from vaultlab.context import resolve_kb_root, KbRootNotConfigured
from datetime import date as _date
import re

try:
    kb_root = resolve_kb_root()
except KbRootNotConfigured as exc:
    print(f"No KB configured. Run `vaultlab init` (default: {exc.suggested_default}).")
    raise SystemExit(1)

slug = re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")[:60] or "untitled"
run_dir = Path(out_dir) if out_dir else (
    Path(kb_root) / "Output" / f"think-{slug}-{_date.today().isoformat()}"
)
```

### Step 3 — Define the runner callback (YOU are the LLM)

The callback fires once per round; you read the meeting + roles and
return one dict per role with an `output` key holding the role's raw
text. Same pattern as `/lit-arc`'s `crosstalk_runner`. Each role's
text should match its `output_format` — for the synthesizer
that's a JSON object the agenda's RULES specify
(default: `{verdict, confidence, alternatives, next_steps}`).

```python
from vaultlab.workflows import RunnerCallback
from vaultlab.runner.models import Meeting, Role
from typing import Sequence

def claude_code_runner(meeting: Meeting, members: Sequence[Role]) -> list[dict]:
    """Execute one ADVERSARIAL round in this Claude Code session.

    YOU implement at runtime. For each role in order:
      1. Read role.system_prompt + meeting.session_context + agenda.
      2. Read prior outputs already populated on meeting.roles' turns.
      3. Produce the role's response text (analyst: data summary;
         critic: structured objections; synthesizer: JSON).
    Return [{"output": "<role 1 text>"}, ..., {"output": "<role N text>"}].
    """
    ...
```

### Step 4 — Run the orchestrator

```python
from vaultlab.research.free_form_meeting import run_free_form_meeting

result = run_free_form_meeting(
    question=question,
    files=files,
    preliminary_analysis_path=analysis_path,
    mode=mode,                      # "adversarial" | "critiqued"
    n_rounds=rounds,                # default 3, capped at 5
    runner_callback=claude_code_runner,
    run_dir=run_dir,
)
```

`run_free_form_meeting`:

1. Ingests `files` per-extension (CSV/TSV → first 50 rows + describe;
   PDF → pdfplumber text; MD/TXT → raw; JSON → pretty-print; XLSX →
   first sheet head; PPTX → slide-by-slide text).
2. Builds an `Agenda` with canonical questions and the
   "cite paths/rows; flag external claims as `[unverified]`" rules.
3. Runs `_run_adversarial_meeting` (reused from
   `vaultlab.workflows.crosstalk` — unchanged).
4. Writes the transcript via `write_crosstalk_artifacts`.

### Step 5 — Print results

```
Free-form meeting complete:
  - Question:    <question>
  - Files in scope: <N> (<M> errored, see ingest-log.md)
  - Mode:        <mode>, <rounds> rounds
  - Transcript:  <run-dir>/meeting-free_form-transcript.md
  - Verdict:     <crosstalk_result.final_output["verdict"]>
                 confidence=<...>

Open the transcript: bobby-kb open vaultlab/Output/think-<slug>-<date>/meeting-free_form-transcript
```

## Default agenda (for reference)

The orchestrator builds this agenda automatically from the question:

```
INVESTIGATION MODE: DIRECTED (if --analysis given) | EXPLORATORY (if not)
AGENDA: <your question>
QUESTIONS:
  1. What do the files actually show (exact values + paths)?
  2. Does the evidence support the question?
  3. What alternative interpretations exist?
  4. What concrete next steps would distinguish them?
RULES:
  1. Cite only paths + rows in FILES IN SCOPE; flag external claims as [unverified].
  2. Compare every numerical claim to a null baseline.
  3. Synthesizer MUST return JSON {verdict, confidence, alternatives, next_steps}.
```

Pass `extra_questions` / `extra_rules` to the orchestrator when calling
from a script to extend (slash-command flags for these can be added
later — for v1 just edit the runner cell).

## Notes for users

- **No paper search.** This command never hits PubMed / Semantic Scholar
  / CrossRef. If the meeting concludes you need literature, the
  synthesizer's `next_steps` should suggest a `/lit-search <topic>` —
  run it as a follow-up.
- **No new dependencies.** pandas / openpyxl / python-pptx /
  pdfplumber are already transitively present.
- **Truncation:** PDFs and JSON > 50KB extracted text get the head
  only, with `truncated=True` in `ingest-log.md`.
- **Errors are non-fatal:** a missing or unreadable file gets logged
  in `ingest-log.md` with an error message; the meeting still runs
  over whatever loaded successfully.
- **Status:** v1 stub at
  `src/vaultlab/research/free_form_meeting.py`. Full implementation
  pending — see
  `G:/My Drive/Knowledge/vaultlab/Sources/Notes/crosstalk-no-litsearch-design-2026-05-01.md`.

## Test plan

- `tests/test_vaultlab_research/test_free_form_meeting.py` (to be
  written): CSV / PDF / MD / JSON ingestion, agenda construction,
  callback wiring (mock runner_callback), error handling.
- Confirm `python -m pytest tests/test_vaultlab_research/ --no-header -q`
  still passes 550+ after stub lands (no behavioural change since
  module is not imported at package level).
