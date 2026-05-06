---
name: onboard-me
type: orchestrated
backed_by: vaultlab.onboarding (init_project_from_intake) + LLM intake-parse
purpose: Natural-language onboarding — paste any freeform description of your project, vaultlab parses it into the IntakeForm and onboards.
arguments: [path-to-project-folder] [-- "<freeform description>"]
---

# /onboard-me [path] [-- "<freeform description>"]

> **Why this exists.** `/onboard-project` walks through 9 structured questions (topic, goals, audiences, etc.). That's the right depth — but it presupposes the user knows the 9-axis schema. `/onboard-me` lets the user dump freeform text instead. Claude parses it into the same IntakeForm; gaps are marked `[unconfirmed]` and surface as 1-2 follow-up questions.
>
> **Source:** designed during the metabolism run 2026-05-05, captured in `Sources/Notes/friction-findings-from-metabolism-run-2026-05-05.md`.

## When to use which

| Situation | Command |
|---|---|
| You can describe what you're doing in plain English | `/onboard-me` |
| You have a clean structured intake to fill | `/onboard-project` |
| You only have a topic, no project folder | `/start-project "<topic>"` |

## Inputs

- `path` (optional): project root. Defaults to `cwd`.
- `-- "<freeform description>"` (optional): the freeform text inline. If omitted, the command prompts the user to paste it.

The freeform description **does not have to be structured**. Examples that all work:

- *"I'm doing CODEX × MALDI-IMS metabolism on human intestine, 4 donors, 29 regions. PI is John Hickey at Duke. Aiming for Nature Metabolism. Have a Box folder full of CODEX TIFFs and IMS parquets."*
- *"trying to figure out if galectin-4 binds sulfatides at the apical membrane. mostly literature so far. for my prelim qual."*
- *"Brief me on prion replication mechanism — I'm reviewing a paper for journal club next week."*

The more detail, the better the parse. But "more detail" means natural-language paragraphs, not bullet points to a schema.

## How to execute

You (Claude Code) are the LLM. The Python orchestrator does the deterministic work (folder scan, file write, START_HERE generation); YOU parse the freeform text into the IntakeForm.

### Step 0 — First-encounter check

Before anything else, verify vaultlab is importable. If not, point the user at `scripts/bootstrap.ps1` (Windows) or `scripts/bootstrap.sh` (Unix) and stop.

```python
try:
    import vaultlab  # noqa: F401
except ImportError:
    print("vaultlab is not installed. Run: bash scripts/bootstrap.sh  (or pwsh scripts/bootstrap.ps1)")
    raise SystemExit(1)
```

### Step 1 — Resolve project path + KB root

```python
from pathlib import Path
import shlex
from vaultlab.context import resolve_kb_root, KbRootNotConfigured

raw_args = shlex.split("$ARGUMENTS") if "$ARGUMENTS" else []

# Split: anything before "--" is positional; anything after is the freeform description
freeform_text = ""
positional = []
if "--" in raw_args:
    sep = raw_args.index("--")
    positional = raw_args[:sep]
    freeform_text = " ".join(raw_args[sep + 1 :])
else:
    positional = raw_args

project_path = Path(positional[0]).expanduser().resolve() if positional else Path.cwd()

try:
    kb_root = resolve_kb_root()
except KbRootNotConfigured as exc:
    print(f"No KB configured. Run `vaultlab init` (default: {exc.suggested_default}).")
    raise SystemExit(1)
```

### Step 2 — Get the freeform description (interactively if missing)

If `freeform_text` is empty, prompt the user:

> Tell me about your project — anything you'd want a new lab member to know on day 1. The more detail the better, but no structure required. (Topic, goal, audience, what data/papers/drafts you have, deadlines, PI, anything else.)

Wait for the user's response. Capture it as `freeform_text`.

If the user types only a topic (≤ 8 words, no verbs), gently prompt for more:

> That's a good topic. Two more sentences would help: (a) what's the goal — understand the literature, draft a section, plan an experiment? and (b) who's the audience — yourself, your PI, journal club, conference?

### Step 3 — Parse the freeform text into an IntakeForm

You (Claude) are the LLM. Read the freeform text and extract structured fields. Return JSON matching this schema:

```json
{
  "topic": "<concise topic phrase, ≤ 12 words>",
  "goals": ["understand_literature" | "build_journal_club_deck" | "draft_methods" | "draft_results" | "draft_discussion" | "plan_experiment" | "build_pre_registration" | "lab_meeting_update" | "prelim_qual" | "thesis_chapter" | "other"],
  "audiences": ["self" | "lab_members" | "pi" | "journal_club" | "conference" | "thesis_committee" | "reviewers"],
  "have": ["pdfs" | "notes" | "wet_lab_data" | "prior_drafts" | "citations_file" | "calendar_meetings" | "nothing"],
  "exclusions": {
    "exclude_preprints": false,
    "min_year": null,
    "english_only": true
  },
  "style": ["hedged" | "direct" | "match_papers" | "match_prior_writing" | "no_preference"],
  "pi_preferences": "<one-sentence summary of any PI/advisor preferences mentioned, or empty string>",
  "deadlines": ["one_shot" | "weekly" | "specific_date:YYYY-MM-DD"],
  "free_form": "<the original freeform text, verbatim, for archival>",
  "extracted_facts": [
    {"fact": "<short verbatim quote or clean paraphrase>", "field": "topic|pi|data|deadline|other", "confidence": "high|medium|low"}
  ],
  "gaps": ["<list of 1-3 IntakeForm fields the freeform text didn't cover, or empty list if nothing is missing>"]
}
```

