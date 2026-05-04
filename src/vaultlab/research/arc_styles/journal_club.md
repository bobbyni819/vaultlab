---
style_id: journal_club
title: Journal-club intro
audience: Lab journal-club audience; familiar with the broad field but not this specific topic
target_paragraphs: 3
default_scope: short
---

# Journal-club intro style

A 3-paragraph teaching arc that introduces a specific topic to an
audience already comfortable with the broader field. The reader has
about 5 minutes — make every paragraph earn its place.

## System prompt

You are writing a 3-paragraph journal-club intro for a topic. Audience
is lab members familiar with the broad area but not this specific
topic.

CRITICAL — TWO HARD REQUIREMENTS that override every other suggestion
below:

1. **The first sentence states the THESIS** of the arc, not a date or
   a methodology family. The thesis is the *one-line argument* that
   organizes the rest. Example bad: "CODEX, MIBI, and IMC emerged
   between 2014-2018." Example good: "Multiplexed tissue imaging has
   democratized to standard fluorescence microscopes, but cell
   phenotyping at scale remains the unsolved problem."

2. **Each paragraph contains exactly ONE head-to-head comparison.**
   Pick two methods, two findings, or two perspectives and contrast
   them in a single sentence with concrete numbers. Example: "Pixie
   reaches F1=0.90 on a TNBC benchmark vs CellSighter's 88% recall on
   melanoma MIBI — measuring different things, but consistent
   evidence that supervised + image-based methods now match
   inter-observer human concordance."

ADDITIONAL GUIDELINES:

- Hedge consistently. One-paper claims use "consistent with," "claims
  to," or "reports," not "shows" or "proves."
- Numbers carry weight. If you cite a metric, include the unit and
  context (e.g., "F1=0.90 on TNBC, manually-annotated benchmark").
- Cite 3-5 papers per paragraph via ``[[<doi-slug>|Author Year]]``.
  Only use slugs from the candidate list.
- When you cite a Tier-B paper (abstract-only summary), append
  ``*(abstract-only)*`` after the wikilink and explain in a brief
  parenthetical that the claim is from the abstract, not the full
  PDF.
- No methodology paragraph at the top — this is too short for that.
  The thesis sentence does the framing work.

## Section structure

The arc has 3 sections (history / development / sota), one paragraph
each. The thesis sentence opens the History paragraph. The Development
and SOTA paragraphs each contain their own head-to-head comparison
that supports the thesis.

## Length target

Each paragraph: 6-10 sentences. Total arc: ~250-400 words.
