# Setting up meeting recording for vaultlab

This walks you through enabling meeting recording + transcription as a vaultlab context source. Once set up, every meeting you record gets transcribed and ingested into your KB so vaultlab can answer *"what did we decide about cluster 7 last Tuesday?"*

> **Status:** v0.0.x scaffold. Full integration lands when `meeting_recorder` is PyPI-published.

## Platform requirement

**Windows only** for v0.1. The underlying `meeting_recorder` tool uses Windows-specific audio capture (PyAudioWPatch + pycaw + mss). macOS/Linux users: meeting integration is on the v0.2 roadmap via a different recording backend.

For now, macOS/Linux users can:
- Record manually (Zoom built-in, OBS, QuickTime) and place WAV/MP4 files in a known folder
- Use `vaultlab meetings transcribe <path>` (planned) to transcribe + ingest existing recordings

## What you get

When set up:
- **`/record-meeting <topic>`** starts a recording in your current project
- Recording auto-stops when you tell it to (`/stop-recording`)
- Transcription happens automatically (local Whisper preferred; cloud Whisper opt-in)
- Transcript lands in `<kb>/Sources/Meetings/<YYYY-MM-DD>-<slug>.md` with rich frontmatter
- vaultlab can search transcripts via `/kb ask "..."` semantic search
- `/brief` and `/prep` commands include relevant past meetings

## Prerequisites

| Requirement | Why |
|---|---|
| **Windows 10 21H2+** (or Windows 11) | meeting_recorder uses Windows audio APIs |
| **NVIDIA GPU** (GTX 1060 6GB+) | Local Whisper runs on CUDA. Cloud Whisper works without GPU but costs ~$0.006/min |
| **NVIDIA driver 525+** | CUDA compatibility |
| **Python 3.12** (NOT 3.13 — torch compat) | meeting_recorder pins torch which needs 3.12 |
| **8 GB+ RAM, 16 GB+ recommended** | large-v3 Whisper uses ~3GB VRAM |
| **Microphone** | Built-in laptop mic works |

## Step 1: Install meeting_recorder

While `meeting_recorder` is not yet on PyPI, install from source:

```powershell
cd C:\Users\bobby\Downloads
# If you don't have it already:
git clone https://github.com/bobbyni819/meeting_recorder
cd meeting_recorder
pip install -e ".[local]"   # includes faster-whisper + torch for local transcription
```

For cloud-only (OpenAI Whisper API; no GPU needed):

```powershell
pip install -e .            # base only; cloud transcription
```

## Step 2: Configure transcription backend

Edit `~/.config/vaultlab/secrets.toml` (create if missing):

```toml
# Transcription backend — choose ONE:

[transcription]
backend = "local"           # local Whisper on your GPU (free, requires CUDA)
# backend = "cloud-openai"   # OpenAI Whisper API ($0.006/min, no GPU needed)
# backend = "cloud-gemini"   # Google Gemini ($)

# If using cloud-openai:
openai_api_key = "sk-..."

# If using cloud-gemini:
gemini_api_key = "..."

[summary]
# After transcription, vaultlab can use Claude to summarize:
backend = "claude"          # uses your existing Anthropic key
```

**vaultlab does not embed any keys.** All keys you provide.

## Step 3: Run the vaultlab setup

```powershell
vaultlab setup --meetings
```

This will:
1. Verify `meeting_recorder` is importable
2. Test microphone access (records 5 seconds + plays back)
3. Test transcription (transcribes the test recording)
4. Verify the KB path can receive `<kb>/Sources/Meetings/`
5. Display ready-to-use slash commands

## Step 4: Record your first meeting

```powershell
# In your project folder:
cd C:\Users\bobby\Downloads\CODEX_lung
vaultlab meetings record "Lab meeting 2026-04-29"
```

A small system-tray icon shows "🔴 RECORDING." Click it to stop, or run:

```powershell
vaultlab meetings stop
```

Transcription runs automatically (local: ~30 seconds for a 30-min meeting on RTX 3060). The transcript lands at:

```
<kb>/Sources/Meetings/2026-04-29-lab-meeting.md
```

with frontmatter:

```yaml
---
type: meeting-transcript
date: 2026-04-29
duration_minutes: 47
attendees: [Researcher A, PI]
project: codex_lung
recording_path: ~/.config/meeting_recorder/recordings/2026-04-29-1430.wav
transcription_model: whisper-large-v3
transcription_backend: local
---
```

## Step 5: Use the meeting in vaultlab

```powershell
# Find recent meetings
vaultlab meetings recent

# Search transcripts
vaultlab meetings find "cluster 7"

# Daily brief includes today's meetings
vaultlab brief

# Prep for an upcoming meeting using past context
vaultlab prep "manuscript review john"
```

Or invoke from Claude Code:

```
> /meetings recent
> /meetings find "cluster 7"
> /brief
```

## Privacy and compliance

Meeting recordings can contain **highly sensitive content**:
- Patient discussions (PHI / HIPAA)
- Embargoed manuscript reviews
- IRB-protected research
- Personnel matters

**Do NOT record meetings with regulated content** unless your institution explicitly approves:
- Local-only recording (no upload) — generally lower risk
- Cloud transcription (OpenAI Whisper API or Gemini) — requires explicit approval; data leaves your machine
- KB storage — transcripts persist; consider whether they're discoverable in legal proceedings

vaultlab is **NOT HIPAA-compliant**. See [`compliance.md`](compliance.md) and meeting_recorder's own privacy docs.

## Privacy controls

- **Local-only mode** — Default. Recording stays on your machine; transcription via local Whisper; no cloud calls.
- **Per-recording opt-in for cloud** — `vaultlab meetings record --cloud-transcribe` flags this specific recording for cloud transcription.
- **Redaction** — `vaultlab meetings redact <id> "<pattern>"` removes matching text before ingest (e.g., patient identifiers).
- **Delete** — `vaultlab meetings delete <id>` removes the transcript + recording (irreversible).

## Troubleshooting

| Error | Fix |
|---|---|
| `meeting_recorder not found` | Install per Step 1 |
| `No CUDA device` | Either install NVIDIA drivers or switch `backend = "cloud-openai"` |
| `Mic permission denied` | Windows Settings → Privacy → Microphone → enable for Python |
| `Transcription stuck on 0%` | Check `~/.config/vaultlab/logs/meetings.log` for the actual error |

## Common workflows

### Morning brief includes meeting context

```powershell
vaultlab brief
```

Includes:
- Yesterday's recorded meetings (with one-line summaries)
- Today's calendar (which may have prep needs)
- Action items extracted from yesterday's meeting transcripts

### Pre-meeting prep using past context

```powershell
vaultlab prep "thesis committee"
```

Reads:
- Outlook/Google Calendar for the meeting details
- Past transcripts mentioning the same attendees/topic
- KB notes mentioning the topic
- Outputs a Markdown prep packet

### EOD summary

```powershell
vaultlab eod
```

Synthesizes today's:
- Recorded meetings (with key decisions extracted)
- Calendar (what you actually attended)
- KB additions
- Sends to PI via Teams (if configured)

## See also

- [`vaultlab.context.meetings` API reference](../src/vaultlab/context/meetings.md)
- meeting_recorder repo (separate)
- [`docs/data-privacy.md`](data-privacy.md) — what data leaves your machine
- [`docs/compliance.md`](compliance.md) — non-HIPAA disclosure
- [`docs/setup-outlook-windows.md`](setup-outlook-windows.md) — Outlook calendar context
- [`docs/setup-google.md`](setup-google.md) — Google Calendar context (cross-platform)
