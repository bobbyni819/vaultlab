# Known unresolvable DOIs

DOIs that the author-backfill chain (OpenAlex -> CrossRef-by-DOI ->
Semantic Scholar -> bioRxiv) cannot resolve. Listed here as a paper
trail rather than silently dropped from corpora.

Most entries fall into two categories:

1. **Malformed / typo'd DOIs** — Unicode hyphens (`U+2010` instead of
   ASCII `-`), embedded spaces, or wrong prefixes (e.g. `10.1016/i.`
   instead of `10.1016/j.`). These usually trace to OCR errors in
   PDF-extracted reference lists.
2. **Genuinely unindexed records** — preprints / arXiv records that
   don't have a CrossRef DOI and aren't in OpenAlex (rare for
   biomedical literature).

Maintenance: if any entry below is fixable (typo correctable, or the
record has since been indexed), regenerate the corpus seed list and
re-run `python scripts/_backfill_anonymous_authors.py --kb <kb>`.

## Run 2026-04-30 17:51:23

Tried OpenAlex, CrossRef-by-DOI, Semantic Scholar, bioRxiv. None
returned authors:

- `10.1016/i.camwa.2004.12.008`
  - Likely typo: should be `10.1016/j.camwa...`
- `10.1038/s415 86-019-1049-y`
  - Embedded space — should be `s41586`
- `10.1038/s41587‐019‐0392‐8`
  - Unicode hyphens (`U+2010`) instead of ASCII `-`
- `10.1038/s41592-024-02565-3`
  - DOI not yet in any indexed source as of this run
- `10.48550/arxiv.1910.13140`
  - arXiv DOI; OpenAlex sometimes lacks the DOI alias for older arXiv
    works. The `arXiv:1910.13140` paper exists but isn't reachable via
    DOI lookup.
