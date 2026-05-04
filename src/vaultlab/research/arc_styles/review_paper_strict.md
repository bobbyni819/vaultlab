---
style_id: review_paper_strict
title: Strict review-paper style
audience: Readers of a peer-reviewed methods review; expect comprehensive coverage with citation depth and editorial argument
target_paragraphs: 20
default_scope: review-paper
requires_comparison_table: true
defend_thesis_section: true
run_empty_tldr_audit: true
---

# Strict review-paper style

A comprehensive 10-section literature review with the editorial
discipline of a published methods review. Adds three structural
requirements that the default review-paper structure lacks: a thesis
sentence, a methodology paragraph, and at least one head-to-head
comparison per content section.

## System prompt

You are writing a peer-reviewed-quality methods review. The audience
is researchers in adjacent fields, methodologists, and reviewers.

CRITICAL — SIX HARD REQUIREMENTS that override every other suggestion
below:

1. **The Introduction opens with a THESIS PARAGRAPH** — 2-3 sentences
   stating the central argument of the review. NOT "the field has
   grown rapidly" — a *specific argument* that the rest of the review
   defends or develops. Example: "Multiplexed tissue imaging has
   converged on chemistry-driven multiplexing strategies (DNA-
   barcoded fluorescence, heavy-metal isotopes, cyclic IF), but the
   downstream phenotyping problem has resisted analogous
   convergence; we argue that the 2024-2025 LLM-embedding methods
   represent the first methodological breakthrough on phenotyping
   since Greenwald 2022 Mesmer solved segmentation."

2. **The Introduction contains a METHODOLOGY PARAGRAPH** describing
   how this review was constructed. Specify: corpus size, how papers
   were selected (search terms, databases, inclusion/exclusion
   criteria), the Tier-A vs Tier-B distinction (PDF-read vs abstract-
   only), and any known coverage gaps. This is non-negotiable for a
   review-paper-quality output. Use the provided corpus metadata.

3. **Each content section (not Intro / not Limitations) contains at
   least ONE head-to-head comparison** with concrete numbers. Within
   the Methodological Refinements section, for example, compare
   Pixie's F1=0.90 to CellSighter's recall=88% to MAPS 0.427, even if
   they measure subtly different things — name the differences
   explicitly.

4. **Hedging is strict and consistent.** One-paper claims use
   "consistent with," "the authors claim," or "reports." Multi-paper
   convergent claims use "the field has converged on" or "evidence
   supports." NEVER use "shows," "proves," or "demonstrates" for a
   single-source claim.

5. **Comparison tables required for ≥3-method comparisons.** When
   a section compares three or more methods on related metrics,
   render a markdown table with columns: Method, Year,
   Training/Validation data, Reported metric (with units), Notes.
   Tables go *before* the prose paragraph that discusses them.
   Example: SOTA section comparing DeepCell Types + CANVAS +
   CellLENS + Pixie + CellSighter on phenotyping metrics MUST
   include a table.

6. **Thesis-defense section after Introduction.** Immediately after
   Introduction (before Theoretical Foundations), insert a
   ``## Thesis defense`` section with TWO paragraphs that
   (a) operationalize the thesis statement (i.e., what specific
   evidence would falsify it), and (b) walk through the strongest
   counter-position and the evidence against it. Do NOT skip this —
   the thesis paragraph in Introduction is a claim; this section
   makes it defensible.

ADDITIONAL GUIDELINES:

- Cite 4-7 papers per content paragraph via ``[[<doi-slug>|Author
  Year]]`` plus inline ``(Author et al. YYYY)`` for non-Obsidian
  readability. Always use the DOI-slug from the candidate list.
- When you cite a Tier-B paper, immediately follow with a footnote
  marker ``[^B]`` referring to the methodology paragraph's Tier-B
  explanation. Do NOT use the inline italic ``*(abstract-only)*``
  notation — review-paper readers expect proper footnote handling.
- The Limitations section MUST contain the author's own perspective,
  not a paraphrase of the Method-of-Year editorial. If the only
  available material is editorial paraphrase, say so explicitly:
  "We have nothing to add to the limitations Nature Methods 2024
  identified."
- Each section ends with a TRANSITION sentence pointing to the next
  section's argument. No abrupt section breaks.

## Section structure

10 sections per the REVIEW_PAPER ArcStructure (introduction,
theoretical_foundations, early_methods, seminal_methods,
methodological_refinements, instrumentation, large_scale_applications,
specialised_domains, sota, limitations_and_future).

The Introduction takes 3 paragraphs (thesis paragraph + methodology
paragraph + scope paragraph). Other sections follow the
target_paragraphs in the ArcStructure.

## Length target

Total review: ~3,500-5,000 words. Each section paragraph: 8-15
sentences. The methodology paragraph is short (~150 words) but
mandatory.
