"""Academic prose polishing rules + 12-step workflow.

Absorbed from the nature-polishing skill (Yuan Yizhe, SJTU) at
nature-skills/skills/nature-polishing/.

This module ships the 25 rules and 12-step polishing workflow as
addressable data — the actual prose transformation happens at
slash-command invocation time (the LLM consults these rules), but the
ruleset lives in code so it's testable, versioned, and queryable.

Public API
----------

- :data:`POLISH_RULES` — list of :class:`PolishRule` (25 rules)
- :data:`WORKFLOW_STEPS` — ordered list of the 12 polishing steps
- :data:`BRITISH_ENGLISH_PAIRS` — US → UK spelling map (60+ entries)
- :func:`rules_by_category` — group rules by category
- :func:`find_rule` — fetch a rule by id
- :func:`check_sentence_length` — flag sentences > 30 words
- :func:`check_us_spelling` — return list of (token, suggestion) pairs

See ``SKILL.md`` (next to this file) for the full prose, when-to-load
guidance, and example transformations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Category = Literal[
    "sentence_architecture",
    "hedging",
    "section_tense",
    "vocabulary",
    "citation_integrity",
    "overclaim",
    "house_style",
]


@dataclass(frozen=True)
class PolishRule:
    """One academic-prose rule.

    Attributes
    ----------
    id:
        Stable rule slug (e.g. ``"sentence-length"``).
    category:
        One of seven domains.
    rule:
        One-sentence statement of the rule.
    rationale:
        Why the rule exists (often references a Nature/eLife convention).
    """

    id: str
    category: Category
    rule: str
    rationale: str = ""


# ---------------------------------------------------------------------------
# The 25 rules — categorized.

POLISH_RULES: list[PolishRule] = [
    # Sentence architecture (5)
    PolishRule(
        "sentence-length",
        "sentence_architecture",
        "Every sentence ≤ 30 words. Count individually; the last sentence in a paragraph fails first.",
        "Long sentences obscure the claim and dilute statistical reporting.",
    ),
    PolishRule(
        "subject-first",
        "sentence_architecture",
        "Lead with the grammatical subject; postpone qualifying clauses.",
        "Front-loaded subjects make scanning easier in dense Methods/Results.",
    ),
    PolishRule(
        "active-voice-default",
        "sentence_architecture",
        "Use active voice by default; reserve passive for emphasizing the experimental object.",
        "Nature/Science/Cell increasingly accept active voice; clearer agency.",
    ),
    PolishRule(
        "no-stacked-prepositions",
        "sentence_architecture",
        'Avoid > 3 prepositional phrases in a row ("of the X in the Y of the Z").',
        "Stacked prepositions are a tell of buried claims.",
    ),
    PolishRule(
        "one-claim-per-sentence",
        "sentence_architecture",
        "One claim per sentence. Compound claims belong in two sentences.",
        "Reviewers cite by sentence; multi-claim sentences cause ambiguous citation.",
    ),
    # Hedging calibration (4)
    PolishRule(
        "hedging-ladder",
        "hedging",
        "Match hedge strength to evidence: demonstrate → show → suggest → indicate → may reflect.",
        "Mis-calibrated hedging is the most common eLife rubric ding.",
    ),
    PolishRule(
        "no-passive-hedging",
        "hedging",
        'Replace "it is suggested that" with "X suggests Y" or "we suggest Y".',
        "Passive hedges hide agency and weaken the claim.",
    ),
    PolishRule(
        "quantify-when-possible",
        "hedging",
        'Replace qualitative hedges ("slightly", "somewhat") with quantitative ranges or effect sizes.',
        "Numbers carry hedge information naturally.",
    ),
    PolishRule(
        "preserve-negative-results",
        "hedging",
        'Negative results state the absence, not the failure: "no detectable X" not "failed to detect X".',
        "Tone matters; absence-of-evidence vs evidence-of-absence.",
    ),
    # Section tense (3)
    PolishRule(
        "results-past-tense",
        "section_tense",
        "Results section: past tense + quantitative detail.",
        '"We observed X (n=12, p<0.001)" — not "We observe...".',
    ),
    PolishRule(
        "methods-past-tense",
        "section_tense",
        "Methods section: past tense, complete-action verbs.",
        "Methods describe what was done.",
    ),
    PolishRule(
        "discussion-tense-shift",
        "section_tense",
        "Discussion: past tense for your results, present tense for mechanism / model claims.",
        "Distinguishes what-we-found from what-we-think-it-means.",
    ),
    # Vocabulary (4)
    PolishRule(
        "vocab-precision",
        "vocabulary",
        'Prefer precise verbs: "recapitulates", "mirrors", "attenuates" over "shows similar", "is the same", "reduces".',
        "Precise verbs carry mechanistic content.",
    ),
    PolishRule(
        "no-very",
        "vocabulary",
        'Strike "very" / "quite" / "rather" — replace with a stronger word or delete.',
        "Intensifiers signal lazy editing.",
    ),
    PolishRule(
        "british-english",
        "vocabulary",
        "Use British English: colour, signalling, modelling, analyse, behaviour, programme.",
        "Nature is British English; consistency matters.",
    ),
    PolishRule(
        "no-acronym-on-first-use",
        "vocabulary",
        "Spell out every acronym on first use in the abstract AND first use in the body.",
        "Reviewers may not read sequentially.",
    ),
    # Citation integrity (3)
    PolishRule(
        "cite-only-read",
        "citation_integrity",
        "Cite only sources personally read and verified. Do not cite by abstract alone.",
        "Hallucinated citations break the literature record.",
    ),
    PolishRule(
        "attribution-types",
        "citation_integrity",
        "Use the four attribution types: foundational, contemporary supporting, contrastive, methodological.",
        'Lazy "see ref X" hides what role the citation plays.',
    ),
    PolishRule(
        "no-self-citation-padding",
        "citation_integrity",
        "Self-citations must justify their relevance, not pad the bibliography.",
        "Editors flag self-citation density > 25% as suspicious.",
    ),
    # Overclaim detection (3)
    PolishRule(
        "no-absolutes",
        "overclaim",
        'Strike "never", "always", "completely", "unique", "first" unless evidence is exhaustive.',
        "Absolutes invite reviewer counterexamples.",
    ),
    PolishRule(
        "causation-vs-association",
        "overclaim",
        "Reserve causal verbs (cause, drive, produce) for interventional evidence; otherwise use associate, correlate, accompany.",
        "Observational data does not license causal language.",
    ),
    PolishRule(
        "scope-fit",
        "overclaim",
        "Do not generalize beyond the tissues / species / conditions tested.",
        "Reviewers will flag scope expansion; preempt it.",
    ),
    # House style (3)
    PolishRule(
        "numbers-and-units",
        "house_style",
        "Spell out one-to-ten in prose; use digits for 11+ and for any unit-bearing quantity.",
        "Consistency across the manuscript.",
    ),
    PolishRule(
        "p-value-format",
        "house_style",
        "Report p-values as P (italic, capital): P=0.012 or P<0.001. Never P=0.000.",
        'Nature house style; "P=0.000" is mathematically impossible.',
    ),
    PolishRule(
        "ci-not-sem",
        "house_style",
        "Prefer 95% CI over SEM for figure error bars; SD for descriptive variability.",
        "CIs convey precision more directly than SEMs for non-statistician readers.",
    ),
]


# ---------------------------------------------------------------------------
# The 12-step workflow

WORKFLOW_STEPS: list[tuple[str, str]] = [
    ("sentence-split", "Split each paragraph into individual sentences for inspection."),
    (
        "section-id",
        "Identify the section (Intro/Results/Methods/Discussion) — drives tense + hedge rules.",
    ),
    ("hourglass-check", "Verify the hourglass: broad opening → narrow claim → broad implications."),
    ("tense-audit", "Apply section-tense rules per sentence."),
    (
        "sentence-edit",
        "Apply sentence-architecture rules: length, subject-first, voice, prepositions.",
    ),
    ("vocabulary-upgrade", "Replace weak verbs / intensifiers; apply British English."),
    ("template-check", "Compare against the section template (e.g. results sentence template)."),
    (
        "citation-audit",
        "Verify every cited claim against personal-read sources; tag attribution type.",
    ),
    ("house-style", "Apply numbers, p-values, units, italics, error-bar conventions."),
    (
        "overclaim",
        'Flag absolutes, unwarranted causation, scope expansion, unverified "first" claims.',
    ),
    ("proofreading", "Final pass for typos, spacing, punctuation, capitalization."),
    ("plain-text-output", "Strip word-processor formatting; emit clean plain-text or markdown."),
]


# ---------------------------------------------------------------------------
# British-English replacement table (60+ entries)

BRITISH_ENGLISH_PAIRS: dict[str, str] = {
    # -or → -our
    "color": "colour",
    "colors": "colours",
    "behavior": "behaviour",
    "behaviors": "behaviours",
    "favor": "favour",
    "favors": "favours",
    "favorable": "favourable",
    "honor": "honour",
    "labor": "labour",
    "neighbor": "neighbour",
    "tumor": "tumour",
    "tumors": "tumours",
    "humor": "humour",
    # -ize → -ise
    "analyze": "analyse",
    "analyzed": "analysed",
    "analyzing": "analysing",
    "characterize": "characterise",
    "characterized": "characterised",
    "characterizing": "characterising",
    "minimize": "minimise",
    "maximize": "maximise",
    "organize": "organise",
    "organized": "organised",
    "summarize": "summarise",
    "emphasize": "emphasise",
    "criticize": "criticise",
    "specialize": "specialise",
    "synthesize": "synthesise",
    "utilize": "utilise",
    "recognize": "recognise",
    "realize": "realise",
    "categorize": "categorise",
    "normalize": "normalise",
    "visualize": "visualise",
    "polarize": "polarise",
    "homogenize": "homogenise",
    # -l → -ll
    "modeling": "modelling",
    "modeled": "modelled",
    "signaling": "signalling",
    "labeled": "labelled",
    "labeling": "labelling",
    "traveling": "travelling",
    "traveled": "travelled",
    "leveling": "levelling",
    "fueling": "fuelling",
    "canceled": "cancelled",
    "canceling": "cancelling",
    # -er → -re
    "center": "centre",
    "centers": "centres",
    "centered": "centred",
    "fiber": "fibre",
    "fibers": "fibres",
    "liter": "litre",
    "liters": "litres",
    "meter": "metre",
    "meters": "metres",
    # Other
    "anemia": "anaemia",
    "leukemia": "leukaemia",
    "diarrhea": "diarrhoea",
    "estrogen": "oestrogen",
    "edema": "oedema",
    "program": "programme",  # only for the non-software sense — careful
    "esthetic": "aesthetic",
    "fetus": "foetus",
    "anesthesia": "anaesthesia",
}


# ---------------------------------------------------------------------------
# Helpers


def rules_by_category() -> dict[Category, list[PolishRule]]:
    """Group rules by category for indexing."""
    out: dict[Category, list[PolishRule]] = {}
    for rule in POLISH_RULES:
        out.setdefault(rule.category, []).append(rule)
    return out


def find_rule(rule_id: str) -> PolishRule | None:
    """Fetch a rule by its slug."""
    for rule in POLISH_RULES:
        if rule.id == rule_id:
            return rule
    return None


_WORD_RE = re.compile(r"\b\w+(?:[-'']\w+)?\b")


def _word_count(sentence: str) -> int:
    return len(_WORD_RE.findall(sentence))


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


def check_sentence_length(text: str, *, max_words: int = 30) -> list[tuple[int, int, str]]:
    """Return [(sentence_index, word_count, sentence)] for sentences that
    exceed ``max_words``.
    """
    sentences = _SENTENCE_RE.split(text.strip())
    return [(i, _word_count(s), s) for i, s in enumerate(sentences) if _word_count(s) > max_words]


def check_us_spelling(text: str) -> list[tuple[str, str]]:
    """Return [(us_word, british_suggestion)] pairs found in the text.

    Whole-word match, case-insensitive on the lookup side; preserves the
    case of the matched token in the returned suggestion (lower → lower,
    Title → Title, UPPER → UPPER).
    """
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for us_word, uk_word in BRITISH_ENGLISH_PAIRS.items():
        pattern = re.compile(rf"\b{us_word}\b", re.IGNORECASE)
        for m in pattern.finditer(text):
            tok = m.group(0)
            key = (tok, uk_word)
            if key in seen:
                continue
            seen.add(key)
            # Preserve case
            if tok.isupper():
                suggestion = uk_word.upper()
            elif tok[0].isupper():
                suggestion = uk_word.capitalize()
            else:
                suggestion = uk_word
            found.append((tok, suggestion))
    return found


__all__ = [
    "BRITISH_ENGLISH_PAIRS",
    "POLISH_RULES",
    "WORKFLOW_STEPS",
    "Category",
    "PolishRule",
    "check_sentence_length",
    "check_us_spelling",
    "find_rule",
    "rules_by_category",
]
