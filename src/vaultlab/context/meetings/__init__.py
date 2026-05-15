"""vaultlab.context.meetings — meeting-recording integration for the research companion.

Wraps the ``meeting_recorder`` package (published as ``vaultlab-meetings`` on
PyPI; source at https://github.com/bobbyni819/meeting-recorder). The
external package handles per-app audio capture + voice-activity detection
+ transcription; this module wraps it so vaultlab can:

* Launch the recorder from inside a Claude Code session.
* Ingest finished transcripts into the KB at canonical paths.
* Query the KB for prior meeting transcripts (e.g. "what did we discuss
  about CODEX in the last 2 weeks?").

Currently Windows-only because the recorder uses PyAudioWPatch + pycaw +
mss for per-app audio capture + screen recording. macOS/Linux support is
planned via a different recording backend.

Public surface
--------------

* :func:`is_available` — check if ``meeting_recorder`` is importable.
* :func:`launch_recorder` — spawn the ``meeting-recorder`` console script
  as a subprocess and return immediately. The user runs their meeting,
  hits stop in the recorder UI, and a transcript lands in the recorder's
  output directory.
* :func:`get_recordings_dir` — return the path where the recorder writes
  its output (``~/MeetingRecordings`` by default; configurable).
* :func:`ingest_transcript` — copy a finished transcript file into
  ``<kb>/Sources/Meetings/<YYYY-MM-DD>-<slug>.md`` with vaultlab
  frontmatter so it's discoverable through the KB's normal index.
* :func:`list_recent_transcripts` — list recent meeting transcripts from
  the KB, sorted newest-first.
* :func:`find_for_project` — find all transcripts whose frontmatter
  ``project`` field matches a given slug.

Convention (per ``AGENTS.md``)
------------------------------

* Transcripts go to ``<kb>/Sources/Meetings/<YYYY-MM-DD>-<slug>.md`` with
  rich frontmatter (date, project, recording_path, duration,
  transcription_model).
* Each transcript is searchable via the KB semantic-search index.
* API keys for transcription (OpenAI Whisper / Gemini) come from the
  user's ``meeting_recorder`` config — vaultlab never embeds keys.
"""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

__all__ = [
    "MeetingTranscript",
    "find_for_project",
    "get_recordings_dir",
    "ingest_transcript",
    "is_available",
    "launch_recorder",
    "list_recent_transcripts",
]


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


def is_available() -> bool:
    """Check if ``meeting_recorder`` is importable in the current environment.

    Returns ``True`` only on Windows with ``meeting_recorder`` installed
    (typically via ``pip install vaultlab-meetings``). On macOS/Linux,
    returns ``False`` — recording is not supported there.
    """
    if platform.system() != "Windows":
        return False
    try:
        import meeting_recorder

        return True
    except ImportError:
        return False


def _check_available() -> None:
    """Raise a clear error if ``meeting_recorder`` isn't usable here."""
    if platform.system() != "Windows":
        raise RuntimeError(
            "vaultlab.context.meetings requires Windows. "
            f"Detected platform: {platform.system()}. "
            "macOS/Linux support is planned via a different recording backend."
        )
    try:
        import meeting_recorder
    except ImportError as e:
        raise RuntimeError(
            "vaultlab.context.meetings requires the meeting_recorder package. "
            "Install with: pip install vaultlab-meetings "
            "(or git clone https://github.com/bobbyni819/meeting-recorder)."
        ) from e


# ---------------------------------------------------------------------------
# Launcher + recordings dir resolution
# ---------------------------------------------------------------------------


