"""Deterministic hedged-voice guardrail.

vaultlab's quality bar (CLAUDE.md / AGENTS.md "hedged voice") forbids
unhedged causal/assertive language in generated scientific text — claims
must read as *"consistent with X"* / *"appears to X"*, never *"proves X"*.

``enforce_hedge`` is the deterministic checker: a banned-assertion scan over
text that returns a flag per overclaiming phrase found. It is intentionally
conservative — it flags a small, high-precision set of strong assertions
rather than attempting to parse every sentence — so it can be wired into the
analysis interpretation pass and role outputs without false-positive noise.
"""

from __future__ import annotations

__all__ = ["ALLOWED_HEDGES", "BANNED_ASSERTIONS", "enforce_hedge"]

# High-precision overclaiming phrases. Lowercased; matched case-insensitively.
# Kept deliberately narrow so legitimate hedged prose is never flagged.
BANNED_ASSERTIONS: tuple[str, ...] = (
    "proves",
    "proven",
    "proof that",
    "demonstrates that",
    "definitively shows",
    "shows that",
    "establishes that",
    "establishes causation",
    "confirms that",
    "we conclude that",
    "clearly indicates",
)

# Reference list of acceptable hedges (for callers / docs; not used to gate).
ALLOWED_HEDGES: tuple[str, ...] = (
    "consistent with",
    "appears to",
    "compatible with",
    "suggests",
    "may indicate",
    "is associated with",
)


def enforce_hedge(text: str) -> list[str]:
    """Scan ``text`` for unhedged overclaiming phrases.

    Returns a list of human-readable flags (one per occurrence), e.g.
    ``["overclaim: 'proves' at offset 5 — use a hedged form (consistent
    with / appears to)"]``. An empty list means the text is clean.
    """
    if not text:
        return []
    low = text.lower()
    flags: list[str] = []
    for phrase in BANNED_ASSERTIONS:
        start = 0
        while True:
            idx = low.find(phrase, start)
            if idx == -1:
                break
            flags.append(
                f"overclaim: '{phrase}' at offset {idx} — use a hedged form "
                "(e.g. 'consistent with' / 'appears to')"
            )
            start = idx + len(phrase)
    return flags
