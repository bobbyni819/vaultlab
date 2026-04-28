---
name: onboard-project
type: orchestrated
backed_by: vaultlab.kb + vaultlab.runner.bounded_loop
purpose: Walk vaultlab through a new project so it knows what's there + what to read first
---

# /onboard-project [path]

When you point vaultlab at a new project (a folder with code, data, papers, notes), it doesn't know what's in there yet. This command does the discovery + verification flow so vaultlab can then act as a competent companion for that project.

## What it does

1. **Walk the folder structure** — list directories, count files by type, identify large directories
2. **Read top-level docs** — README, CLAUDE.md, docs/, any .vaultlab-project.json
3. **Identify file types and patterns** — Python source, Jupyter notebooks, data files (.h5ad, .tiff, .csv), figure outputs, manuscripts
4. **Build a draft project understanding** — written to `<kb>/Wiki/Projects/<slug>.md`
5. **Run grill-me verification** — pose 5-10 questions to the human about things vaultlab can't infer (the science, the conventions, the priorities)
6. **Update the human-answered understanding** into the project page
7. **Initialize `<kb>/Wiki/Projects/<slug>/START_HERE.md`** with current state + suggested next-step files to read
8. **Suggest a `.vaultlab-project.json`** if one doesn't exist (data sources, validation files, KB path)

## Inputs

- `path` (optional): project root directory. Defaults to current working directory.
- `--name <slug>`: project slug (default: derived from folder name)
- `--kb <name>`: which KB to write the project page into (default: from vaultlab config)
- `--skip-grill`: skip the verification grill (faster but less accurate)

## Outputs

```
<kb>/Wiki/Projects/<slug>.md                # canonical understanding
<kb>/Wiki/Projects/<slug>/START_HERE.md     # current focus + files to read
<project>/.vaultlab-project.json            # config (if didn't exist)
```

## Implementation

```python
from pathlib import Path

from vaultlab.kb import get_kb_path, ingest_file
from vaultlab.kb.start_here import init_start_here, update_start_here
from vaultlab.runner.bounded_loop import bounded_loop
from vaultlab.workflows import onboard

def main(path: Path, name: str | None = None, skip_grill: bool = False):
    kb_path = get_kb_path()
    slug = name or path.name.lower().replace(" ", "_")

    # Step 1-3: walk + identify
    inventory = onboard.scan_project(path)

    # Step 4: build draft understanding (Claude reads + summarizes)
    draft = onboard.draft_understanding(inventory, kb_path=kb_path)

    # Step 5: verification grill (skip-able)
    if not skip_grill:
        questions = onboard.compose_grill_questions(draft, inventory)
        # Saves to <kb>/Wiki/Projects/<slug>/onboarding-grill.md
        # Human answers later; on next /onboard-project run, answers get folded in
        onboard.write_grill(kb_path, slug, questions)

    # Step 6: write the project page
    onboard.write_project_page(kb_path, slug, draft)

    # Step 7: initialize START_HERE
    init_start_here(kb_path, slug, draft, suggested_files=onboard.priority_files(inventory))

    # Step 8: suggest .vaultlab-project.json
    if not (path / ".vaultlab-project.json").exists():
        onboard.suggest_project_config(path, slug, inventory)

    return {"slug": slug, "kb_page": kb_path / "Wiki/Projects" / f"{slug}.md"}
```

## Anti-laziness rules (per AGENTS.md)

When Claude reads files for the draft understanding:
1. QUOTE specific filenames + their purpose
2. If unsure what a file is for, mark it `[unknown — ask user]` rather than guessing
3. Hedge interpretations: *"`pipeline/run_codex.py` appears to be the main analysis driver"* not *"`run_codex.py` is the main driver"*
4. Don't fabricate dependencies — only list what's actually in `pyproject.toml` / `requirements.txt`

## Test plan

- [ ] Run on `~/Downloads/CODEX_MALDIIMS/` — should produce a draft that recognizes the lipid-annotation pipeline
- [ ] Run on a freshly-created empty folder — should produce a minimal draft suggesting next steps
- [ ] Verify the grill questions are answerable by Bobby in <5 minutes (not 50 questions)
- [ ] Verify START_HERE.md has actionable "files to read first"
- [ ] Verify .vaultlab-project.json suggestion is valid JSON

## Related commands

- `/discover-data <path>` — narrower; just for wet-lab data folders
- `/research-status` — once a project is onboarded, this shows current focus
- `/groom-kb` — periodically tidies the KB; complements onboarding