def launch_recorder(
    *,
    detach: bool = True,
    extra_args: list[str] | None = None,
) -> subprocess.Popen | int:
    """Spawn the ``meeting-recorder`` console script.

    The recorder runs in its own process with system-tray UI; the user
    starts/stops recording via the tray or hotkey, and on stop the
    recorder writes a transcript to its configured output directory.
    Once the meeting ends, call :func:`ingest_transcript` to copy the
    file into the KB.

    Args:
        detach: When ``True`` (default), the subprocess is fully detached
            so it survives the calling Python process exiting. The
            function returns immediately; the recorder runs in the
            background. When ``False``, returns a :class:`subprocess.Popen`
            handle the caller can wait on.
        extra_args: Extra arguments to forward to the ``meeting-recorder``
            CLI (e.g. ``["--config", "/path/to/custom.toml"]``).

    Returns:
        ``subprocess.Popen`` handle when ``detach=False``; an ``int``
        process id when ``detach=True``.

    Raises:
        RuntimeError: When the platform isn't Windows or the
            ``meeting_recorder`` package isn't installed.
        FileNotFoundError: When the ``meeting-recorder`` console script
            isn't on PATH (rare — happens when the package was installed
            via a non-pip path or the script wasn't symlinked).
    """
    _check_available()
    cmd = ["meeting-recorder", *(extra_args or [])]
    if detach:
        # On Windows, DETACHED_PROCESS + new process group lets the
        # subprocess outlive its parent. CREATE_NEW_CONSOLE is added
        # so the recorder gets its own console window.
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        proc = subprocess.Popen(
            cmd,
            creationflags=flags,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        return proc.pid
    return subprocess.Popen(cmd)


def get_recordings_dir() -> Path:
    """Return the directory where ``meeting_recorder`` writes its output.

    Reads the recorder's own config (``meeting_recorder.config.Config.load``)
    and returns the resolved ``output_dir`` as a :class:`Path`. Default
    is ``~/MeetingRecordings``.

    Raises:
        RuntimeError: When ``meeting_recorder`` isn't installed.
    """
    _check_available()
    from meeting_recorder.config import Config

    cfg = Config.load()
    return cfg.output_dir


# ---------------------------------------------------------------------------
# KB-side data model + ingestion
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MeetingTranscript:
    """A meeting transcript as stored in the vaultlab KB.

    Attributes:
        path: Absolute path to the transcript markdown in the KB.
        date: ISO date string (``YYYY-MM-DD``) parsed from filename or frontmatter.
        slug: The slugified meeting label (filename suffix after the date).
        project: Project slug from frontmatter, or empty string if unset.
        duration_s: Recording duration in seconds, or 0 if unknown.
        transcription_model: e.g. ``"whisper-large-v3"``, or empty string.
        recording_path: Original audio file path (for cross-reference).
    """

    path: Path
    date: str
    slug: str
    project: str = ""
    duration_s: int = 0
    transcription_model: str = ""
    recording_path: str = ""


def _meetings_dir(kb_root: Path) -> Path:
    """Return ``<kb_root>/Sources/Meetings`` (created if missing)."""
    out = Path(kb_root) / "Sources" / "Meetings"
    out.mkdir(parents=True, exist_ok=True)
    return out


_FILENAME_DATE_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<slug>.+)\.md$")


def _slugify_label(label: str) -> str:
    """Lower-case + dash-separate a free-form label for use in a filename."""
    s = label.strip().lower()
    # Keep alphanumerics + hyphens; collapse other runs into single dashes.
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "meeting"


