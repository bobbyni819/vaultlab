"""Trial run for the onboarding scaffolding.

Creates a temp project folder with a filled-in ``project_intake.md``,
runs ``init_project_from_intake`` against a temp KB, and prints what
landed where + a preview of the ``.vaultlab-project.json`` content.

Run from the vaultlab repo root:

    python scripts/_trial_onboarding.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

# Allow `python scripts/_trial_onboarding.py` from repo root
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from vaultlab.onboarding import (  # noqa: E402
    IntakeForm,
    init_project_from_intake,
    load_config,
)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="vaultlab_trial_onboard_"))
    print(f"Trial sandbox: {tmp}")

    project_path = tmp / "codex-pdac-cn"
    project_path.mkdir()
    kb_root = tmp / "kb"
    kb_root.mkdir()

    # Synthetic project content
    (project_path / "README.md").write_text(
        "# CODEX PDAC CN\n\nSpatial neighborhoods.\n", encoding="utf-8"
    )
    (project_path / "analysis.py").write_text("# placeholder\n", encoding="utf-8")
    (project_path / "exploration.ipynb").write_text("{}", encoding="utf-8")
    (project_path / "data").mkdir()
    (project_path / "data" / "expression.h5ad").write_bytes(b"")
    (project_path / "data" / "annotations.csv").write_text(
        "cell_id,cluster\n1,A\n", encoding="utf-8"
    )
    (project_path / "papers").mkdir()
    (project_path / "papers" / "Schurch2020.pdf").write_bytes(b"")

    # Filled intake
    form = IntakeForm(
        topic="CODEX cellular neighborhoods in PDAC",
        goals=["understand_literature", "build_journal_club_deck"],
        audiences=["pi", "journal_club"],
        have=["wet_lab_data", "pdfs"],
        exclusions={"exclude_preprints": True, "min_year": 2015},
        style=["hedged"],
        pi_preferences="John prefers author-year style; flagged superscript clutter",
        deadlines=["weekly"],
        free_form="Aim 3 of thesis. Need lineage arc + journal club by month-end.",
    )
    intake_path = project_path / "project_intake.md"
    intake_path.write_text(form.to_markdown(), encoding="utf-8")
    print(f"Wrote intake form: {intake_path}")

    # Run the orchestrator
    result = init_project_from_intake(intake_path, kb_root, project_path)

    print()
    print(f"Resolved slug: {result.slug}")
    print(f"Inventory: {result.inventory.total_files} files classified")
    for cat, n in sorted(
        result.inventory.counts.items(), key=lambda kv: -kv[1]
    ):
        print(f"  - {cat}: {n}")

    print()
    print("Files written:")
    for p in result.files_written():
        rel = p.relative_to(tmp) if str(p).startswith(str(tmp)) else p
        print(f"  - {rel}  ({p.stat().st_size} bytes)")

    expected = 4
    actual = len(result.files_written())
    if actual != expected:
        print(f"FAIL: expected {expected} files, got {actual}")
        return 1
    print(f"OK: {actual}/{expected} expected files written")

    # Preview .vaultlab-project.json
    print()
    print("--- .vaultlab-project.json ---")
    cfg = load_config(project_path)
    assert cfg is not None
    print(json.dumps(cfg.to_dict(), indent=2))

    # Preview START_HERE.md (first 30 lines)
    print()
    print("--- START_HERE.md preview ---")
    sh = result.start_here_path
    assert sh is not None
    body = sh.read_text(encoding="utf-8").splitlines()
    for line in body[:30]:
        print(line)
    if len(body) > 30:
        print(f"... ({len(body) - 30} more lines)")

    # Follow-up questions
    print()
    print("--- Follow-up questions for slash command to ask ---")
    for i, q in enumerate(result.follow_up_questions, 1):
        print(f"  {i}. {q}")

    # Cleanup
    shutil.rmtree(tmp, ignore_errors=True)
    print()
    print("Trial complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
