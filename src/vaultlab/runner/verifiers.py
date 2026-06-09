"""Internal verifiers for generated scientific text.

CLAUDE.md / architecture.md describe a set of internal verifiers that gate
generated output. Citation and cross-doc verification live in
``vaultlab.citations`` and ``vaultlab.research``; the **numeric** verifier
lives here.

``verify_numeric`` is deterministic (no LLM): it scans text for reported
statistics — p-values, sample sizes, and ``mean ± std, range [...]``
descriptives — and flags internally inconsistent or implausible values
(e.g. a p-value outside [0, 1], a non-positive n, or a mean outside its
stated range). It pairs naturally with the analysis interpretation pass,
which now emits recomputed ``p=`` / ``n=`` lines.
"""

from __future__ import annotations

import re

__all__ = ["verify_numeric"]

# p = 0.01 / p=5.88e-09 / p = .03
_P_RE = re.compile(r"\bp\s*=\s*(\d*\.?\d+(?:[eE][+-]?\d+)?)")
# n=54 or n=6/6 (per-group)
_N_RE = re.compile(r"\bn\s*=\s*(\d+)(?:\s*/\s*(\d+))?")
# mean 12.5±15.7, range [1.36, 65]  (std optional; flexible gap, no '[' crossing)
_MEAN_RANGE_RE = re.compile(
    r"mean\s+(-?\d*\.?\d+)(?:\s*±\s*-?\d*\.?\d+)?[^\[]*?"
    r"range\s*\[\s*(-?\d*\.?\d+)\s*,\s*(-?\d*\.?\d+)\s*\]"
)


def verify_numeric(text: str) -> list[str]:
    """Flag internally inconsistent / implausible reported statistics.

    Returns a list of human-readable findings (one per problem); an empty
    list means no inconsistency was detected. Deterministic and side-effect
    free.
    """
    if not text:
        return []
    findings: list[str] = []

    for m in _P_RE.finditer(text):
        val = float(m.group(1))
        if not (0.0 <= val <= 1.0):
            findings.append(
                f"implausible p-value {val} at offset {m.start()} "
                "(p must lie in [0, 1])"
            )

    for m in _N_RE.finditer(text):
        for grp in m.groups():
            if grp is not None and int(grp) <= 0:
                findings.append(
                    f"non-positive sample size n={grp} at offset {m.start()}"
                )

    for m in _MEAN_RANGE_RE.finditer(text):
        mean_v = float(m.group(1))
        lo = float(m.group(2))
        hi = float(m.group(3))
        if lo > hi:
            findings.append(
                f"inverted range [{lo}, {hi}] at offset {m.start()} (min > max)"
            )
        elif not (lo <= mean_v <= hi):
            findings.append(
                f"mean {mean_v} outside its reported range [{lo}, {hi}] "
                f"at offset {m.start()}"
            )

    return findings
