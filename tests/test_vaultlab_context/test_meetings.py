"""Tests for vaultlab.context.meetings KB-side surface.

The launch_recorder() and get_recordings_dir() helpers require Windows
+ the meeting_recorder package to be installed; those are smoke-tested
under their own platform guards. The KB-side helpers (ingest_transcript,
list_recent_transcripts, find_for_project) are pure-Python and run on
any platform.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from vaultlab.context.meetings import (
    MeetingTranscript,
    find_for_project,
    ingest_transcript,
    is_available,
    list_recent_transcripts,
)


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------


def test_is_available_returns_bool():
    """is_available never raises; returns True or False."""
    result = is_available()
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# ingest_transcript
# ---------------------------------------------------------------------------


def test_ingest_transcript_creates_canonical_file(tmp_path: Path):
    """Source file → <kb>/Sources/Meetings/<date>-<slug>.md with frontmatter."""
    src = tmp_path / "raw" / "meeting-notes.md"
    src.parent.mkdir(parents=True)
    src.write_text("Meeting body - discussion of CODEX results.", encoding="utf-8")

    kb = tmp_path / "kb"
    out = ingest_transcript(src, kb_root=kb, project="codex-imaging")

    assert out.exists()
    assert out.parent == kb / "Sources" / "Meetings"
    text = out.read_text(encoding="utf-8")
    # Frontmatter present + project recorded
    assert text.startswith("---")
    assert "kind: meeting-transcript" in text
    assert "project: codex-imaging" in text
    # Body preserved
    assert "discussion of CODEX results" in text


def test_ingest_transcript_filename_date_from_mtime(tmp_path: Path):
    """When source file has no frontmatter date, use the mtime year-month-day."""
    src = tmp_path / "raw.md"
    src.write_text("body only - no frontmatter", encoding="utf-8")
    out = ingest_transcript(src, kb_root=tmp_path / "kb")
    # Filename like "YYYY-MM-DD-raw.md"
    parts = out.name.split("-", 3)
    assert len(parts) == 4
    # First three parts form an ISO date
    iso = "-".join(parts[:3])
    datetime.strptime(iso, "%Y-%m-%d")  # would raise on invalid format


def test_ingest_transcript_uses_explicit_label(tmp_path: Path):
    """Explicit ``label`` controls the slug, not the source filename."""
    src = tmp_path / "raw_blah.md"
    src.write_text("body")
    out = ingest_transcript(
        src, kb_root=tmp_path / "kb", label="Q3 Planning Meeting!"
    )
    # Slug is lower-case + dash-separated, special chars stripped
    assert out.name.endswith("-q3-planning-meeting.md")


def test_ingest_transcript_preserves_existing_frontmatter_keys(tmp_path: Path):
    """When source has a frontmatter ``date`` / ``duration_s`` / ``project``,
    those values flow into the new frontmatter."""
    src = tmp_path / "src.md"
    src.write_text(
        "---\n"
        "date: 2026-04-15\n"
        "duration_s: 1834\n"
        "transcription_model: whisper-large-v3\n"
        "project: existing-project\n"
        "---\n\n"
        "# Meeting body"
    )
    out = ingest_transcript(src, kb_root=tmp_path / "kb")
    text = out.read_text(encoding="utf-8")
    assert "2026-04-15" in out.name
    assert "duration_s: 1834" in text
    assert "transcription_model: whisper-large-v3" in text
    # Source's project survives because no override given
    assert "project: existing-project" in text


def test_ingest_transcript_explicit_project_overrides_source(tmp_path: Path):
    """Explicit ``project=`` argument wins over the source's frontmatter project."""
    src = tmp_path / "src.md"
    src.write_text("---\nproject: old-project\n---\n\nbody")
    out = ingest_transcript(
        src, kb_root=tmp_path / "kb", project="new-project"
    )
    text = out.read_text(encoding="utf-8")
    assert "project: new-project" in text
    assert "project: old-project" not in text


def test_ingest_transcript_move_removes_source(tmp_path: Path):
    """``move=True`` deletes the source after copy."""
    src = tmp_path / "src.md"
    src.write_text("body")
    out = ingest_transcript(src, kb_root=tmp_path / "kb", move=True)
    assert out.exists()
    assert not src.exists()


def test_ingest_transcript_default_leaves_source(tmp_path: Path):
    """Default (no ``move``) leaves the source file in place."""
    src = tmp_path / "src.md"
    src.write_text("body")
    out = ingest_transcript(src, kb_root=tmp_path / "kb")
    assert out.exists()
    assert src.exists()


def test_ingest_transcript_missing_source_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        ingest_transcript(
            tmp_path / "does-not-exist.md", kb_root=tmp_path / "kb"
        )


