"""Tests for ``scripts/_normalize_unicode_source_yaml.py``.

The script is a one-shot data-hygiene cleanup, but the helpers
(:func:`normalize_string`, :func:`normalize_yaml_value`,
:func:`normalize_summary_file`, :func:`sweep_kb_summaries`) are pure
and worth pinning so future runs (or accidental edits) can't reintroduce
mixed-Unicode source YAML. See evening-5 / Round 2 audit log Finding 8
(2026-04-30) for context.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# -----------------------------------------------------------------------------
# Module loader — the script lives under ``scripts/`` (not in any package), so
# we load it via importlib so the tests can exercise its helpers directly.
# -----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def normalize_module():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "_normalize_unicode_source_yaml.py"
    spec = importlib.util.spec_from_file_location("_normalize_unicode_source_yaml", script_path)
    assert spec and spec.loader, f"Could not load {script_path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_normalize_unicode_source_yaml"] = mod
    spec.loader.exec_module(mod)
    return mod


# -----------------------------------------------------------------------------
# normalize_string / normalize_yaml_value
# -----------------------------------------------------------------------------


def test_normalize_unicode_replaces_u2010_in_authors(normalize_module):
    """U+2010 HYPHEN ('Kennedy‐Darling') must become ASCII '-'."""
    raw = "Kennedy‐Darling"
    out, counts = normalize_module.normalize_string(raw)
    assert out == "Kennedy-Darling"
    assert counts["‐"] == 1


def test_normalize_unicode_replaces_all_four_hyphens(normalize_module):
    """All four target Unicode hyphens get normalized."""
    raw = "a‐b–c—d−e"
    out, counts = normalize_module.normalize_string(raw)
    assert out == "a-b-c-d-e"
    assert counts["‐"] == 1
    assert counts["–"] == 1
    assert counts["—"] == 1
    assert counts["−"] == 1


def test_normalize_unicode_idempotent(normalize_module):
    """Running normalize twice on the same input is a no-op the second time."""
    raw = "Kennedy‐Darling and J. K—L"
    once, c1 = normalize_module.normalize_string(raw)
    twice, c2 = normalize_module.normalize_string(once)
    assert once == twice == "Kennedy-Darling and J. K-L"
    assert sum(c1.values()) > 0
    assert sum(c2.values()) == 0  # second pass: nothing left to fix


def test_normalize_unicode_preserves_other_content(normalize_module):
    """Other non-ASCII characters (Greek, accented Latin, ASCII -) are untouched."""
    raw = "β-catenin Café résumé Kennedy‐Darling"
    out, counts = normalize_module.normalize_string(raw)
    assert out == "β-catenin Café résumé Kennedy-Darling"
    # ASCII '-' is preserved; the only replacement is the U+2010.
    assert counts["‐"] == 1
    # Everything else is byte-identical.
    assert "β" in out
    assert "Café" in out
    assert "résumé" in out


def test_normalize_yaml_value_recurses_into_lists_and_dicts(normalize_module):
    """``authors`` is a list of strings; ``title`` is a string; both must normalize."""
    fm = {
        "doi": "10.1/example",
        "title": "A study by Kennedy‐Darling et al.",
        "authors": ["Kennedy‐Darling J", "L—pez R"],
        "year": 2020,
        "nested": {"journal": "Nat Methods–Online"},
    }
    out, counts = normalize_module.normalize_yaml_value(fm)
    assert out["doi"] == "10.1/example"
    assert out["title"] == "A study by Kennedy-Darling et al."
    assert out["authors"] == ["Kennedy-Darling J", "L-pez R"]
    assert out["year"] == 2020  # unchanged scalar
    assert out["nested"] == {"journal": "Nat Methods-Online"}
    # Counts cover all replaced occurrences across the structure.
    assert counts["‐"] == 2  # title + first author
    assert counts["—"] == 1  # second author
    assert counts["–"] == 1  # nested.journal


# -----------------------------------------------------------------------------
# normalize_summary_file (filesystem)
# -----------------------------------------------------------------------------


def _write_summary(path: Path, *, frontmatter: str, body: str = "## TL;DR\nfoo\n") -> None:
    text = f"---\n{frontmatter}---\n{body}"
    path.write_text(text, encoding="utf-8")


def test_normalize_summary_file_rewrites_yaml_frontmatter(normalize_module, tmp_path: Path):
    """File with U+2010 in authors gets rewritten in place; body untouched."""
    f = tmp_path / "10.1_example.md"
    _write_summary(
        f,
        frontmatter=(
            "doi: 10.1/example\ntitle: Example\nauthors:\n- Kennedy‐Darling J\nyear: 2020\n"
        ),
        body="## TL;DR\nThe Kennedy‐Darling study showed...\n",
    )
    changed, counts = normalize_module.normalize_summary_file(f)
    assert changed is True
    assert counts["‐"] >= 1
    new_text = f.read_text(encoding="utf-8")
    # Frontmatter normalized.
    assert "Kennedy-Darling J" in new_text
    # Body normalization is out of scope — the body keeps the U+2010 because
    # only YAML frontmatter is rewritten. Verify that explicitly so we don't
    # accidentally over-step.
    assert "Kennedy‐Darling study" in new_text


def test_normalize_summary_file_idempotent_on_clean_file(normalize_module, tmp_path: Path):
    """Clean file is byte-identical after a sweep (no write at all)."""
    f = tmp_path / "10.1_clean.md"
    _write_summary(
        f,
        frontmatter="doi: 10.1/clean\ntitle: Clean Title\nauthors:\n- Smith J\nyear: 2020\n",
    )
    before_mtime = f.stat().st_mtime_ns
    before_bytes = f.read_bytes()
    changed, counts = normalize_module.normalize_summary_file(f)
    assert changed is False
    assert sum(counts.values()) == 0
    # File on disk is byte-identical (and we didn't even rewrite it).
    assert f.read_bytes() == before_bytes
    assert f.stat().st_mtime_ns == before_mtime


def test_normalize_summary_file_idempotent_after_first_pass(normalize_module, tmp_path: Path):
    """Run twice on a dirty file: first pass changes, second is a no-op."""
    f = tmp_path / "10.1_dirty.md"
    _write_summary(
        f,
        frontmatter=("doi: 10.1/dirty\nauthors:\n- Kennedy‐Darling J\nyear: 2020\n"),
    )
    changed1, counts1 = normalize_module.normalize_summary_file(f)
    assert changed1 is True
    assert counts1["‐"] == 1
    changed2, counts2 = normalize_module.normalize_summary_file(f)
    assert changed2 is False
    assert sum(counts2.values()) == 0


def test_normalize_summary_file_respects_dry_run(normalize_module, tmp_path: Path):
    """Dry-run reports changes but does not touch the file."""
    f = tmp_path / "10.1_dryrun.md"
    _write_summary(
        f,
        frontmatter="doi: 10.1/dryrun\nauthors:\n- A‐B\nyear: 2020\n",
    )
    before_bytes = f.read_bytes()
    changed, counts = normalize_module.normalize_summary_file(f, dry_run=True)
    assert changed is True
    assert counts["‐"] == 1
    assert f.read_bytes() == before_bytes  # untouched


def test_normalize_summary_file_skips_no_frontmatter(normalize_module, tmp_path: Path):
    """File with no ``---`` frontmatter is left alone."""
    f = tmp_path / "no_frontmatter.md"
    f.write_text("# Just a heading\n\nKennedy‐Darling is here.\n", encoding="utf-8")
    before = f.read_bytes()
    changed, counts = normalize_module.normalize_summary_file(f)
    assert changed is False
    assert sum(counts.values()) == 0
    assert f.read_bytes() == before


# -----------------------------------------------------------------------------
# sweep_kb_summaries (directory walk)
# -----------------------------------------------------------------------------


def test_sweep_kb_summaries_counts_and_normalizes(normalize_module, tmp_path: Path):
    """Sweep across a faux KB picks up every dirty file and reports counts."""
    summaries = tmp_path / "Wiki" / "Summaries"
    summaries.mkdir(parents=True)

    # Two dirty files, one clean, one with no frontmatter.
    _write_summary(
        summaries / "a.md",
        frontmatter="doi: 10.1/a\nauthors:\n- Kennedy‐Darling J\nyear: 2020\n",
    )
    _write_summary(
        summaries / "b.md",
        frontmatter="doi: 10.1/b\ntitle: A study—B test\nauthors:\n- Smith J\nyear: 2021\n",
    )
    _write_summary(
        summaries / "c-clean.md",
        frontmatter="doi: 10.1/c\nauthors:\n- Smith J\nyear: 2022\n",
    )
    (summaries / "no-fm.md").write_text("# heading only\nKennedy‐Darling here.\n", encoding="utf-8")

    stats = normalize_module.sweep_kb_summaries(tmp_path)
    assert stats["scanned"] == 4
    assert stats["normalized"] == 2
    per_char = stats["per_char"]
    assert per_char["‐"] == 1  # a.md
    assert per_char["—"] == 1  # b.md

    # Re-running is a no-op.
    stats2 = normalize_module.sweep_kb_summaries(tmp_path)
    assert stats2["scanned"] == 4
    assert stats2["normalized"] == 0
    assert sum(stats2["per_char"].values()) == 0


def test_sweep_kb_summaries_handles_missing_dir(normalize_module, tmp_path: Path):
    """Empty/missing ``Wiki/Summaries/`` returns zero stats, not an error."""
    stats = normalize_module.sweep_kb_summaries(tmp_path)
    assert stats == {
        "scanned": 0,
        "normalized": 0,
        "per_char": __import__("collections").Counter(),
        "files": [],
    }
