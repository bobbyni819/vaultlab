# Retrieval benchmark v0

The first versioned retrieval benchmark for vaultlab. It scores the **current**
TF-IDF baseline (`vaultlab.kb.semantic_search.search`) at **recall@1/5/20** over a
fixed corpus of `(claim, source_doi, passage)` tuples. Every later index
(embeddings, BM25 chunk store) should be scored against the same `tuples.jsonl`
with the same recall@k definition, so improvements are comparable.

## Files

| file | role |
|---|---|
| `tuples.jsonl` | the load-bearing artifact — one tuple per line (see schema below) |
| `corpus_meta.json` | KB root the tuples were mined from, mining provenance, and the skipped-candidate audit |
| `run_baseline.py` | the runner — queries the baseline once per claim, computes recall@1/5/20 |
| `baseline_report.md` | generated report (recall numbers + per-tuple hit/miss + skip audit) |

## Tuple schema (`tuples.jsonl`)

```json
{
  "claim": "the assertion as written in the manuscript",
  "source_doi": "10.xxxx/...",
  "source_title": "short title (or null)",
  "expected_passage": "the supporting sentence in the source (or null)",
  "manuscript_path": "/abs/path/to/manuscript.md",
  "provenance": "file.md:line (section)",
  "verified": false
}
```

`verified` is **false** for every tuple — the user flips these after reviewing that
each claim genuinely cites that DOI. Treat the recall numbers as provisional until
then.

## Recall@k definition

For each tuple, query the baseline with `claim` and take the top-k returned files.
A tuple is a **hit@k** iff its `source_doi` (lowercased) appears as a substring in
the text of **any** of those top-k files. `recall@k = hits@k / total_tuples`.

## ⚠️ Caveat — this is an upper bound, not cross-doc retrieval

The configured KB (`resolve_kb_root()`) had no citation-bearing manuscripts, so the
v0 corpus was mined from a fallback KB (`corpus_meta.json` → `kb_root`) where the
**claim and its cited DOI live in the same file** (no separate per-paper source
docs exist). So `search(kb, claim)` retrieves that same file, which contains the
DOI → near-guaranteed hit. v0 recall measures *"can TF-IDF re-find the document a
claim was copied from"* — an inflated **upper bound**, not true cross-doc citation
retrieval. The harness is the durable artifact; it produces a meaningful number the
moment a corpus with separate manuscript + source docs is supplied.

> Note: the corpus KB lives under Google Drive's `.shortcut-targets-by-id`
> shortcut. The TF-IDF baseline previously collected **0 files** from any
> dot-prefixed path; that was fixed in `kb/semantic_search.py` (`_collect_paths`
> now only excludes hidden segments *inside* the KB), so the runner searches the
> real path directly — no mirror/workaround needed.

## Run

```bash
/opt/anaconda3/bin/python tests/benchmarks/retrieval/run_baseline.py
# or point at a different corpus KB:
/opt/anaconda3/bin/python tests/benchmarks/retrieval/run_baseline.py --kb-root /path/to/kb
# score the opt-in embeddings backend (requires sentence-transformers):
/opt/anaconda3/bin/python tests/benchmarks/retrieval/run_baseline.py --backend embeddings
```

The runner calls `resolve_kb_root()` to honour the KB-resolution contract and prints
it; it then scores against `corpus_meta.json`'s `kb_root` (where the cited sources
live), warning loudly if the two differ. `--backend tfidf` (default) writes
`baseline_report.md`; `--backend embeddings` writes `baseline_report_embeddings.md`
and refuses to run if sentence-transformers is missing (rather than silently
falling back to tfidf).

## TF-IDF vs embeddings (v0 corpus)

| metric | tfidf | embeddings (all-MiniLM-L6-v2) | delta |
|---|---|---|---|
| recall@1 | 0.833 | 0.417 | −0.416 |
| recall@5 | 1.000 | 0.667 | −0.333 |
| recall@20 | 1.000 | 0.917 | −0.083 |

Doc-level embeddings **regress** here, as expected for this co-located corpus: the
claim text is verbatim in its source file, so lexical TF-IDF nails rank 1, while
averaging a whole ~5000-char card into one vector blurs the specific claim. The
embedding cache (`kb/semantic_search.py` `_embed_paths`) is still the durable win —
it stops the opt-in backend re-encoding every doc per call.

## Regenerating with a better corpus

1. Replace `tuples.jsonl` with tuples mined from real manuscripts that cite
   **separate** source documents present in the KB.
2. Update `corpus_meta.json` `kb_root` + `mined_from` + `skipped`.
3. Re-run `run_baseline.py`. Recall then reflects genuine cross-doc retrieval.
