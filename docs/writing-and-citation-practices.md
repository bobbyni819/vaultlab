# Writing and citation practices (canonical)

> Bobby's standing practices for thesis, proposal, and grant prose, plus the PDF-grounded
> citation-verification workflow. This file is the single source of truth. The slash commands
> `/style-check` and `/cite` point here, and `READ_FIRST.md` routes natural-language asks to them,
> so a cold Claude Code session inherits these practices without being re-told.
>
> Lifted from the thesis KB: `thesis/Wiki/Methodology/prelim-proposal-writing-and-process-standards.md`
> (last updated 2026-06-03), `thesis/Wiki/Methodology/grant-abstract-writing-principles.md` (2026-06-02),
> and the `feedback-prelim-writing` memory. Apply to any thesis/proposal/grant prose without re-asking.
> This doc itself follows the section A rules (no em-dashes, no arrows).

## How a session inherits this

1. Working inside the vaultlab repo: the `using-vaultlab` skill auto-loads and points here.
2. Pointed at vaultlab from another repo ("go read my vaultlab"): the session reads `READ_FIRST.md`,
   whose Step-3 dispatch rows and Step-4 role-pass row route writing and citation asks to `/style-check`
   and `/cite`, both of which load this file.
3. At session start, `recall_all()` surfaces the seeded `thesis-writing-style` and `pdf-citation-grounding`
   feedback memories.

The reliable channel is the `READ_FIRST.md` dispatch rows. They are read deterministically every session.

---

## A. Writing style (hard rules)

Non-negotiable for thesis, proposal, and grant prose. Apply to any prose written for those documents.

- **No em-dashes (—) in prose.** Use commas, periods, parentheses, or semicolons. Section-header
  separators use a colon or period, not an em-dash. (In v11 of the R21 draft this took prose em-dashes
  from 88 to 0.)
- **No arrow symbols (→).** Write "to", "then", or "into" in words.
- **Few colons.** Prefer full sentences. Do not use a colon to bolt a list or explanation onto a clause.
- **No short, snappy, AI-sounding sentences.** A sentence like "This is biology, not abstraction." or
  "The approach is proven." is not acceptable. Either delete it or merge it into a fuller, more
  informative sentence. Signpost fragments ("Success has two parts.") are tolerated only when they
  genuinely organize a list.
- **No filler or conversational words:** exactly, really, just, actually, of course, in turn, simply,
  clearly. This is a proposal, not a conversation.
