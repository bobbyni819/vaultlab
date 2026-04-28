# Template: agent role

To add a new agent role to vaultlab:

1. Copy this directory to `src/vaultlab/roles/<role_name>/`
2. Fill in `role.py` (thin loader; ~15 lines) and `prompt.md` (the actual prompt content)
3. Register the role in `src/vaultlab/roles/__init__.py`
4. Add to `tests/test_vaultlab/test_role_invariants.py`
5. Run `pytest tests/test_vaultlab/test_role_invariants.py`

## Required files

```
<role_name>/
  role.py        # Thin Python loader
  prompt.md      # The prompt content (markdown)
```

## `role.py` template

```python
from pathlib import Path
from vaultlab.roles._loader import Role, load_prompt

ROLE = Role(
    name="<role_name>",
    focus="<one-line focus area>",
    applicable_modes=[<Mode.X>, <Mode.Y>],
    prompt=load_prompt(__file__),
    temperature=0.0,  # or 0.7 for creative
    tools=[<tool list>],
)
```

## `prompt.md` requirements

Per AGENTS.md (Invariants 7 + the anti-laziness rules):

- **Required frontmatter:** `role`, `mode`, `temperature`
- **Required sections:** "Your role", "Anti-laziness rules", "Process", "Output format"
- **The 4 anti-laziness rules** must appear verbatim or be strengthened, never softened
- **Hedged voice** must be enforced for any interpretation/hypothesis output

## Reference roles

See existing roles in `src/vaultlab/roles/` for patterns (once migration commits land).