**Rules:**
- Use ONLY the enum values listed for `goals`, `audiences`, `have`, `style`, `deadlines`. If the freeform text suggests something outside the enums, pick the closest match and put the original phrase in `extracted_facts`.
- `topic` is the headline phrase a lab-mate would use to refer to this project. Concise.
- `extracted_facts` is your evidence trail — every meaningful claim from the freeform text should appear there. Hedged voice: if the user said "I think ~4 donors", quote that and set confidence=medium.
- `gaps` lists what IntakeForm fields you couldn't fill from the text. Don't invent answers — leave it for the follow-up loop.

### Step 4 — Build the IntakeForm and confirm with user

```python
from vaultlab.onboarding import IntakeForm

form = IntakeForm(
    topic=parsed["topic"],
    goals=parsed["goals"],
    audiences=parsed["audiences"],
    have=parsed["have"],
    exclusions=parsed["exclusions"],
    style=parsed["style"],
    pi_preferences=parsed["pi_preferences"],
    deadlines=parsed["deadlines"],
    free_form=parsed["free_form"],
)
```

Print a brief preview:

```
Parsed your description:
  Topic:     <topic>
  Goal(s):   <goals comma-joined>
  Audience:  <audiences>
  Have:      <have>
  Deadlines: <deadlines>

I caught these specific facts (your words → schema field):
  • "<quote 1>" → topic
  • "<quote 2>" → pi_preferences
  • ...

Gaps I couldn't fill from your description:
  • <gap 1>
  • <gap 2>

Confirm or correct?
```

Ask the user "Look right?" and wait. If they correct anything, update `form` accordingly.

### Step 5 — Write the intake + run init

```python
intake_path = project_path / "project_intake.md"
intake_path.write_text(form.to_markdown(), encoding="utf-8")

from vaultlab.onboarding import init_project_from_intake

result = init_project_from_intake(
    intake_path=intake_path,
    kb_root=kb_root,
    project_path=project_path,
)
```

The orchestrator handles folder scan, project-config write, and START_HERE generation — same backend as `/onboard-project`.

### Step 6 — Follow up on the gaps

`result.follow_up_questions` may include items overlapping with `parsed["gaps"]`. Ask **at most 3 follow-up questions** total (lower than `/onboard-project`'s cap of 5 — natural-language users have less patience for structured Q&A). Log answers via `vaultlab.kb.feedback.log_decision` exactly like `/onboard-project` does.

### Step 7 — Print the summary + open command

```
Project onboarded: <slug>

Files written:
  - <kb>/Wiki/Projects/<slug>/START_HERE.md
  - <kb>/Wiki/Projects/<slug>/intake.md
  - <kb>/Wiki/Projects/<slug>/decisions-log.md
  - <project>/.vaultlab-project.json

What I learned from your description:
  Topic: <topic>
  Goals: <comma-separated goals>
  Audience: <comma-separated>
  Folder: <total_files> files (<top categories>)

Next steps:
  - /lit-arc "<topic>"        — build the literature lineage arc
  - /build-deck "<topic>"     — compose a deck from your KB
  - /cite audit               — verify citations in any draft

To open: bobby-kb open vaultlab/Wiki/Projects/<slug>/START_HERE
```

## Anti-laziness rules (per AGENTS.md + Source-aware extraction)

- Every claim in `extracted_facts` MUST be either a verbatim quote (preferred) or a clean paraphrase that the user could match against their own original text.
- `gaps` is honest. If the user didn't mention `pi`, don't fabricate an empty `pi_preferences`; mark it as a gap.
- The follow-up loop is capped at 3 (vs `/onboard-project`'s 5). Stop after 3 even if gaps remain — log them as open questions in `decisions-log.md` and let the user fill them later via plain editing.
- Never re-prompt for information already in the freeform text. If the user said "Nature Metabolism deadline mid-June", don't ask "what's your deadline?" — extract `specific_date:2026-06-15` (or hedge if the date is fuzzy) and surface it for confirmation.

## Test plan

- [ ] Trial dry-run with synthetic freeform text covering all 9 IntakeForm fields — should produce a complete intake with no gaps and 0 follow-ups.
- [ ] Trial with text covering only topic + audience — should produce 2-3 specific gap questions.
- [ ] Trial with vague text ("I'm reviewing some papers") — should prompt for more detail at Step 2 before parsing.
- [ ] Trial with a real Bobby-style description from the metabolism KB — should parse `pi=John Hickey at Duke`, `topic=CODEX × MALDI-IMS metabolism`, `data=Box folder of CODEX TIFFs and IMS parquets`, `goal=draft_results`, `audience=pi+reviewers`, `deadlines=specific_date for Nature Metabolism submission`.

## Related commands

- `/onboard-project [path]` — structured-Q&A path; use when the user prefers schema over freeform
- `/start-project "<topic>"` — fastest minimal scaffold (topic only, no folder)
- `/lit-arc <topic>` — natural next step after any onboarding
