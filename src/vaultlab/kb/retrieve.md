---
name: vaultlab-kb-retrieve
description: >-
  Layered retrieval cascade for vaultlab KBs — corpus, frontmatter,
  auto-indexes, wikilink walk, cumulative recall. Use this skill whenever a
  vaultlab primitive needs to assemble context from a KB the way a human
  researcher with deep project knowledge would.
---

# vaultlab.kb retrieval cascade

> Binding feedback memory: `feedback_researcher_pathway_thinking` — every
> primitive uses layered retrieval simulating a human researcher with deep
> project knowledge. "Agent reads 3 things" is too narrow.

This skill documents the five-layer retrieval cascade. Pull from layers in
order until you have enough context; the layers are deliberately ordered
from cheapest + most precise (frontmatter) to most expensive + most fuzzy
(embedding search).

## The cascade

```
1.  Corpus            — paperclip MCP, full-text PDF/HTML corpus,
                        cumulative summaries folder.
2.  Frontmatter       — vaultlab.kb.retrieve_by_frontmatter(filter, kb_root)
                        Structured lookup by type / project / donor / status.
3.  Indexes           — _Index.md (by type), _Catalog.md (chronological),
                        _BackLinks.md (bidirectional wikilink map).
4.  Wikilink walk     — follow [[Target]] edges from a seed page; useful
                        for citation graphs and lineage arcs.
5.  Cumulative recall — vaultlab.kb.semantic_search.search(...) + the
                        `corpus_recall.gather_relevant_summaries` helper.
```

Each layer narrows or expands the candidate set. A typical primitive runs:

1. **Filter structurally first** (layer 2) — e.g. "all Wiki/Summaries for the
   metabolism project". This is the cheapest, most precise narrow.
2. **Consult the indexes** (layer 3) — `_Index.md` gives a typed overview,
   `_Catalog.md` shows recency, `_BackLinks.md` reveals what else points to
   each candidate. Indexes are auto-regenerated from frontmatter + wikilink
   scanning; they're never hand-maintained.
3. **Walk wikilinks** (layer 4) — from a seed candidate, follow `[[Target]]`
   edges N hops out. The reverse direction comes free from `_BackLinks.md`.
4. **Fall through to semantic search** (layer 5) — when frontmatter +
   wikilinks haven't surfaced the right page (e.g. the user's query uses
   different vocabulary than the KB), `vaultlab.kb.semantic_search.search`
   does TF-IDF or embedding ranking over markdown bodies.
5. **Always merge cumulative recall** — for narrative arcs and decks, merge
   `Wiki/Summaries` with this-run picks via
   `corpus_recall.gather_relevant_summaries`. Default to MORE context, not
   less (per the `feedback_dont_skimp_tokens_max_detail` memory).

## API

```python
from pathlib import Path
from vaultlab.kb import retrieve_by_frontmatter, build_indexes

# Layer 2 — structured filter
wiki_notes = retrieve_by_frontmatter(
    {"type": "wiki", "project": "metabolism"},
    kb_root=Path("G:/My Drive/Knowledge/metabolism"),
)

# OR within a key: any note tagged 'lipidomics' or 'maldi'
tagged = retrieve_by_frontmatter(
    {"tags": {"lipidomics", "maldi"}},
    kb_root=Path("G:/My Drive/Knowledge/metabolism"),
)

# Layer 3 — refresh the auto-indexes
paths = build_indexes(Path("G:/My Drive/Knowledge/metabolism"))
# paths == {"index": .../"_Index.md", "catalog": .../"_Catalog.md",
#           "backlinks": .../"_BackLinks.md"}
```

## Filter semantics

| Filter clause | Match condition |
|---|---|
| `{"type": "wiki"}` | `meta["type"] == "wiki"` |
| `{"type": {"wiki", "paper"}}` | `meta["type"] in {"wiki", "paper"}` (OR) |
| `{"type": "wiki", "donor": "D1"}` | both clauses (AND) |
| `{"tags": "lipidomics"}` | `"lipidomics" in meta["tags"]` if list, else `==` |
| `{"tags": {"lipidomics", "maldi"}}` | any tag in set |

Files without YAML frontmatter are silently skipped — this primitive only
covers the structured layer. Use `vaultlab.kb.semantic_search.search` for
unfrontmattered notes.

## What gets indexed

`build_indexes` walks every `.md` file under `kb_root` except:

- The three index files themselves (`_Index.md`, `_Catalog.md`,
  `_BackLinks.md`) — they're outputs, not inputs.
- Anything under a dotfile directory (`.obsidian/`, `.embeddings/`, etc.).
- Files whose YAML frontmatter fails to parse (treated as "no metadata").

`_Index.md` and `_Catalog.md` only list files that *have* frontmatter.
`_BackLinks.md` ALSO scans bodies of unfrontmattered files for `[[Target]]`
references so a scratch note can still surface as a referrer.

## Provenance

`build_indexes` and `retrieve_by_frontmatter` are reads / index-builds, not
artifact writes — they do NOT produce a `.audit.json` companion manifest.
That contract is reserved for primitives that materialize new analytic
artifacts (decks, reports, lineage arcs).

## Wikilink resolution rules

- Pattern: `[[Target]]`, `[[Target|Alias]]`, `[[Target#Section]]`,
  `[[Target#Section|Alias]]`.
- Backlinks resolve to the **target stem only** — section anchors and
  aliases are display-only.
- Self-references (`[[foo]]` appearing in `foo.md`) are not recorded as
  backlinks.
- Targets are matched case-sensitively (Obsidian default).
