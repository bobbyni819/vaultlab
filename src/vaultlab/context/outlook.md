---
module: vaultlab.context.outlook
purpose: Outlook Classic integration (Windows-only) — email, calendar, contacts, tasks — as research-companion context
status: scaffold (full implementation lifts from bobby_outlook)
platform: Windows only (COM automation requires Outlook Classic)
---

# vaultlab.context.outlook — Outlook integration (Windows)

## Platform requirement

**Windows only.** vaultlab.context.outlook uses COM automation, which requires:
- Windows OS (verified at runtime; raises clearly on macOS/Linux)
- Outlook Classic installed and signed in (NOT Outlook Web / new Outlook)
- The user's mailbox already configured in Outlook

If you're on macOS/Linux or use Outlook Web, use `vaultlab.context.google` for Gmail / Google Calendar instead. Same conceptual surface, different backend.

## Why Outlook (when Google works cross-platform)?

Many academic researchers (especially at universities tied to Microsoft 365 — Duke, JHU, etc.) have Outlook as the institutional default. Their lab inbox, calendar, and tasks all live there. vaultlab supports both Outlook and Gmail as parallel context sources so researchers don't have to migrate just to use vaultlab.

## Public surface (planned)

```python
from vaultlab.context.outlook import (
    # Email
    read_inbox, search_emails, send_email, reply, forward,
    get_unread_count, get_recent_from, get_flagged_emails,
    create_draft, get_drafts, get_conversation,

    # Calendar
    get_today_schedule, get_events, find_free_slots, create_meeting,

    # Tasks
    read_tasks, create_task, complete_task, search_tasks,

    # Contacts
    read_contacts, search_contacts, create_contact,

    # Analytics
    count_by_sender, get_email_stats,

    # vaultlab-specific extensions
    scope_to_research_threads,   # narrow to emails matching project/PI
    as_context_passages,          # convert email → RAG passages
    ingest_thread_to_kb,          # auto-ingest a research thread into KB
)
```

## Setup

```powershell
vaultlab setup --outlook
```

(PowerShell — Windows.)

This:
1. Verifies Outlook Classic is installed and accessible via COM
2. Validates that you're signed in (reads `Application.Session.CurrentUser`)
3. Tests read access to inbox + calendar
4. Stores config at `~/.config/vaultlab/outlook/config.json` (preferences + auth state)

No OAuth tokens — Outlook COM uses your already-signed-in Windows session. No credentials stored.

Full setup: [`docs/setup-outlook-windows.md`](../../docs/setup-outlook-windows.md).

## What gets accessed

vaultlab's Outlook integration reads (when explicitly requested):

| Slash command / API | What it reads |
|---|---|
| `/brief` | Today's calendar + unread email count + flagged emails |
| `/prep <meeting>` | Specific event details + recent emails from attendees |
| `read_recent_from(sender)` | Recent emails from a specific sender |
| `get_today_schedule()` | Today's calendar events |
| Background context retrieval | Email subjects matching current task topics (not bodies, unless explicit) |

vaultlab does **not** continuously monitor your inbox or run background email indexing. Every read is initiated by an explicit slash command or RAG context query.

## Privacy

Outlook content can include sensitive data (patient communications, IRB-restricted threads, peer-review under embargo). **Do not enable Outlook integration on a mailbox that contains PHI/PII/IRB-restricted threads** unless your institution explicitly approves cloud LLM transmission of email content.

Every prompt that includes Outlook content shows source citations in the trace log (`<kb>/.vaultlab/runs/<id>/trace.jsonl`), so you can audit what was sent.

See [`docs/compliance.md`](../../docs/compliance.md) for the full disclosure.

## How to use it

```python
from vaultlab.context.outlook import read_inbox, get_today_schedule, search_emails

# Daily morning brief
events = get_today_schedule()
unread = read_inbox(unread_only=True, limit=5)

# Find emails about a specific manuscript
results = search_emails("LPI manuscript", since=datetime(2026, 4, 1), limit=20)
```

## Common gotchas

- **"RPC server unavailable"** — Outlook Classic crashed or is closed. Restart Outlook.
- **"Operation aborted"** — Usually a permission dialog Outlook is blocking on. Check Outlook for a confirmation popup.
- **macOS / Outlook Web users** — Not supported. Use `vaultlab.context.google` instead.
- **New Outlook (Microsoft Store version)** — COM not exposed. Switch to Outlook Classic via File → "Use Classic Outlook."

## Migration plan

This subpackage is currently a **placeholder**. The full code is in `bobby-tools/src/bobby_outlook/` and migrates here in a follow-up commit. Migration steps:

1. Copy `_connection.py`, `_constants.py`, `_converters.py`, `email.py`, `calendar.py`, `contacts.py`, `tasks.py`, `models.py` into `vaultlab/context/outlook/`
2. Update import paths (`bobby_outlook` → `vaultlab.context.outlook`)
3. Add vaultlab-specific config (`~/.config/vaultlab/outlook/`)
4. Add `scope_to_research_threads`, `ingest_thread_to_kb` extensions
5. Add Windows-platform CI test path
6. Update `docs/setup-outlook-windows.md` with screenshots

## See also

- [`docs/setup-outlook-windows.md`](../../docs/setup-outlook-windows.md) — Windows-specific setup
- [`docs/data-privacy.md`](../../docs/data-privacy.md) — what email data flows to Anthropic
- `bobby_outlook` (in bobby-tools) — the predecessor implementation
- `vaultlab.context.google` — cross-platform alternative (Gmail + Google Calendar)
