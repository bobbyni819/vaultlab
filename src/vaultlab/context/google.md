---
module: vaultlab.context.google
purpose: Google Workspace integration — Docs, Sheets, Drive, Gmail, Calendar — as research-companion context
status: scaffold (full implementation lifts from bobby_google)
platform: cross-platform (any OS)
---

# vaultlab.context.google — Google ecosystem as context

## Why this exists

A research companion needs context. The companion-mode framing of vaultlab assumes the LLM has access to:

- **Your lab work log** (a Google Doc you append to daily — vaultlab uses the same `daily updates` pattern as bobby-tools)
- **Project spreadsheets** (sample manifests, antibody panels, equipment bookings)
- **Drive files** (papers, figures, raw exports you've put in shared folders)
- **Recent emails** (manuscript-deadline alerts, reviewer comments, collaborator threads)
- **Calendar** (today's lab meetings, paper deadlines, conference dates)

Without this context, vaultlab is a generic LLM chat. With it, vaultlab is a colleague who reads everything you've written.

## Public surface (planned)

```python
from vaultlab.context.google import (
    # Auth (reuses bobby_google patterns)
    get_credentials, build_service,

    # Google Docs (the lab work log + project notes)
    append_to_today, read_recent_entries, get_full_text,

    # Google Sheets (sample manifests, panel info)
    read_range, write_range, append_rows, get_sheet_names,

    # Drive (file scanning + ID resolution)
    scan_directory, get_google_id, open_file,

    # Gmail (research-relevant emails only — see scope rules below)
    search_emails, get_recent_from, get_unread_count,

    # Calendar (today's schedule + upcoming events)
    get_today_schedule, get_events, find_free_slots,

    # vaultlab-specific extensions
    ingest_doc_to_kb,        # auto-ingest a Google Doc into KB
    scope_for_project,       # narrow access to current project's data
    as_context_passages,     # convert Google content into RAG passages
)
```

## Setup

```bash
vaultlab setup --google
```

This runs an interactive flow that:
1. Prompts you to place `client_secret.json` at `~/.config/vaultlab/google/client_secret.json` (one-time, manual download from Google Cloud)
2. Opens a browser for OAuth consent
3. Stores token at `~/.config/vaultlab/google/google_token.json` (auto-refreshes)
4. Verifies access by listing your authorized scopes

**Your credentials never leave your machine.** vaultlab does NOT proxy Google API calls; the OAuth token + Google API client run locally.

Full step-by-step: [`docs/setup-google.md`](../../docs/setup-google.md).

## Scope discipline (privacy)

vaultlab requests **the minimal scopes** needed for the integration you turn on. Default scopes:

| Scope | When requested | What it grants |
|---|---|---|
| `docs` (read/write) | Always | Read + append to lab work log |
| `sheets` (read/write) | Always | Read sample manifests; append run records |
| `drive` (read-only) | When `--drive` flag | Scan local Drive folder; resolve `.gsheet`/`.gdoc` IDs |
| `gmail.readonly` | When `--gmail` flag | Search emails matching your queries |
| `calendar.readonly` | When `--calendar` flag | Read today's schedule + upcoming events |

You can disable any integration: `vaultlab setup --no-gmail` or audit + revoke scopes at [Google Account → Security → Third-party access](https://myaccount.google.com/permissions).

## What gets sent to Anthropic when

vaultlab's LLM calls don't automatically include all your Google content. Content enters the prompt only when:
- A slash command explicitly fetches it (e.g., `/brief` reads today's calendar; `/research-status` reads the work log's recent entries)
- A RAG retrieval (`vaultlab.context.build_context_for_task`) judges a Google passage as relevant to the current task

Every prompt that includes Google content shows the source citations in the trace log (`<kb>/.vaultlab/runs/<id>/trace.jsonl`).

**Do not enable Google integration if your Google account holds PHI / IRB-restricted data**, or if your institution prohibits external transmission. See [`docs/compliance.md`](../../docs/compliance.md).

## How to use it

```python
from vaultlab.context.google import append_to_today, read_today_entries, get_today_schedule

# Append today's progress to the lab work log
append_to_today("Finished segmentation on tonsil run; 47k cells; QC clean.")

# Read what's been logged today (across sessions)
entries = read_today_entries()

# Today's calendar
events = get_today_schedule()
```

Slash commands that use Google context:
- `/brief` — daily morning briefing (calendar + emails + tasks + work log)
- `/eod` — end-of-day summary (synthesizes today's entries; sends to PI via Teams)
- `/weekly` — weekly summary from the work log
- `/update <description>` — log work to the Google Doc

## Migration plan

This subpackage is currently a **placeholder**. The full code is in `bobby-tools/src/bobby_google/` and migrates here in a follow-up commit. Migration steps:

1. Copy `auth.py`, `docs.py`, `sheets.py`, `drive.py`, `gmail.py`, `outlook.py` into `vaultlab/context/google/`
2. Update import paths (`bobby_google` → `vaultlab.context.google`)
3. Add vaultlab-specific config (auth at `~/.config/vaultlab/google/` instead of `~/.config/google/`)
4. Add `ingest_doc_to_kb`, `scope_for_project`, `as_context_passages` extensions
5. Add tests in `tests/test_vaultlab_context_google/`
6. Update `docs/setup-google.md` with screenshots

## See also

- [`docs/setup-google.md`](../../docs/setup-google.md) — step-by-step OAuth setup
- [`docs/data-privacy.md`](../../docs/data-privacy.md) — what data flows to Anthropic
- `bobby_google` (in bobby-tools) — the predecessor implementation
- `vaultlab.context.outlook` — Windows-specific email/calendar integration