def test_ingest_transcript_strips_existing_frontmatter_block(tmp_path: Path):
    """Source frontmatter block is parsed, then the BODY (sans frontmatter)
    is recombined with vaultlab's frontmatter — no double frontmatter."""
    src = tmp_path / "src.md"
    src.write_text(
        "---\nproject: foo\n---\n\nFirst body line.\nSecond body line.\n"
    )
    out = ingest_transcript(src, kb_root=tmp_path / "kb")
    text = out.read_text(encoding="utf-8")
    # Exactly one frontmatter block (the new one)
    assert text.count("---\n") == 2  # opening + closing fence


# ---------------------------------------------------------------------------
# list_recent_transcripts
# ---------------------------------------------------------------------------


def test_list_recent_returns_empty_when_dir_missing(tmp_path: Path):
    """No Meetings/ dir → empty list (no error)."""
    out = list_recent_transcripts(tmp_path / "kb")
    assert out == []


def test_list_recent_sorts_newest_first(tmp_path: Path):
    """Multiple transcripts are returned sorted by date descending."""
    kb = tmp_path / "kb"
    meetings = kb / "Sources" / "Meetings"
    meetings.mkdir(parents=True)
    # Create three transcripts on different dates
    (meetings / "2026-04-15-old.md").write_text(
        "---\nkind: meeting-transcript\n---\n\nbody"
    )
    (meetings / "2026-05-01-newest.md").write_text(
        "---\nkind: meeting-transcript\n---\n\nbody"
    )
    (meetings / "2026-04-22-mid.md").write_text(
        "---\nkind: meeting-transcript\n---\n\nbody"
    )

    out = list_recent_transcripts(kb, limit=10)
    assert [t.slug for t in out] == ["newest", "mid", "old"]
    assert all(isinstance(t, MeetingTranscript) for t in out)


def test_list_recent_respects_limit(tmp_path: Path):
    kb = tmp_path / "kb"
    meetings = kb / "Sources" / "Meetings"
    meetings.mkdir(parents=True)
    for d in range(1, 6):
        (meetings / f"2026-04-{d:02d}-mtg.md").write_text(
            "---\nkind: meeting-transcript\n---\n\nbody"
        )
    assert len(list_recent_transcripts(kb, limit=2)) == 2


def test_list_recent_skips_non_iso_filenames(tmp_path: Path):
    """Files that don't match the YYYY-MM-DD-slug.md pattern are ignored."""
    kb = tmp_path / "kb"
    meetings = kb / "Sources" / "Meetings"
    meetings.mkdir(parents=True)
    (meetings / "valid-2026-04-15-mtg.md").write_text("---\n---\n\nbody")
    (meetings / "2026-04-15-real.md").write_text("---\n---\n\nbody")
    (meetings / "random-notes.md").write_text("not a transcript")

    out = list_recent_transcripts(kb)
    # Only the one with a leading ISO date is kept
    assert len(out) == 1
    assert out[0].slug == "real"


def test_list_recent_parses_frontmatter_fields(tmp_path: Path):
    """Frontmatter project / duration_s / transcription_model land in the dataclass."""
    kb = tmp_path / "kb"
    meetings = kb / "Sources" / "Meetings"
    meetings.mkdir(parents=True)
    (meetings / "2026-05-01-codex.md").write_text(
        "---\n"
        "kind: meeting-transcript\n"
        "project: codex-imaging\n"
        "duration_s: 1834\n"
        "transcription_model: whisper-large-v3\n"
        "---\n\nbody"
    )
    [t] = list_recent_transcripts(kb)
    assert t.project == "codex-imaging"
    assert t.duration_s == 1834
    assert t.transcription_model == "whisper-large-v3"


# ---------------------------------------------------------------------------
# find_for_project
# ---------------------------------------------------------------------------


def test_find_for_project_filters_by_frontmatter(tmp_path: Path):
    """Only transcripts with matching ``project`` field are returned."""
    kb = tmp_path / "kb"
    meetings = kb / "Sources" / "Meetings"
    meetings.mkdir(parents=True)
    (meetings / "2026-05-01-a.md").write_text(
        "---\nkind: meeting-transcript\nproject: codex\n---\n\nbody"
    )
    (meetings / "2026-04-30-b.md").write_text(
        "---\nkind: meeting-transcript\nproject: car-t\n---\n\nbody"
    )
    (meetings / "2026-04-29-c.md").write_text(
        "---\nkind: meeting-transcript\nproject: codex\n---\n\nbody"
    )

    out = find_for_project(kb, "codex")
    assert {t.slug for t in out} == {"a", "c"}


def test_find_for_project_case_insensitive(tmp_path: Path):
    """Project slug match ignores case + surrounding whitespace."""
    kb = tmp_path / "kb"
    meetings = kb / "Sources" / "Meetings"
    meetings.mkdir(parents=True)
    (meetings / "2026-05-01-a.md").write_text(
        "---\nkind: meeting-transcript\nproject: CODEX\n---\n\nbody"
    )
    [t] = find_for_project(kb, "  codex  ")
    assert t.slug == "a"


def test_find_for_project_empty_slug_returns_empty(tmp_path: Path):
    out = find_for_project(tmp_path / "kb", "")
    assert out == []
