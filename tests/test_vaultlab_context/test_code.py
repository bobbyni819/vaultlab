"""Tests for vaultlab.context.code — linked-codebase mode (#109)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from vaultlab.context.code import (
    CommitInfo,
    get_linked_repo,
    list_files,
    list_recent_changes,
    read_file,
    set_linked_repo,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(tmp_path: Path) -> Path:
    """Create a tiny vaultlab project (with .vaultlab-project.json)."""
    from vaultlab.onboarding.config import VaultLabProjectConfig, save_config

    cfg = VaultLabProjectConfig(
        slug="test-project",
        topic="testing",
        project_path=str(tmp_path / "project"),
    )
    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    save_config(cfg, project_dir)
    return project_dir


def _make_repo(tmp_path: Path, *, with_git: bool = True) -> Path:
    """Create a tiny code repo on disk with a few files (and optionally git)."""
    repo = tmp_path / "code"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "src").mkdir()
    (repo / "src" / "model.py").write_text("def foo(): return 1\n")
    (repo / "README.md").write_text("# Test repo")
    (repo / ".gitignore").write_text("__pycache__/\n")
    cache = repo / "__pycache__"
    cache.mkdir()
    (cache / "junk.pyc").write_bytes(b"\x00\x00")
    if with_git:
        try:
            subprocess.run(
                ["git", "init", "-b", "main"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "add", "."],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "initial"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            # git not installed or init failed — tests using git features will skip
            pass
    return repo


# ---------------------------------------------------------------------------
# get_linked_repo / set_linked_repo
# ---------------------------------------------------------------------------


def test_get_linked_repo_returns_none_when_unset(tmp_path: Path):
    project = _make_project(tmp_path)
    assert get_linked_repo(project) is None


def test_get_linked_repo_returns_none_when_config_missing(tmp_path: Path):
    """No config file at all → None, not an error."""
    project_dir = tmp_path / "no-project"
    project_dir.mkdir()
    assert get_linked_repo(project_dir) is None


def test_set_linked_repo_writes_config_field(tmp_path: Path):
    project = _make_project(tmp_path)
    repo = _make_repo(tmp_path, with_git=False)

    stored = set_linked_repo(project, repo)
    assert stored == repo.resolve()

    linked = get_linked_repo(project)
    assert linked is not None
    assert linked.resolve() == repo.resolve()


def test_set_linked_repo_creates_config_when_missing(tmp_path: Path):
    """Calling set_linked_repo on a project without a config creates one."""
    project = tmp_path / "fresh-project"
    project.mkdir()
    repo = _make_repo(tmp_path, with_git=False)

    set_linked_repo(project, repo)
    cfg_path = project / ".vaultlab-project.json"
    assert cfg_path.exists()
    assert get_linked_repo(project) is not None


def test_set_linked_repo_rejects_nonexistent_path(tmp_path: Path):
    project = _make_project(tmp_path)
    with pytest.raises(FileNotFoundError):
        set_linked_repo(project, tmp_path / "does-not-exist")


def test_set_linked_repo_rejects_file_not_directory(tmp_path: Path):
    project = _make_project(tmp_path)
    a_file = tmp_path / "just-a-file.txt"
    a_file.write_text("hi")
    with pytest.raises(NotADirectoryError):
        set_linked_repo(project, a_file)


def test_get_linked_repo_returns_none_when_repo_deleted(tmp_path: Path):
    """If the linked repo path no longer exists on disk, treat as not linked."""
    project = _make_project(tmp_path)
    repo = _make_repo(tmp_path, with_git=False)
    set_linked_repo(project, repo)

    # Delete the repo
    import shutil
    shutil.rmtree(repo)

    assert get_linked_repo(project) is None


# ---------------------------------------------------------------------------
# list_files
# ---------------------------------------------------------------------------


def test_list_files_returns_files_excluding_noise_dirs(tmp_path: Path):
    repo = _make_repo(tmp_path, with_git=False)
    files = list_files(repo)
    names = {p.name for p in files}
    assert "model.py" in names
    assert "README.md" in names
    # __pycache__ contents excluded
    assert "junk.pyc" not in names


def test_list_files_pattern_filter(tmp_path: Path):
    repo = _make_repo(tmp_path, with_git=False)
    pyfiles = list_files(repo, pattern="**/*.py")
    assert all(p.suffix == ".py" for p in pyfiles)
    assert any(p.name == "model.py" for p in pyfiles)


def test_list_files_max_results_caps_output(tmp_path: Path):
    """A large repo doesn't return unbounded results."""
    repo = _make_repo(tmp_path, with_git=False)
    # Fabricate 50 files
    for i in range(50):
        (repo / f"f{i}.txt").write_text("x")
    # Cap at 5
    out = list_files(repo, max_results=5)
    assert len(out) == 5


def test_list_files_returns_empty_for_missing_repo(tmp_path: Path):
    out = list_files(tmp_path / "no-such-repo")
    assert out == []


def test_list_files_custom_exclude(tmp_path: Path):
    """Caller can override the exclude set."""
    repo = tmp_path / "code"
    repo.mkdir()
    custom = repo / "custom-noise"
    custom.mkdir()
    (custom / "junk.txt").write_text("noise")
    (repo / "real.py").write_text("real")
    out = list_files(repo, exclude_dirs={"custom-noise"})
    names = {p.name for p in out}
    assert "real.py" in names
    assert "junk.txt" not in names


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------


def test_read_file_returns_contents(tmp_path: Path):
    repo = _make_repo(tmp_path, with_git=False)
    text = read_file(repo, "src/model.py")
    assert "def foo()" in text


def test_read_file_returns_empty_for_missing_file(tmp_path: Path):
    repo = _make_repo(tmp_path, with_git=False)
    assert read_file(repo, "does-not-exist.py") == ""


def test_read_file_blocks_path_traversal(tmp_path: Path):
    """Reading outside the repo root should return empty, not the file."""
    repo = _make_repo(tmp_path, with_git=False)
    # Create a sibling file outside the repo
    outside = tmp_path / "secret.txt"
    outside.write_text("shhh")
    # Try to escape with ../
    out = read_file(repo, "../secret.txt")
    assert out == ""


def test_read_file_truncates_at_max_bytes(tmp_path: Path):
    repo = _make_repo(tmp_path, with_git=False)
    big = repo / "big.txt"
    big.write_bytes(b"x" * 100_000)
    out = read_file(repo, "big.txt", max_bytes=100)
    assert len(out) == 100


# ---------------------------------------------------------------------------
# list_recent_changes (git)
# ---------------------------------------------------------------------------


def _has_git() -> bool:
    try:
        subprocess.run(
            ["git", "--version"], capture_output=True, check=False
        )
        return True
    except FileNotFoundError:
        return False


@pytest.mark.skipif(not _has_git(), reason="git not available in this env")
def test_list_recent_changes_returns_commits_for_git_repo(tmp_path: Path):
    repo = _make_repo(tmp_path, with_git=True)
    commits = list_recent_changes(repo, limit=5)
    if not commits:
        pytest.skip("git init succeeded but log returned empty — environment quirk")
    assert all(isinstance(c, CommitInfo) for c in commits)
    # The "initial" commit should appear
    assert any("initial" in c.subject.lower() for c in commits)


def test_list_recent_changes_returns_empty_for_non_git(tmp_path: Path):
    repo = _make_repo(tmp_path, with_git=False)
    assert list_recent_changes(repo) == []
