---
name: vaultlab.research.abstract_recall
description: Thin abstract-recall wrapper. Given a DOI, returns the paper abstract via the federated get_paper. Akin to the metadata-recall step in PaperQA2 — fast, low-cost, no full-text fetch.
---

# vaultlab.research.abstract_recall

Use this module when you need **only the abstract** for a paper identified by DOI —
not the full text, not a structured summary, not a bilingual reading file.

It delegates entirely to `vaultlab.research.get_paper`, which tries PubMed, Semantic
Scholar, Springer, and OpenAlex in turn.

## Public API

```python
from vaultlab.research.abstract_recall import get_abstract_for_doi

abstract = get_abstract_for_doi("10.1038/s41586-023-05915-x")
# -> "Spatial transcriptomics has revealed..." (str)
# -> None  if paper not found, DOI empty, or abstract missing
```

### Signature

```python
def get_abstract_for_doi(doi: str) -> str | None: ...
```

**Args:**

- `doi` — DOI string (e.g. `"10.1038/s41586-023-05915-x"`). Empty / falsy → `None`
  immediately, no network call made.

**Returns:** Abstract text as a plain string, or `None` if the paper is not found or
the abstract field is empty.

## When to use this vs. alternatives

| Need | Use |
| --- | --- |
| Only the abstract | `vaultlab.research.abstract_recall.get_abstract_for_doi` ← **here** |
| A short TL;DR / structured summary with citation stats | `vaultlab.research.summarize.summarize_paper` |
| Full bilingual reading file with figures and anchors | `vaultlab.research.full_reader.build_paper_reader` |
| Citation / DOI verification | `vaultlab.citations` |
| Batched cross-paper synthesis | `vaultlab.research.batched_reader` (planned / not yet implemented) |

## Lineage

PATTERN — mirrors the metadata-recall step in
[PaperQA2 (FutureHouse)](https://github.com/Future-House/paper-qa): fetch abstract
before deciding whether to spend tokens on a full-text retrieval. Thin delegate
rather than reimplementation — all network logic lives in `vaultlab.research.get_paper`.
See INSPIRATIONS.md (PaperQA2 entry).
