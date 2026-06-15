# vaultlab.context

The plumbing that lets every vaultlab session find the user's stuff — where the KB lives, where named files live, what to remember across chats, and (in companion mode) the life-context pipes into Google, Outlook, meetings, and a linked code repo.

See the plain-language subsystem write-ups in `Wiki/Concepts/vaultlab-subsystems.md` (the "Knowledge base", "Onboarding + setup", and companion-context sections) and the architecture sketch in [`docs/architecture.md`](../../../docs/architecture.md) (`### vaultlab.context`).

## What it is

A vaultlab session has no in-memory state to lose — everything it needs to pick up where it left off lives on disk, and `vaultlab.context` is how it *finds* that disk state. Two jobs, really. The first is small and universal: resolve the one path every orchestrator and slash command needs — the **KB root** — plus a per-user registry of named paths (your work-log Google Doc ID, where transcripts land, which Drive folder is which project) so vaultlab doesn't re-ask you every session. The second is the **research-companion** layer: optional pipes that pull your *life* context — Google Workspace, Outlook, meeting transcripts, a linked code repo, and per-user memory — into the prompt, so vaultlab behaves like a colleague who has read everything you've written rather than a generic LLM chat.

The package top-level (`vaultlab.context`) re-exports only the always-needed resolvers. The companion pipes are deliberately *not* re-exported at the top level — they're imported lazily by their own callers (`from vaultlab.context.google import ...`) so that a plain analysis session never pays the import cost of Google API clients or Outlook COM.

## Public surface

### Top-level (`vaultlab.context`)

The locations registry + KB-root resolver — the small universal core every command touches. Surfaced to users as the `vaultlab init` CLI subcommand (which writes `[paths] kb_root`) and re-exported for every orchestrator / slash command via `from vaultlab.context import ...`.

- `resolve_kb_root` — the single canonical way to obtain the KB root. Walks a fixed resolution chain (explicit arg → `$VAULTLAB_KB_ROOT` → `locations.toml` `[paths] kb_root`, then legacy `[kb] root`/`[kb] default` in the same file → `bobby_kb` `config.json` compat → first-run prompt) and returns a `Path`; raises if nothing resolves and the runner is non-interactive. Never auto-creates the directory. The `bobby_kb` compat read checks `~/.config/bobby_kb/`, `%APPDATA%`, and `%LOCALAPPDATA%` so a Windows install whose config landed at the idiomatic location still resolves.
- `KbRootNotConfigured` — exception raised when no KB root resolves non-interactively; carries a `suggested_default` so callers can offer a one-key-accept prompt.
- `load_locations` — read `~/.config/vaultlab/locations.toml` into a nested dict (empty dict if the file is missing).
- `get_path` — look up one named path by dotted slug (e.g. `"work_log.google_doc_id"`); returns `None` if unset rather than raising.
- `register_path` — write/update a named path; atomically persists to `locations.toml`.
- `locations_path` — return the canonical path of `locations.toml` (honours `$VAULTLAB_LOCATIONS` for tests).
- `missing_paths_grill_doc` — when N+ registry paths are missing, write a grill doc (via `vaultlab.kb.feedback.open_question`) instead of blocking the chat, per the async-feedback invariant.

### `user_memory` (imported directly: `from vaultlab.context.user_memory import ...`)

Per-user auto-memory so vaultlab inherits prior tuning across sessions, scoped to vaultlab's own research-companion behaviour.

- `remember` — save (or update) a memory entry under a category (`feedback` / `preference` / `pattern` / `project`) and refresh the always-loaded `MEMORY.md` index.
- `recall` — read one memory entry by category + name; `None` if absent.
- `recall_all` — return the index text plus every parsed entry (used to seed a system prompt).
- `forget` — delete a memory entry (rare, explicit; supports a `dry_run` preview).
- `memory_root` — return the `~/.config/vaultlab/user_memory` directory.
- `MemoryEntry` — dataclass for one parsed memory file (path, name, category, description, content, last_updated).
- `Category` — the `Literal` type alias for the four valid categories.
- `INDEX_FILENAME` — the index filename constant (`MEMORY.md`).

### `code` (imported directly: `from vaultlab.context.code import ...`)

Links a separate code repo to a vaultlab project so crosstalk meetings can read its files and recent changes as context.

