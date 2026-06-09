"""Tests for `vaultlab claude validate` (slash-command frontmatter linter)."""

from __future__ import annotations

from pathlib import Path

from vaultlab.cli.claude import _parse_frontmatter, main, validate_commands


def _cmd(dir_: Path, name: str, text: str) -> None:
    (dir_ / name).write_text(text, encoding="utf-8")


def test_parse_frontmatter_basic():
    fm = _parse_frontmatter("---\nname: foo\ntype: pure-capability\n---\n\n# body\n")
    assert fm == {"name": "foo", "type": "pure-capability"}
    assert _parse_frontmatter("# no frontmatter") is None


def test_validate_flags_problems(tmp_path: Path):
    d = tmp_path / "commands"
    d.mkdir()
    _cmd(d, "good.md", "---\nname: good\n---\n\n# Good\n\nDoes a thing.\n")
    _cmd(d, "noname.md", "---\ntype: pure\n---\n\n# body\n")
    _cmd(d, "nofm.md", "# just a heading, no frontmatter\n")
    _cmd(d, "mismatch.md", "---\nname: other\n---\n\n# body\n")
    _cmd(d, "empty.md", "---\nname: empty\n---\n")
    _cmd(d, "README.md", "index, not a command")  # skipped

    results = {p.name: probs for p, _name, probs in validate_commands(d)}
    assert "README.md" not in results  # index files skipped
    assert results["good.md"] == []
    assert any("missing 'name'" in p for p in results["noname.md"])
    assert any("missing YAML frontmatter" in p for p in results["nofm.md"])
    assert any(p.startswith("warn:") for p in results["mismatch.md"])  # name != stem = warn
    assert any("empty body" in p for p in results["empty.md"])


def test_main_validate_returns_nonzero_on_hard_failure(tmp_path: Path, monkeypatch, capsys):
    d = tmp_path / ".claude" / "commands"
    d.mkdir(parents=True)
    _cmd(d, "bad.md", "# no frontmatter\n")
    monkeypatch.chdir(tmp_path)
    assert main(["validate"]) == 1
    assert "FAIL bad.md" in capsys.readouterr().out


def test_main_validate_passes_clean(tmp_path: Path, monkeypatch, capsys):
    d = tmp_path / ".claude" / "commands"
    d.mkdir(parents=True)
    _cmd(d, "ok.md", "---\nname: ok\n---\n\n# Ok\n\nbody\n")
    monkeypatch.chdir(tmp_path)
    assert main(["validate"]) == 0
    assert "1/1 command files valid" in capsys.readouterr().out


def test_main_list(tmp_path: Path, monkeypatch, capsys):
    d = tmp_path / ".claude" / "commands"
    d.mkdir(parents=True)
    _cmd(d, "alpha.md", "---\nname: alpha\n---\n\nbody\n")
    monkeypatch.chdir(tmp_path)
    assert main(["validate", "--list"]) == 0
    assert "/alpha" in capsys.readouterr().out


def test_unknown_subcommand(capsys):
    assert main(["frobnicate"]) == 1
    assert "unknown subcommand" in capsys.readouterr().err
