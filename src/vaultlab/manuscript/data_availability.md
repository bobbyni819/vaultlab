---
title: Data Availability statements
type: methodology
---

# Data Availability statements

`vaultlab.manuscript.data_availability` provides the DAS repository registry,
FAIR checklist, scenario templates, heuristic audit, and provenance-writing
helper for manuscript data-availability sections.

## Populate the DAS from figure coverage manifests

Figure publication bundles can emit coverage sidecars named
`*.coverage.json`. Each sidecar is read through
`CoverageManifest.read_json(...)`, and its `source_data` entries can be
summarized for the manuscript DAS:

```python
from vaultlab.manuscript.data_availability import (
    data_sources_from_coverage,
    merge_into_das,
)

coverage_sources = data_sources_from_coverage("Output/my-project/figures/coverage")
print(coverage_sources.to_markdown())
draft = coverage_sources.to_das_draft()
statement = merge_into_das(existing_statement, coverage_sources)
```

The coverage-derived draft is additive. It links source-data files to the
figures that use them, deduplicates shared files across manifests, includes
the first eight characters of any recorded SHA-256 hash in the markdown table,
and adds an author-review note if coverage sidecars disagree about a hash.

The draft does not assert repository deposition. If any source looks like a
local path rather than a DOI, URL, or common accession, the draft keeps an
accession-based deposit TODO line so authors can finalize the DAS before
submission.
