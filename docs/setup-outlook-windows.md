# Setting up Outlook integration for vaultlab (Windows)

This walks you through getting `vaultlab.context.outlook` working — email, calendar, contacts, and tasks via Outlook Classic on Windows.

**Windows only.** macOS / Linux / Outlook Web users — use [`setup-google.md`](setup-google.md) for Gmail + Google Calendar instead. Same conceptual integration, different backend.

## Prerequisites

| Prerequisite | Why |
|---|---|
| **Windows OS** | COM automation is Windows-only |
| **Outlook Classic** installed | Outlook Web / "new Outlook" don't expose COM |
| **Outlook signed in** | vaultlab uses your already-authenticated session |
| **Python 3.12+** | (already installed if vaultlab is) |
| **`pywin32` package** | (auto-installed via vaultlab's optional `[outlook-windows]` extra) |

## Step 1: Confirm you have the right Outlook

There are TWO Outlooks for Windows. Check yours:

| Outlook variant | Works with vaultlab? |
|---|---|
| **Outlook Classic** (Office 365 desktop, Outlook 2016+, Outlook 2021) | ✅ YES |
| **New Outlook** (Microsoft Store, free, blue-ish UI) | ❌ NO — switch to Classic |
| **Outlook Web** (browser at outlook.office.com) | ❌ NO — use vaultlab.context.google instead |

If you have New Outlook and want to use vaultlab.context.outlook:

1. Open New Outlook
2. **File → "Use Classic Outlook"** (toggle in the top-left corner)
3. Outlook will switch to Classic; future opens default to Classic

## Step 2: Install the Outlook extra

```powershell
pip install -e "C:\Users\bobby\Downloads\vaultlab[outlook-windows]"
```

(Adjust path as needed.)

This installs `pywin32`, the Python bridge to Windows COM.

## Step 3: Sign in to Outlook

Open Outlook Classic. Sign in with your work or personal Microsoft account. Wait until your inbox loads (vaultlab can't read what Outlook hasn't synced).

vaultlab does **not** store your Outlook credentials — it uses Outlook's already-authenticated COM session.

## Step 4: Run the vaultlab setup

```powershell
vaultlab setup --outlook
```

This will:
1. Verify Outlook Classic is installed and accessible via COM
2. Confirm you're signed in (reads `Application.Session.CurrentUser`)
3. Test read access by counting your unread emails
4. Test calendar access by reading today's events
5. Save preferences to `~/.config/vaultlab/outlook/config.json`

If everything works, you'll see:

```
✓ Outlook Classic detected (version 16.x)
✓ Signed in as you@your-institution.edu
✓ Read access: 12 unread / 4321 total in inbox
✓ Calendar access: 3 events today
✓ Saved config to ~/.config/vaultlab/outlook/config.json
```

## Step 5: Verify it works

```powershell
vaultlab doctor
```

Should show:

```
✓ Outlook integration: enabled
  ✓ Email
  ✓ Calendar
  ✓ Contacts
  ✓ Tasks
```

Or, in Python:

```python
from vaultlab.context.outlook import get_today_schedule, get_unread_count

print(f"{get_unread_count()} unread emails")
for event in get_today_schedule():
    print(f"  {event.start:%H:%M} - {event.end:%H:%M}  {event.subject}")
```

## Troubleshooting

| Error | Fix |
|---|---|
| "RPC server is unavailable" | Outlook Classic crashed / closed. Reopen Outlook. |
| "Operation aborted" | Outlook is showing a permission dialog. Check the Outlook window for a confirmation popup. |
| "AttributeError: module 'pywintypes' has no attribute ..." | `pywin32` install incomplete. Run: `python -m pip install --upgrade pywin32` |
| "ImportError: No module named 'win32com'" | `pywin32` not installed. Run: `pip install -e "<vaultlab path>[outlook-windows]"` |
| "Class not registered" | Outlook installation corrupted. Repair via Settings → Apps → Office → Repair. |
| Works but read returns no emails | You may be signed into a different Outlook profile. File → Account Settings → Manage Profiles. |

## What you grant vaultlab when you enable Outlook

When `vaultlab.context.outlook` is enabled, vaultlab can (when explicitly invoked):
- Read inbox subjects + bodies
- Search emails by sender, subject, date
- Read calendar events (subject, time, attendees, body)
- Read tasks (subject, due date, status)
- Read contacts
- **Send email** (only when an explicit `send_email()` is called — not automatic)

It does NOT:
- Continuously monitor / index your inbox (every read is on-demand)
- Send emails automatically without a command
- Forward your inbox to any external service except (when an LLM call needs context) Anthropic, per [`data-privacy.md`](data-privacy.md)

## Privacy / compliance

Outlook content can be highly sensitive (patient communications at Duke; IRB-restricted thread; peer-review under embargo).

**Do not enable Outlook integration if your mailbox contains:**
- Protected Health Information (PHI)
- IRB-restricted research correspondence
- Embargoed manuscript reviews
- Other regulated content

vaultlab is **NOT HIPAA-compliant**. See [`compliance.md`](compliance.md).

If your Duke mailbox is mixed (some PHI, some research), consider:
- Use Outlook integration ONLY when working on non-PHI projects
- Or use a separate personal Microsoft account for vaultlab and forward only research-relevant emails to it
- Or disable Outlook entirely and use Google integration for non-Microsoft accounts

## Common workflows

### Daily morning brief

```powershell
vaultlab brief
```

Reads:
- Today's Outlook calendar
- Unread email count + flagged emails
- Open Outlook tasks
- Recent KB / Google Doc work-log entries

Output: a single Markdown brief written to `<kb>/Wiki/Briefs/<date>.md`.

### Pre-meeting prep

```powershell
vaultlab prep "tonsil paper review"
```

Reads:
- The matching meeting's details (time, attendees, body)
- Recent emails from each attendee
- KB notes mentioning the meeting topic

Output: a prep packet for the meeting.

### End-of-day summary

```powershell
vaultlab eod
```

Synthesizes:
- Today's KB / Google Doc entries
- Today's completed Outlook tasks
- Today's calendar (what you actually attended)

Sends to PI via Teams (if configured).

## Going further

- [`vaultlab.context.outlook` API reference](../src/vaultlab/context/outlook.md)
- [`docs/data-privacy.md`](data-privacy.md) — what data flows to Anthropic
- [`docs/compliance.md`](compliance.md) — explicit non-HIPAA disclosure
- [`docs/setup-google.md`](setup-google.md) — cross-platform alternative
