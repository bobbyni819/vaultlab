# spec-c-kb-retrieval-upgrade

**Slug:** `spec-c-kb-retrieval-upgrade`
**Status:** in-progress → see EVIDENCE block at bottom
**North-star sub-goal:** 2.2 (SPEC-C — KB retrieval upgrade)
**Plan file:** `.claude/goals/vaultlab-north-star-plan.md` §171

## Outcome

Upgrade `vaultlab.kb` retrieval so every primitive can pull layered context the
way a human researcher with deep project knowledge would — frontmatter-first
filter, auto-generated indexes by `type` and `created`, and bidirectional
wikilink (`[[Target]]`) tracking through `_BackLinks.md`.

Binding feedback memory: `feedback_researcher_pathway_thinking` — "agent reads
3 things" is too narrow. The full cascade is corpus → frontmatter →
auto-indexes → wikilink walk → cumulative recall.

## Deliverables

1. `src/vaultlab/kb/retrieve.py` — `retrieve_by_frontmatter(filter, kb_root)`
2. `src/vaultlab/kb/indexes.py` — `build_indexes(kb_root) -> {index, catalog, backlinks}`
3. `src/vaultlab/kb/retrieve.md` — SKILL.md documenting the retrieval cascade
4. `src/vaultlab/kb/__init__.py` — exports
5. `tests/test_vaultlab_kb/test_retrieve.py`
6. `tests/test_vaultlab_kb/test_indexes.py`

CLI wiring (success criterion #4 — `bobby-kb index --kb <name>` calling the
new builder) is deferred to sub-goal 2.3 (`spec-d-kb-setup-primitive`) which
already plans to refresh the CLI surface together with `setup`/`lint`. The
primitives shipped here are wirable in one line from `kb/cli/__init__.py` when
2.3 lands.

## Decisions

- **YAML parsing:** use `python-frontmatter` (already a dep, used by
  `start_here.py`). Keeps parsing consistent with the rest of the package and
  avoids a hand-rolled tolerant regex parser.
- **Filter AND/OR semantics:** AND across keys, OR within a key when the
  filter value is a `set`. Strings match exactly. Lists in frontmatter (e.g.
  `tags: [a, b]`) are membership-tested against the filter value/set.
- **Index file format:** plain markdown with stable section headers and
  alphabetically sorted file paths so re-runs are byte-identical (idempotent).
- **Skipped paths:** the three index files themselves (`_Index.md`,
  `_Catalog.md`, `_BackLinks.md`), anything under a dotfile directory
  (`.obsidian/`, `.embeddings/`), and files without frontmatter (per spec).
- **Wikilink regex:** `\[\[([^\]|#]+)(?:\#[^\]|]+)?(?:\|[^\]]*)?\]\]` — strips
  optional `#section` and `|alias` suffixes so `[[Foo#bar|Foo bar]]` resolves
  to backlink target `Foo`.
- **No provenance manifest** for `build_indexes` / `retrieve_by_frontmatter`:
  these are index-builds / reads, not artifact writes (per task brief).

## Test plan

- Fixture KB in `tmp_path` with 5-10 small `.md` files spanning `type:
  wiki|paper|note`, varied `created:` dates, and wikilinks across files.
- `retrieve.py`: filter by single key, multiple keys (AND), set value (OR),
  files without frontmatter excluded, index files excluded.
- `indexes.py`: `_Index.md` groups by type; `_Catalog.md` sorted by date;
  `_BackLinks.md` lists referrers per target; idempotency (run twice → same
  bytes).

## EVIDENCE

Populated on completion — see git commit, test counts, file paths.
