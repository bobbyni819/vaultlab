"""vaultlab.context.meetings — meeting-recording integration for the research companion.

Wraps the `meeting_recorder` tool (separate package — see docs/setup-meeting-recorder.md)
when installed. Records meetings, transcribes them, and ingests transcripts into the
KB so vaultlab has them as context for future tasks.

Currently Windows-only because meeting_recorder uses PyAudioWPatch + pycaw + mss for
per-app audio capture + screen recording. macOS/Linux support is planned via a
different recording backend (PR welcome).

Public surface:

    from vaultlab.context.meetings import (
        is_available,                # check if meeting_recorder is installed
        start_recording,             # begin a meeting recording
        stop_and_ingest,             # stop, transcribe, ingest into KB
        list_recent_transcripts,     # query KB for recent meeting transcripts
        link_to_project,             # associate a transcript with a project
        find_for_project,            # all transcripts for a given project
    )

Convention (per AGENTS.md):
- Transcripts go to `<kb>/Sources/Meetings/<YYYY-MM-DD>-<slug>.md` with rich frontmatter
  (date, attendees, project, recording_path, duration, transcription_model).
- Each transcript is searchable via the KB semantic-search index.
- API keys for transcription (OpenAI Whisper / Gemini) come from the user's
  `~/.config/vaultlab/secrets.toml` — vaultlab never embeds keys.

PLACEHOLDER — full implementation lands when Bobby's meeting_recorder repo is
either PyPI-published or stable enough for vaultlab to depend on.
"""

from __future__ import annotations

import platform


def is_available() -> bool:
    """Check if meeting_recorder is importable in the current environment.

    Returns True only on Windows with meeting_recorder installed. On macOS/Linux,
    returns False (recording not supported).
    """
    if platform.system() != "Windows":
        return False
    try:
        import meeting_recorder  # noqa: F401
        return True
    except ImportError:
        return False


def _check_available() -> None:
    """Raise if meeting_recorder is not installed; vaultlab.context.meetings requires it."""
    if platform.system() != "Windows":
        raise RuntimeError(
            "vaultlab.context.meetings requires Windows. "
            f"Detected platform: {platform.system()}. "
            "macOS/Linux support is planned via a different recording backend."
        )
    try:
        import meeting_recorder  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            "vaultlab.context.meetings requires the meeting_recorder package. "
            "Install with: pip install meeting-recorder "
            "(or git clone https://github.com/bobbyni819/meeting_recorder). "
            "See docs/setup-meeting-recorder.md."
        ) from e


# Placeholder. Real wrappers land when meeting_recorder is stable + installable.
__all__: list[str] = ["is_available"]
