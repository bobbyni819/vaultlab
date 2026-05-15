# Citation cleanup report

**Source:** `draft.md`  
**Audit date:** 2026-05-15  
**Total citations:** 10

## Summary

- Critical (must fix before publication): **1**
- Review (verify before publication): **7**
- OK (well-formed; pending API verification): **2**

## Critical — 1 citation(s)

- **(Doe et al., 2099)** (line 15) — `Doe et al. (2099)`
  - Year 2099 is implausible — possible hallucination

## Review — 7 citation(s)

- **(Asp et al., 2020)** (line 4) — `Asp et al. (2020)`
  - Add DOI before publication; author-year alone cannot be verified
- **(Park et al., 2023)** (line 7) — `Park et al. (2023)`
  - Add DOI before publication; author-year alone cannot be verified
- **PMID: 28104796** (line 16) — `28104796`
  - Citation parsed without authors — re-check source markdown
- **(Garcia and Singh, 2024)** (line 19) — `Garcia and Singh (2024)`
  - Add DOI before publication; author-year alone cannot be verified
- **(Pentimalli and Rajewsky, 2025)** (line 20) — `Pentimalli and Rajewsky (2025)`
  - Add DOI before publication; author-year alone cannot be verified
- **Lee et al. (2021)** (line 22) — `Lee et al. (2021)`
  - Add DOI before publication; author-year alone cannot be verified
- **(Lee 1822)** (line 23) — `Lee (1822)`
  - Add DOI before publication; author-year alone cannot be verified

## OK — 2 citation(s)

- **DOI: 10.1038/s41592-024-02123-w** (line 11) — `10.1038/s41592-024-02123-w`
  - DOI well-formed; verify against CrossRef in real run
- **doi:10.1016/j.cels.2025.101261.** (line 20) — `10.1016/j.cels.2025.101261`
  - DOI well-formed; verify against CrossRef in real run

## Per-citation classification

| line | citation | severity | action |
|---|---|---|---|
| 4 | `(Asp et al., 2020)` | review | Add DOI before publication; author-year alone cannot be verified |
| 7 | `(Park et al., 2023)` | review | Add DOI before publication; author-year alone cannot be verified |
| 11 | `DOI: 10.1038/s41592-024-02123-w` | ok | DOI well-formed; verify against CrossRef in real run |
| 15 | `(Doe et al., 2099)` | critical | Year 2099 is implausible — possible hallucination |
| 16 | `PMID: 28104796` | review | Citation parsed without authors — re-check source markdown |
| 19 | `(Garcia and Singh, 2024)` | review | Add DOI before publication; author-year alone cannot be verified |
| 20 | `(Pentimalli and Rajewsky, 2025)` | review | Add DOI before publication; author-year alone cannot be verified |
| 20 | `doi:10.1016/j.cels.2025.101261.` | ok | DOI well-formed; verify against CrossRef in real run |
| 22 | `Lee et al. (2021)` | review | Add DOI before publication; author-year alone cannot be verified |
| 23 | `(Lee 1822)` | review | Add DOI before publication; author-year alone cannot be verified |

## Next steps

Run a verifying audit with full API access by wiring a research client:

```python
from vaultlab.research import ResearchClient
from vaultlab.citations import audit_file

report = audit_file(
    'draft.md',
    research_client=ResearchClient(),
    kb_dir='G:/My Drive/Knowledge/<kb-name>',
)
print(report.action_items)
```

_Bucket counts: {'review': 7, 'ok': 2, 'critical': 1}_
