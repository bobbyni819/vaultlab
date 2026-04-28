# Template: tool index entry

To document a Python package in vaultlab's tool index (so the LLM knows when to use it):

1. Copy `tool.md` to `src/vaultlab/kb/tools_index/<tool_name>.md`
2. Fill in: what it does, when to use, gotchas, link to docs
3. The LLM consults this index when picking tools for a user request

## `tool.md` template

```markdown
---
tool: <package-name>
modality: <e.g., scrnaseq, spatial, imaging, stats, general>
import_from: <e.g., scanpy>
canonical_use: <one-line>
heaviness: <light | medium | heavy>
---

# <package-name>

## What it does

(2-3 sentences)

## When to use it (vs alternatives)

- Use when: <case>
- Don't use when: <case>
- Alternatives: <other tools that overlap>

## Quick example

```python
import <package> as <alias>
# minimal example
```

## Gotchas

- (any pitfalls)

## Links

- Docs: <URL>
- GitHub: <URL>
- Paper: <DOI>
```