- **No rhetorical questions.** State the point directly rather than posing "what arrangement causes it?"
- **Plain, straightforward language, no fluff.** Cut meta-commentary ("our claim is mechanistic, not
  promotional"). Favor short, clear structure, concrete verbs, and concrete adjectives. Long nested
  sentences and idioms ("closes the loop", "throws away") are flagged and rewritten.
- **Avoid over-specialized or jargon verbs** where a plain word is clearer. Prefer "makes reviewable"
  over "renders inspectable", "controls" over "gates", "does not preserve" over "throws away",
  "is incorporated" over "plugs in / drops in".
- **Define every abbreviation at first use** (ABM, LLM, NK, CODEX, BSS, ODE, ARDS, AST, AM, H&E, FM,
  PRCC, TOST). Use real Greek letters where appropriate (IFN-γ, TNF-α, not IFNG).
- **Active voice.**
- **Natural, flowing, declarative sentences.** Split run-ons; keep to about one nested clause per
  sentence. This is the grounded form of the anti-AI-tell flow rules below.
- **Break dense walls of text into paragraphs by sub-topic.**
- **Lead with the takeaway a skimming reader remembers.** State the result a reviewer will carry away
  before the supporting detail.
- **Concise.** Near the real document length (for the R21 prelim: 1 page Specific Aims, about 6 pages
  Research Strategy; references are free and uncapped).
- **US English, not British.** vaultlab's `/polish` defaults to British vocabulary for Nature-family
  journals. For Bobby's thesis and US grant work, use US spelling. This is a per-profile override, not
  a global flip.

### A(flow). Anti-AI-tell flow rules (JUDGMENT-LEVEL)

These three shape sentence rhythm so prose does not read as machine-generated (from the 2026-06-05
writing-style feedback). They are judgment calls, not regex rules. Apply with care and, when a pass
would heavily rewrite the author's prose, confirm the threshold with Bobby rather than over-editing.

- **Lead with the main clause.** Put the subject and verb first, then qualifications.
- **Reduce comma-stops.** Fewer mid-sentence commas; split into two sentences when a sentence stacks
  several comma-separated clauses.
- **Vary sentence length.** Avoid a run of same-length sentences. Mix longer explanatory sentences with
  shorter ones, without crossing into the banned snappy-fragment style above.

## B. Honesty and scope of claims

- **Capabilities-only for in-progress metrics.** Do not state brittle numbers from work still in code
  (test pass percentages, test counts, runtimes, parameter tallies). Say what the system can do. Numbers
  from published papers are fine.
- **No overclaiming.** A pipeline in development is "in active development", not "operational". Describe
  precedent without calling your own approach "proven".
- **Hedged voice always** (vaultlab commitment #2): "consistent with X", "suggests", "may indicate";
  never "is X", "proves", "demonstrates".
- **Architectural-lite disclosure.** Reveal enough for a reviewer to judge novelty (name the most
  defensible artifact, for example the BSS), but do not leak full implementation (phase counts, fixer
  catalog, prompt strategy). For an internal prelim, lean more open, since the committee wants depth.
- **Do not sell implementation hygiene as the contribution.** Test counts and fixer counts are hygiene.
  Lead with the idea, support with the metric.
- **Report partial results honestly.** "1/12 inconsistent, under investigation" and "84.8% pass rate"
  read as credible work-in-progress, not weakness. Frame so numbers can be updated without restructuring.
- **A documented negative result is framed as a deliverable.** A benchmark stands regardless of whether
  the method wins.

## Grant and proposal structure (proposals and aims)

Transferable across the prelim, F-series, and conference abstracts.

- **Significance, then Innovation, then Approach.** Each Aim ends with an explicit Payoff.
- **Every Aim states its deliverable and a go/no-go gate.** De-risking branches are explicit. For the
  R21, Aim 2 is independent of Aim 1, and Aim 3 needs no new tissue.
- **Match the audience and track; avoid hype-pollution.** Reviewers read methods, not keywords.

## C. Citation integrity (zero hallucination)

- **Every cited paper is read from its actual PDF** (page images, not text extraction), and verified
  against a per-paper note in `Sources/Papers/<Author><Year>.md`. Text extraction drops figures, tables,
  and superscripts, so it is not sufficient on its own.
- **Confirm paper identity before confirming any claim.** Check that the title, authors, journal, and
  DOI on the opened PDF match the cited paper. On a mismatch, quarantine the file and mark the citation
  UNVERIFIED. This catches a wrong PDF filed under the right name.
- **High-stakes numbers are quoted from the source** with their location (table, figure, or page). For
  example, "melanoma R² = 0.97–0.99" is for cell-type composition, not spatial dynamics, and must be
  quoted as such.
- **Do not cite unpublished or in-preparation manuscripts.** Present that work as "our preliminary data".
- **Attribute correctly.** A framework a PI co-authored is "our PI co-authored", not "our lab's".
- **Citations are renumbered to first-appearance order**, ascending, gapless, zero orphans, after every
  edit batch.
- **No uncited references ("nothing wasted").** Every reference earns a cited claim, or it is cut.
- **Claims are anchored to concrete, verified numbers** with citations, not vague gestures.
- **The master record is `Output/<project>/VERIFICATION_LEDGER.md`.** Run a paper-by-paper grounding
  audit before declaring a draft final.

## D. The PDF-grounded verification workflow (reusable, run by `/cite`)

The three-step loop used to verify every citation. It generalizes to any document with references.

1. **Inventory.** For every reference, check whether a local PDF exists (in `Sources/Papers/` or the
   papers database). Split the reference list into have-PDF and no-PDF.
2. **Ground what we have.** For each have-PDF paper, read the actual PDF page images (not text
   extraction). First confirm identity (title, authors, journal, DOI). Then verify every claim, number,
   and attribution that cites it against the real text. Record the result in a per-paper note plus one
   line in `VERIFICATION_LEDGER.md`. Quote high-stakes numbers verbatim with their location.
3. **Harvest what we are missing.** For each no-PDF reference, output a clean clickable link list
   directly in the chat, one link per line (DOI or publisher or PubMed URL), grouped so they are easy to
   scan. Bobby left-clicks each to open them as browser tabs and bulk-downloads them in one pass. The
   downloaded PDFs are then filed and re-run through step 2. This is far faster than fetching papers one
   at a time. The `vaultlab fetch-list paywalled <acquisition-log.json>` CLI subcommand produces this
   clustered list.

**Hard rule:** never verify a claim from memory, from an abstract alone, or from a search snippet. If
there is no PDF and the paper has not yet been downloaded, mark that citation UNVERIFIED in the ledger
rather than asserting it is correct. A citation is only "verified" once its PDF has been read in step 2.

## E. Document and tooling conventions

- **Markdown is the single source of truth.** A Word file is rendered from it (Arial 11, 0.5-inch
  margins, ALL-CAPS bold section headers, page numbers, strips HTML comments).
- **Do not clobber a figure-embedded Word file.** Figures are pasted in by hand. When a `.docx` is large
  (about 1 MB), it holds figures and must not be overwritten by a fresh text-only render.
- **Plain-language companion docs** are maintained for jargon-heavy parts, so the work can be explained
  and defended without the technical wording.

## F. Process and workflow

- **One comment at a time.** Bobby reviews drafts and sends edits incrementally. Keep editing the same
  working version rather than spawning a new version per comment, unless asked.
- **Confirm the canonical version before editing.** There is exactly one current draft. Do not assume a
  summary is up to date. Check `START_HERE.md` and the latest draft on disk first.
- **Ask before a large rewrite** if the intent is unclear, and before any irreversible action (deleting
  or overwriting drafts, sending anything outward).
- **Keep KB metadata fresh at session close.** Update `START_HERE.md` (newest at top), append to
  `_Log.md` (newest at bottom), and update `VERIFICATION_LEDGER.md` if citations changed. Archive
  superseded drafts rather than deleting them.

## G. Pre-ship checklist (run before a draft goes out)

- [ ] No em-dashes or arrow symbols in prose; colons minimal.
- [ ] No short snappy sentences, no filler words, no rhetorical questions.
- [ ] Anti-AI-tell flow applied (lead with main clause, fewer comma-stops, varied sentence length).
- [ ] Every abbreviation defined at first use; Greek letters where appropriate; US spelling.
- [ ] In-progress metrics stated as capabilities, not brittle numbers; hedged voice.
- [ ] Every citation read from its PDF and verified; identity confirmed; first-appearance order, zero orphans.
- [ ] No unpublished or in-prep citations; attributions correct.
- [ ] Word file rendered from the markdown source; figure-bearing `.docx` not clobbered.
- [ ] `START_HERE.md`, `_Log.md`, and `VERIFICATION_LEDGER.md` updated.

---

## Status of enforcement

- **Today (instruction-driven):** `/style-check` and `/cite` run this discipline by following the rules
  above. GROUND reads PDF page images with the `Read` tool. HARVEST runs `vaultlab fetch-list paywalled`.
- **Planned (deterministic engine, on `feat/writing-citation-practices`):** a `StyleProfile` that
  `/polish` auto-consumes (US-English, ban em-dash, ban arrows, filler ban), and a `citations.grounding`
  module that emits `VERIFICATION_LEDGER.md` and the missing-PDF link list in code. Until those land,
  the rules are applied by the session, not auto-checked.
