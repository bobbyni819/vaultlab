---
template: project_intake
schema: vaultlab-intake/v1
fill_time_estimate: ~5 minutes
required_fields: [topic, goal, audience]
---

# Project intake — <your project name>

Copy this file to `<your-project-folder>/project_intake.md` and fill it
in. Then run `/onboard-project [path-to-project-folder]` — vaultlab will
read your answers, scan the folder, and ask only 3-5 follow-up questions
instead of 30.

> **5 minutes is the budget.** Skip anything that doesn't apply. The
> required fields are `topic`, `goal`, and `audience` — everything else
> is helpful but optional.

## 1. Topic (required)

What's this project about, in one sentence?

> _e.g. "spatial transcriptomics of pancreatic ductal adenocarcinoma
> with focus on CAF-immune neighborhoods"_

YOUR ANSWER:

## 2. Goal (required)

What are you trying to accomplish? Pick all that apply.

- [ ] Understand a literature field
- [ ] Write a journal-club deck
- [ ] Draft a manuscript section (Background / Methods / Results / Discussion)
- [ ] Build a deep research report (3000-5000 word review)
- [ ] Analyze your own wet-lab data
- [ ] Ongoing knowledge-management for an active project (live updates)
- [ ] Other: ____________

## 3. Audience (required)

Who's the output for? Pick all that apply.

- [ ] Yourself (personal notes)
- [ ] Lab members (informal)
- [ ] PI / weekly meeting
- [ ] Journal club
- [ ] Conference talk
- [ ] Manuscript reviewers / journal submission
- [ ] Grant reviewers
- [ ] Other: ____________

## 4. What you already have

Anything vaultlab should read first? Tick + path/info.

- [ ] PDFs you've already collected: <path or list of DOIs>
- [ ] Notes / outlines: <path>
- [ ] Wet-lab data: <type, e.g. "CODEX TIFF stacks at Z:/lab/data/2026-03/">
- [ ] Prior drafts: <path>
- [ ] Citations file (.bib / .ris): <path>
- [ ] Nothing — vaultlab starts from scratch

## 5. What you don't want

Helpful guard-rails. Tick all that apply.

- [ ] Don't include preprints
- [ ] Don't summarize papers older than <year>
- [ ] Don't include papers from <journal>
- [ ] Skip non-English papers
- [ ] Other: ____________

## 6. Style / voice

If outputs include writing, any voice preferences?

- [ ] Conservative / hedged ("X may suggest Y")
- [ ] Direct / declarative ("X shows Y")
- [ ] Match the style of these papers: <DOIs>
- [ ] Match my prior writing at <path>
- [ ] No preference

## 7. PI preferences (if relevant)

Things to mirror or avoid for your PI's review:

> _e.g. "John prefers diagrams over text for methods sections" or
> "John flagged citation [N] superscripts as visual clutter — use
> author-year style"_

YOUR ANSWER:

## 8. Deadlines

- [ ] One-shot — output delivered ASAP, no follow-up
- [ ] Weekly check-ins — vaultlab updates the project page weekly
- [ ] Specific date: <when>

## 9. Anything else

> _Free-form. What would a smart collaborator need to know?_

YOUR ANSWER:

---

When you're done, save this file IN your project folder (not the
template directory) and run:

    /onboard-project [path-to-project-folder]

vaultlab will read this, scan the folder contents, and ask 3-5
follow-up questions for any remaining gaps.
