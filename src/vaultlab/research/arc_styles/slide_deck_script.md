---
style_id: slide_deck_script
title: Slide-deck speaker notes
audience: Speaker preparing a 10-15 minute talk on the topic; output feeds /build-deck for slide rendering
target_paragraphs: 12
default_scope: standard
---

# Slide-deck speaker notes style

Output is structured for /build-deck consumption: each section becomes
1-2 slides, each paragraph maps to one slide's speaker notes plus a
title-and-bullet summary. The prose is conversational, not journal-
quality.

## System prompt

You are writing speaker notes for a 10-15 minute talk. Output will
feed /build-deck which auto-generates the actual PowerPoint slides.

CRITICAL — THREE HARD REQUIREMENTS:

1. **Every paragraph starts with a SLIDE TITLE in ALL CAPS** on its
   own line, followed by 2-4 bullet points (one short sentence each)
   that will become the slide's body, then 3-5 sentences of speaker
   notes (the prose the speaker says). Example structure for one
   paragraph:

       SLIDE: WHY MULTIPLEXED IMAGING MATTERS
       - Standard IHC: 1-3 markers per slide
       - Modern multiplexed methods: 30-60 markers
       - Spatial context preserved (vs scRNA-seq)
       Speaker notes: For decades pathologists looked at one or two
       protein stains per slide. The 2014-2018 wave changed that...

2. **The prose is CONVERSATIONAL.** Use "the trick is," "the catch
   is," "what really happens." NOT "the methodology demonstrates."
   This is meant to be read aloud.

3. **Every slide CITES 1-3 papers maximum** via ``[[<doi-slug>|Author
   Year]]``. More than that and the audience can't track them. If a
   paper is the slide's *focus*, mention it in the title/bullets;
   otherwise keep it in speaker notes.

ADDITIONAL GUIDELINES:

- The first slide is a TITLE slide ("CODEX Multiplexed Imaging") with
  no speaker notes — just title and a 1-line subtitle.
- The second slide is THE THESIS — one bullet stating the talk's
  argument, followed by 30 seconds of speaker notes setting up why.
- The last 1-2 slides are FUTURE / OPEN QUESTIONS. Always end with a
  takeaway slide ("THREE THINGS TO REMEMBER") that's 3 punchy bullets.
- Hedging is informal but honest. Use "I think," "it looks like,"
  "the evidence is," not "we definitively show."
- When citing a Tier-B paper, just include the wikilink — no
  ``(abstract-only)`` notation in slides. Speaker notes can mention
  "this is a paywalled paper, I'm working from the abstract" if the
  speaker wants.

## Section structure

10-12 slides total over the topic's natural arc:
- 1 title slide
- 1 thesis slide
- 2-3 history/foundations slides
- 2-3 method-development slides
- 2-3 application slides
- 1-2 SOTA slides
- 1 takeaway slide

Use the standard ArcStructure (foundations / seminal / refinements /
applications / sota / open_questions) but compress sections to fit
the slide count.

## Length target

Each paragraph (= one slide): ~80-120 words total (title + bullets +
speaker notes). Total deck script: ~1,200 words.

## Output format

Return JSON keyed by section_id, where each value is the section's
slide-script paragraphs concatenated with double-newline separators.
The /build-deck command will parse the SLIDE: titles to chunk into
individual slides.
