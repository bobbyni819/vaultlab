---
module: vaultlab.context.meetings
purpose: Meeting recording + transcription + KB ingest, for research-companion context
status: scaffold (full integration when meeting_recorder is stable + PyPI-published)
platform: Windows-only (meeting_recorder dependency)
---

# vaultlab.context.meetings — meeting recording for the companion

## Why this exists

A research companion needs to know what was said in recent meetings. *"What did John say about the LPI/GPR55 finding in last Tuesday's meeting?"* should be answerable.

Manual transcription is friction. vaultlab integrates with `meeting_recorder` (Bobby's separate Windows tool) to capture, transcribe, and ingest meetings into the KB automatically.

## Why it's a separate package, not lifted into vaultlab

meeting_recorder is **heavyweight** — depends on PyAudioWPatch, pycaw, mss, faster-whisper, torch (with CUDA), opencv, ~15 packages. Most vaultlab users don't need recording; users who do can install it as an optional sibling.

vaultlab's role is the integration LAYER: when meeting_recorder is installed, vaultlab uses it; when not, vaultlab still works.

## Public surface (planned)

```python
from vaultlab.context.meetings import (
    is_available,                # bool — meeting_recorder installed?
    start_recording,             # begin a meeting; returns a session handle
    stop_and_ingest,             # stop + transcribe + ingest to KB
    list_recent_transcripts,     # query KB
    link_to_project,             # associate transcript with vaultlab project
    find_for_project,            # all transcripts for a given project slug
)
```

## Setup

1. Install `meeting_recorder` separately (Windows + NVIDIA GPU for local Whisper recommended). See [`docs/setup-meeting-recorder.md`](../../docs/setup-meeting-recorder.md).
2. Provide your own transcription API keys (OpenAI Whisper or Google Gemini) in `~/.config/vaultlab/secrets.toml`. **vaultlab never embeds keys.**
3. Run `vaultlab setup --meetings` to verify the integration works.

## What gets ingested

Every recorded meeting produces a markdown file at:

```
<kb>/Sources/Meetings/<YYYY-MM-DD>-<slug>.md
```

with frontmatter:

```yaml
---
type: meeting-transcript
date: 2026-04-28
duration_minutes: 47
attendees: [Researcher A, PI]
project: codex_lung
recording_path: ~/.config/meeting_recorder/recordings/2026-04-28-1430.wav
transcription_model: whisper-large-v3
transcription_backend: local
---
```

The body is the full transcript with speaker labels (when available). Searchable via the KB semantic-search index (`/kb ask "what did we decide about cluster 7"`).

## Project association

When you record a meeting from inside a vaultlab-tracked project (i.e., `.vaultlab-project.json` is present in the working directory), the transcript automatically gets the `project: <slug>` frontmatter. The companion can then surface the right transcript when you ask *"what was decided about <topic>?"* in that project's context.

For meetings not associated with a project, you can link them later:
```bash
vaultlab meetings link 2026-04-28-1430 --project codex_lung
```

## Privacy

Meetings can contain highly sensitive content (patient discussions, embargoed manuscript reviews, IRB-protected research). **Do not record meetings that contain regulated content** unless your institution explicitly approves cloud transcription (if using cloud backend) and KB storage.

vaultlab respects meeting_recorder's privacy controls:
- Local-only recording (no upload) is the default
- Cloud transcription (OpenAI Whisper API) is opt-in per recording
- Transcripts can be redacted before ingest via `meetings filter` patterns

See [`docs/data-privacy.md`](../../docs/data-privacy.md) and meeting_recorder's own privacy docs.

## Slash commands using this

- `/record-meeting <topic>` — start a recording in the current project
- `/transcribe <recording-path>` — transcribe an existing recording (e.g., from Teams export)
- `/meetings recent` — list recent transcripts
- `/meetings find <query>` — semantic search over transcripts
- `/brief` — daily brief includes today's meetings
- `/prep <meeting>` — prep for an upcoming meeting using context from prior transcripts

## See also

- [`docs/setup-meeting-recorder.md`](../../docs/setup-meeting-recorder.md) — installation
- `meeting_recorder` (separate repo) — the recording tool itself
- `vaultlab.context.outlook` — Outlook calendar integration (knows when meetings ARE)
- `vaultlab.context.google` — Google Calendar integration (cross-platform alternative)