def _build_frontmatter(
    *,
    date_str: str,
    slug: str,
    project: str,
    duration_s: int,
    transcription_model: str,
    recording_path: str,
) -> str:
    """Build the YAML frontmatter block for a meeting transcript."""
    lines = [
        "---",
        "kind: meeting-transcript",
        f"date: {date_str}",
        f"slug: {slug}",
    ]
    if project:
        lines.append(f"project: {project}")
    if duration_s:
        lines.append(f"duration_s: {duration_s}")
    if transcription_model:
        lines.append(f"transcription_model: {transcription_model}")
    if recording_path:
        lines.append(f"recording_path: {recording_path}")
    lines.append("---")
    return "\n".join(lines)


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Parse a YAML-ish frontmatter block at the top of a markdown file.

    Cheap implementation — supports the simple ``key: value`` shape we
    write in :func:`_build_frontmatter`. Doesn't handle nested or list
    values; callers that need full YAML should use the ``yaml`` package.
    """
    out: dict[str, str] = {}
    if not text.startswith("---"):
        return out
    parts = text.split("---", 2)
    if len(parts) < 3:
        return out
    body = parts[1].strip()
    for line in body.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip()
    return out


def ingest_transcript(
    transcript_path: Path | str,
    *,
    kb_root: Path,
    project: str = "",
    label: str | None = None,
    move: bool = False,
    dry_run: bool = False,
) -> Path:
    """Copy or move a finished transcript file into the KB.

    The destination is ``<kb_root>/Sources/Meetings/<YYYY-MM-DD>-<slug>.md``.
    If the source file already starts with YAML frontmatter (e.g. the
    recorder wrote one), we PREPEND ours and merge — vaultlab's
    frontmatter wins for vaultlab-managed keys (``kind``, ``project``).

    Args:
        transcript_path: Path to the transcript file the recorder wrote.
            Typically inside ``get_recordings_dir()``.
        kb_root: The vaultlab KB root.
        project: Optional project slug to associate this transcript with.
            Stored in the frontmatter so :func:`find_for_project` can
            retrieve it later.
        label: Optional human-readable label for the slug. When ``None``,
            uses the source filename's stem.
        move: When ``True``, the source file is removed after successful
            copy. When ``False`` (default), the source is left alone.
        dry_run: When ``True``, compute the destination path but do NOT
            write to the KB or delete the source. Use to preview where a
            transcript would land before committing the ingest. Defaults
            to ``False``.

    Returns:
        Absolute path to the new (or would-be, on dry_run) file in the KB.

    Raises:
        FileNotFoundError: When the source file doesn't exist.
    """
    src = Path(transcript_path).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"transcript not found: {src}")

    # Source files written by other tools on Windows can use cp1252 etc.
    # Read tolerantly: try utf-8, fall back to cp1252, ultimately replace.
    try:
        raw = src.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            raw = src.read_text(encoding="cp1252")
        except UnicodeDecodeError:
            raw = src.read_text(encoding="utf-8", errors="replace")
    existing_fm = _parse_frontmatter(raw)
    body = raw
    if raw.startswith("---"):
        # Strip the existing frontmatter; keep the body.
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            body = parts[2].lstrip("\n")

    # Resolve date — prefer existing frontmatter, then file mtime.
    date_str = existing_fm.get("date") or datetime.fromtimestamp(src.stat().st_mtime).strftime(
        "%Y-%m-%d"
    )

    # Resolve slug — explicit label > source stem.
    raw_label = label if label is not None else src.stem
    slug = _slugify_label(raw_label)

    duration_s = int(existing_fm.get("duration_s") or 0)
    transcription_model = existing_fm.get("transcription_model") or ""
    recording_path = existing_fm.get("recording_path") or ""

    fm = _build_frontmatter(
        date_str=date_str,
        slug=slug,
        project=project or existing_fm.get("project", ""),
        duration_s=duration_s,
        transcription_model=transcription_model,
        recording_path=recording_path,
    )
    out_path = _meetings_dir(kb_root) / f"{date_str}-{slug}.md"
    if dry_run:
        return out_path
    out_path.write_text(fm + "\n\n" + body, encoding="utf-8")

    if move:
        try:
            src.unlink()
        except OSError:
            pass

    return out_path


# ---------------------------------------------------------------------------
# KB-side queries
# ---------------------------------------------------------------------------


def _read_transcript(path: Path) -> MeetingTranscript | None:
    """Build a :class:`MeetingTranscript` from a KB-side transcript file."""
    name = path.name
    m = _FILENAME_DATE_RE.match(name)
    if not m:
        return None
    fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
    duration_str = fm.get("duration_s", "0")
    try:
        duration_s = int(duration_str)
    except (TypeError, ValueError):
        duration_s = 0
    return MeetingTranscript(
        path=path,
        date=m.group("date"),
        slug=m.group("slug"),
        project=fm.get("project", ""),
        duration_s=duration_s,
        transcription_model=fm.get("transcription_model", ""),
        recording_path=fm.get("recording_path", ""),
    )


def list_recent_transcripts(
    kb_root: Path,
    *,
    limit: int = 10,
) -> list[MeetingTranscript]:
    """List the most-recent meeting transcripts in the KB, newest first.

    Args:
        kb_root: The vaultlab KB root.
        limit: Maximum number to return (default 10).

    Returns:
        List of :class:`MeetingTranscript`, sorted by date descending.
        Empty list when no transcripts exist (or the meetings directory
        is missing).
    """
    meetings = Path(kb_root) / "Sources" / "Meetings"
    if not meetings.exists():
        return []
    entries: list[MeetingTranscript] = []
    for p in meetings.glob("*.md"):
        t = _read_transcript(p)
        if t is not None:
            entries.append(t)
    entries.sort(key=lambda t: (t.date, t.path.name), reverse=True)
    return entries[: max(0, int(limit))]


def find_for_project(
    kb_root: Path,
    project_slug: str,
) -> list[MeetingTranscript]:
    """Return every meeting transcript whose frontmatter ``project`` matches.

    Useful for "show me every meeting I had about <project>".
    """
    target = (project_slug or "").strip().lower()
    if not target:
        return []
    out: list[MeetingTranscript] = []
    for t in list_recent_transcripts(kb_root, limit=10_000):
        if t.project.strip().lower() == target:
            out.append(t)
    return out
