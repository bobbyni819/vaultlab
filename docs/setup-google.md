# Setting up Google integration for vaultlab

This walks you through getting `vaultlab.context.google` working — Google Docs (lab work log), Sheets (sample manifests), Drive (file scanning), Gmail (email context), Calendar (schedule context).

**Cross-platform** — works on Windows, macOS, Linux. macOS/Linux users should use this INSTEAD of `vaultlab.context.outlook`.

## Prerequisites

- Python 3.12+ (already installed if vaultlab is)
- A Google account (personal or institutional — see compliance note below)
- 10 minutes for one-time setup

## Step 1: Create a Google Cloud project

This gives you the OAuth client credentials that identify your vaultlab install to Google's APIs.

1. Go to https://console.cloud.google.com/
2. **Create a new project** (top-left dropdown → New Project). Name: `vaultlab` (or anything; only you see it).
3. Note the project ID; you'll return here in step 4.

## Step 2: Enable the APIs you need

Enable each API at https://console.cloud.google.com/apis/library:

| API | What it powers |
|---|---|
| **Google Docs API** | Lab work log (read/append) |
| **Google Sheets API** | Sample manifests, panel data |
| **Google Drive API** | File scanning + .gsheet/.gdoc ID resolution |
| **Gmail API** | Email context retrieval |
| **Google Calendar API** | Schedule context |

Click "ENABLE" on each. (You can re-enable later if you skip some now.)

## Step 3: Configure OAuth consent screen

1. Go to https://console.cloud.google.com/apis/credentials/consent
2. **User type:** External
3. Fill in:
   - **App name:** vaultlab (or whatever)
   - **User support email:** your email
   - **Developer contact email:** your email
4. **Scopes:** add the scopes for each enabled API (Docs, Sheets, Drive, Gmail, Calendar). Use `.../auth/<api>` non-restricted scopes.
5. **Test users:** add your own Google email. This is required while the app is in "Testing" status (which is fine for personal use; no need to publish).
6. Save.

## Step 4: Create OAuth Desktop credentials

1. Go to https://console.cloud.google.com/apis/credentials
2. **+ Create Credentials → OAuth client ID**
3. **Application type:** Desktop app
4. Name: `vaultlab-desktop` (or anything)
5. Click "Create" → **download the JSON**

## Step 5: Place the credentials file

Move the downloaded JSON to:

```
# Windows
%USERPROFILE%\.config\vaultlab\google\client_secret.json

# macOS / Linux
~/.config/vaultlab/google/client_secret.json
```

(Create the directories if they don't exist.)

## Step 6: Run the vaultlab setup

```bash
vaultlab setup --google
```

This will:
1. Check that `client_secret.json` is in place
2. Open your browser for the Google OAuth consent flow
3. Confirm the scopes you're granting (you can deselect any you don't want — e.g., skip Gmail if you only want Docs + Sheets + Calendar)
4. Save the resulting token to `~/.config/vaultlab/google/google_token.json`
5. Test access by listing your authorized scopes

Subsequent vaultlab runs auto-refresh the token. You only sign in via browser ONCE per machine.

## Step 7: Verify it works

```bash
vaultlab doctor
```

Should show:

```
✓ Google credentials valid
  ✓ Docs API
  ✓ Sheets API
  ✓ Drive API
  ✓ Gmail API
  ✓ Calendar API
```

Or, in Python:

```python
from vaultlab.context.google import get_today_schedule, read_today_entries

print(get_today_schedule())          # today's calendar
print(read_today_entries()[-3:])     # last 3 entries from your lab work log
```

## Troubleshooting

| Error | Fix |
|---|---|
| "Access Not Configured" | An API isn't enabled. Go back to step 2. |
| "Token has been expired or revoked" | Delete `~/.config/vaultlab/google/google_token.json` and re-run `vaultlab setup --google`. |
| "invalid_scope: Bad Request" | You changed scopes between runs. Delete the token file and re-auth. |
| "Redirect URI mismatch" | In Cloud Console → Credentials → edit the OAuth client → add `http://localhost:8090` to authorized redirect URIs. |
| "App not verified" / "Access denied" | Your email isn't a test user. Go to OAuth consent screen → Test users → add your email. |

## Choosing the right Google account

You can use any of:

- **Personal Gmail account** (e.g., `bobbyni819@gmail.com`) — for non-research personal work logs, hobby projects
- **Institutional account** (e.g., `bobby.ni@duke.edu`) — for research that should live in your work account

**Important:** if you choose your institutional account, your IT department / IRB may have policies about what scopes you can grant to a third-party app. Check before proceeding for any account that contains PHI or IRB-restricted data.

vaultlab is **not HIPAA-compliant**. See [`compliance.md`](compliance.md). If your work account contains PHI, do not enable Gmail integration; use Docs/Sheets/Calendar only or skip Google integration entirely.

## Scope-by-scope guide

If you want to enable Google integration but limit what vaultlab can read, here's what each scope grants:

| Scope (in OAuth flow) | Read | Write |
|---|---|---|
| `auth/documents` | All Docs you can access | Append to / modify Docs |
| `auth/spreadsheets` | All Sheets you can access | Append rows / write ranges |
| `auth/drive.file` | Only files vaultlab created or you opened with vaultlab | Same |
| `auth/drive.readonly` | All files in your Drive | None |
| `auth/gmail.readonly` | All emails matching searches you initiate | None |
| `auth/calendar.readonly` | All calendar events | None |

Recommended minimum for research-companion mode:
- `documents` (lab work log)
- `spreadsheets` (project manifests)
- `drive.file` (NOT `drive.readonly` — narrower)
- `calendar.readonly`

Skip `gmail.readonly` unless you actively want email in scope.

## Switching accounts

```bash
vaultlab setup --google --reset
```

Removes the existing token + prompts for a new account.

## Going further

- [`vaultlab.context.google` API reference](../src/vaultlab/context/google.md)
- [`docs/data-privacy.md`](data-privacy.md) — what data flows to Anthropic
- [`docs/compliance.md`](compliance.md) — explicit non-HIPAA disclosure
