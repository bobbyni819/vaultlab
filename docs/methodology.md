# Vaultlab citation-metrics methodology

This page documents how vaultlab computes the citation-graph metrics that
appear in lineage arcs, decks, and reports. It is the canonical reference
for terms like ``og_score``, ``forward_influence``, and the year-bucketing
scheme.

## og_score (bibliographic coupling)

**Definition:** ``og_score(p) = |{s in seeds : p in refs(s)}| / |seeds|``.

In words: ``og_score`` is the fraction of seed papers that cite candidate
``p``. A score of 0.8 means 8 out of 10 seeds cite that paper; a score of
0.0 means no seed cites it (which is normal for Tier-C stubs walked one
hop out, and for *fresh* seeds whose own outbound citations haven't been
indexed within the corpus).

The score is a direct application of **Kessler (1963)** bibliographic
coupling
([Kessler 1963, ASIS&T](https://doi.org/10.1002/asi.5090140103)):
two papers are coupled in proportion to the references they share. Here
we measure coupling against the seed set rather than between arbitrary
paper pairs — the score answers "how foundational is this candidate to
the seed pool's intellectual lineage?".

### What og_score does NOT measure

* It is **not** total citation count. A paper cited by 1,000 unrelated
  studies gets ``og_score=0`` here unless those citations appear in the
  seed pool.
* It is **not** topical relevance. A high-og paper that turns out to be
  off-topic is still high-og; the content-aware picker exists precisely
  to catch this case (read the abstract before ranking, override the
  citation-graph baseline when the abstract disagrees).
* It is **not** stable across seed perturbations. Adding a single seed
  can change every score; the seed set is the privileged frame of
  reference.

### Why og_score is the default ranking signal

For literature-arc work the seed set IS the topic definition. A paper
referenced by most of the seeds is by construction central to the
literature the seeds are arguing within. This is much narrower (and more
useful) than global citation counts, which conflate "famous" with
"foundational to your topic".

## forward_influence

**Definition:** in-degree on the seed × seed subgraph. For a paper ``p``
that is itself a seed, ``forward_influence(p)`` is the number of *other
seeds* that cite ``p``. Non-seed papers always have
``forward_influence = 0``.

This catches the "seed citing seed" pattern that's invisible in
``og_score`` (which already counts the citation): if seed B cites seed A,
A gets ``+1`` to ``forward_influence`` and ``+1/|seeds|`` to ``og_score``
both. The two metrics are correlated but not identical — a paper cited
heavily by *non-seed* references will have high ``og_score`` and zero
``forward_influence``.

## Co-citation pairs

**Definition:** pairs ``(a, b)`` ranked by the number of seeds that cite
**both** of them. This is **co-citation analysis** in the classic Small
(1973) sense — pairs co-cited frequently belong to the same intellectual
neighbourhood even if they don't cite each other directly.

The pair list is filtered to ``count >= 2`` and capped at the top 50 in
``CorpusMetrics.co_citation_pairs``. The deck builder uses this to
suggest "two-papers-in-one-slide" pairings.

## Year buckets

Papers are bucketed by year into one of:

* ``history`` — pre-2000 (or first-third of the corpus year range,
  whichever is later).
* ``development`` — middle third.
* ``sota`` — last third (typically last ~5 years).
* ``unknown`` — no year metadata.

The buckets are resolved relative to the **corpus** year span, not a
fixed cutoff. A 2020-2026 corpus has different bucket boundaries than a
1995-2026 one. See ``vaultlab.research.graph_metrics._year_bucket_assignments``
for the exact logic.

## Tier classification

* **Tier A** — full text was read by Claude Code (or the Anthropic SDK
  in pure-Python mode). The summary's ``key_findings``, ``methods_summary``,
  and ``why_it_matters`` are grounded in the paper body.
* **Tier C** — citation-stat-only stub. The summary's ``tldr`` is
  derived from metadata + abstract; ``key_findings`` is empty by design.
  Tier-C papers contribute to the citation graph (so they show up in
  ``og_score``, co-citation pairs, etc.) but do not anchor any narrative
  claim.

(Tier B is reserved for "abstract + methods only" — currently unused;
the pipeline collapses to A or C.)

## Anonymous-author handling

Some Tier-C stubs come back from CrossRef references with empty author
lists (CrossRef references typically only carry the first author, and
sometimes none). As of evening 3 (2026-04-30) the pipeline backfills
empty author lists from Semantic Scholar by DOI before rendering. When
both CrossRef and S2 fail, the renderer **drops the wikilink** rather
than emit a useless ``[[<slug>|Anon n.d.]]`` token; the paper still
appears in the table, but as a metadata-only stub row keyed by DOI.

## When og_score is misleading

Run the **adversarial picker** (``picker_mode="adversarial"``) when the
seed set is heterogeneous or when the topic is application-heavy
(application papers tend to cite a long tail of methods papers, inflating
``og_score`` for tools that aren't really the topic). The picker's
critic round explicitly checks for "high og_score, off-topic abstract"
and demotes such papers.

## References

* Kessler, M. M. (1963). *Bibliographic coupling between scientific
  papers.* American Documentation 14(1):10-25.
  https://doi.org/10.1002/asi.5090140103
* Small, H. (1973). *Co-citation in the scientific literature: A new
  measure of the relationship between two documents.* JASIS 24(4):265-269.
* Vaultlab implementation lives in
  ``vaultlab.research.graph_metrics`` (citation graph) and
  ``vaultlab.research.picker`` (content-aware override).