- `get_linked_repo` — read the project config and return the linked repo `Path`, or `None` when none is linked (or the path no longer exists).
- `set_linked_repo` — write a linked-repo path into `.vaultlab-project.json` (used by `/link-repo`); validates the path is an existing directory.
- `list_recent_changes` — `git log` over the linked repo, returning structured `CommitInfo` entries (empty if not a git repo / git missing).
- `read_file` — read a file from the linked repo by repo-relative path, with a byte cap and a path-traversal guard.
- `list_files` — glob the linked repo for files, skipping standard noise dirs (`.git/`, `__pycache__/`, …), capped at `max_results`.
- `CommitInfo` — dataclass for one commit (short sha, date, author, subject).

### `meetings` (imported directly: `from vaultlab.context.meetings import ...`)

Wraps the external `meeting_recorder` package and ingests finished transcripts into the KB. Windows-only.

- `is_available` — whether `meeting_recorder` is importable here (False off Windows).
- `launch_recorder` — spawn the `meeting-recorder` console script as a (by default detached) subprocess.
- `get_recordings_dir` — return the directory the recorder writes to (reads the recorder's own config).
- `ingest_transcript` — copy/move a finished transcript into `<kb>/Sources/Meetings/<date>-<slug>.md` with vaultlab frontmatter (supports `dry_run`).
- `list_recent_transcripts` — list KB transcripts newest-first.
- `find_for_project` — every transcript whose frontmatter `project` matches a slug.
- `MeetingTranscript` — dataclass describing a transcript as stored in the KB.

### `google` subpackage (`from vaultlab.context.google import ...`)

Google Workspace as context. Cross-platform. Lifted from `bobby_google`, re-pathed to `~/.config/vaultlab/google/`. Real exported symbols:

- Auth: `get_credentials`, `build_service`.
- Docs (the lab work log): `append_to_today`, `read_today_entries`, `read_recent_entries`, `get_full_text`.
- Sheets: `read_range`, `write_range`, `append_rows`, `get_sheet_names`, `batch_read`, `batch_write`, `find_replace`, `set_formatting`, `clear_range`, `create_sheet`, `delete_sheet`.
- Drive: `scan_directory`, `get_google_id`, `open_file`, and the `DriveFile` dataclass.

### `outlook` subpackage (`from vaultlab.context.outlook import ...`)

Outlook Classic via COM automation. **Windows-only** — every call raises a clear platform error off Windows. Lifted from `bobby_outlook`. Real exported symbols:

- Email: `read_inbox`, `read_folder`, `list_folders`, `search_emails`, `search_sent`, `get_email`, `get_conversation`, `get_recent_from`, `get_unread_count`, `get_flagged_emails`, `count_by_sender`, `mark_read` / `mark_unread` / `mark_read_batch`, `move_to_folder`, `get_attachments_info`, `save_attachments`; sending — `send_email`, `reply`, `reply_to_thread`, `forward`, `create_draft`, `get_drafts`, `send_draft`, `send_with_signature`, `send_summary_email`, `send_personalized_emails`.
- Calendar: `get_today_schedule`, `get_events`, `find_free_slots`, `create_meeting`.
- Tasks: `read_tasks`, `create_task`, `complete_task`.
- Contacts: `read_contacts`, `search_contacts`, `create_contact`.
- Models: `Email`, `CalendarEvent`, `Task`, `Contact` dataclasses.

> Note: the sibling `.md` docs (`google.md`, `outlook.md`, `meetings.md`) carry `status: scaffold` / "planned" surfaces and list some symbols that are aspirational, not yet wired up. In particular `google.md` advertises a Gmail/Calendar/RAG surface (`search_emails`, `get_today_schedule`, `find_free_slots`, `ingest_doc_to_kb`, `scope_for_project`, `as_context_passages`) that the code does **not** export today: the `google` subpackage ships only auth + Docs + Sheets + Drive, there is no `calendar` module, and the lone `gmail.py` exposes a single `send_email` helper that is **not** re-exported from `vaultlab.context.google`. This README lists what is actually exported by the code today; treat the `.md` files as design intent, not the current API.

## How it fits

`vaultlab.context` sits *underneath* the rest of vaultlab as the addressing layer:

- **`resolve_kb_root` is upstream of everything.** Per the first-encounter checklist in `CLAUDE.md`, an agent resolves the KB root before invoking any primitive; orchestrators, the CLI, and slash commands all call it to find where to read/write. In this repo the slash commands that open with `from vaultlab.context import resolve_kb_root` include `/lit-arc`, `/lit-arc-next`, `/lit-report`, `/papers-index`, `/onboard-me`, `/onboard-project`, `/start-project`, `/build-deck`, `/find-analogs`, `/full-reader`, `/next-analysis`, `/run-analysis`, and `/understand-figure` — i.e. essentially every artifact-producing primitive.
- **The `vaultlab init` CLI subcommand is the write-side entry point.** `vaultlab init` (no-arg) runs the first-run prompt via `resolve_kb_root(interactive=True)`; `vaultlab init <path>` skips the prompt and calls `register_path("paths.kb_root", <path>)` directly. Either way the choice persists to `locations.toml` so the prompt fires exactly once per machine. This is the one CLI surface this package backs.
- **`/link-repo` is the write-side entry point for the linked-code pipe.** The `/link-repo <path>` slash command calls `set_linked_repo` to store the repo path in `.vaultlab-project.json`, after which crosstalk meetings read its files + recent commits via `list_files` / `read_file` / `list_recent_changes`.
- **The locations registry feeds the companion pipes.** Companion slash commands / skills (e.g. `/brief`, `/update`, `/weekly`, `/eod`) read named paths (work-log doc ID, transcript folders) from `locations.toml` rather than re-asking. When a needed slug is absent, `missing_paths_grill_doc` queues the question as a grill doc instead of blocking the chat.
- **The companion pipes write back into the KB.** `meetings.ingest_transcript` lands transcripts in `<kb>/Sources/Meetings/`; the Google/Outlook pipes surface email/calendar/doc content into prompts. From there the normal KB index + retrieval pick them up.
- **`code` bridges into crosstalk meetings.** It lets a researcher's own repo + data feed the multi-agent reasoning machinery without first converting everything into KB notes.
- **`user_memory` is read on session start.** `recall_all()` seeds the always-loaded calibration summary so the system doesn't relearn preferences each chat.

Config lives under `~/.config/vaultlab/` (`locations.toml`, `user_memory/`, `google/`, `outlook/`) — per-user, per-machine, never committed.

## What it does NOT do

- It does **not** auto-create the KB directory. `resolve_kb_root` returns a path that may or may not exist on disk; the read side never magic-creates folders.
- It does **not** continuously monitor your inbox, calendar, or meetings. Every Google/Outlook read is initiated by an explicit slash command or RAG query, not a background indexer.
- It does **not** embed or proxy any credentials. Google OAuth tokens, Outlook's signed-in COM session, and transcription API keys all stay on the user's machine; the companion pipes never ship keys through vaultlab.
- It does **not** run your code. The `code` pipe surfaces files and git history for meeting context; executing scripts is the user-side Claude Code session's job, not this layer's.
- It does **not** police accuracy or compliance. Enabling a pipe over a mailbox/account holding PHI / IRB-restricted data is the user's call — see `docs/compliance.md`.

## Files

- `__init__.py` — slim barrel re-exporting the locations registry + KB-root resolver only.
- `locations.py` — `locations.toml` reader/writer, dotted-slug lookups, the `resolve_kb_root` resolution chain, and the `bobby_kb` compat bridge.
- `user_memory.py` — per-user auto-memory store + `MEMORY.md` index maintenance.
- `code/__init__.py` — linked-repo feature (config read/write + git/file surfacing).
- `meetings/__init__.py` — `meeting_recorder` launcher + transcript ingest/query. `meetings.md` is the companion design doc.
- `google/` — Workspace integration (`auth.py`, `docs.py`, `sheets.py`, `drive.py`). `google.md` is the companion design doc.
- `outlook/` — Outlook Classic COM integration (`email.py`, `calendar.py`, `tasks.py`, `contacts.py`, `models.py`, `_connection.py`, `_constants.py`, `_converters.py`). `outlook.md` is the companion design doc.

## See also

- [`docs/architecture.md`](../../../docs/architecture.md) — `### vaultlab.context` and the system data-flow diagram.
- `Wiki/Concepts/vaultlab-subsystems.md` (KB) — the plain-language tour of the knowledge base, onboarding/setup, and context layers.
- `CLAUDE.md` — the first-encounter checklist (where `resolve_kb_root` / `KbRootNotConfigured` enter), Invariant 7 (context preservation), and the per-user auto-memory section.
- `vaultlab.kb` — the KB whose root this package resolves and into which the companion pipes write.
- `vaultlab.onboarding` — `.vaultlab-project.json` config loading that the `code` pipe reads/writes.
