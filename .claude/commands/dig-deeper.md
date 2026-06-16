Explore a paper's citation network — who cites it and what it cites.

## Arguments

`$ARGUMENTS` — A DOI (e.g., `10.1083/jcb.200407073`) or paper title in quotes, plus optional flags:
- `--kb <name>` — check KB status and offer to save discoveries

## Workflow

### 1. Parse arguments

Extract DOI or title from `$ARGUMENTS`, and optional `--kb`.

### 2. Fetch the paper

```python
from bobby_research import ResearchClient

client = ResearchClient()
```

If input contains `/` (looks like a DOI):
```python
paper = client.get_paper(doi)
```

If input is a title, search for it:
```python
results = client.search(title, max_results=5)
# Show matches and ask user to confirm which one
```

If paper not found, report and stop.

### 3. Show paper details

Display full metadata:
- Title, all authors, year, journal
- DOI, PMID (if available)
- Citation count
- Abstract (first 300 chars + "...")
- Link: `https://doi.org/<doi>`

### 4. If --kb provided, check KB status

```python
from bobby_kb import get_kb_path

kb_path = get_kb_path(kb_name)
full_text = client.find_full_text_in_kb(paper, kb_path)
```

Report: "Found in KB" / "Not in KB yet"

### 5. Get citation network

```python
citing = client.get_citations(paper.doi)     # papers that cite this one
references = client.get_references(paper.doi) # papers this one cites
```

### 6. Display citing papers (forward citations)

```
## Cited by (N papers)
| # | Title | Authors | Year | Journal | Cited | DOI |
```

Sort by citation count. Show top 15.

### 7. Display references (backward citations)

```
## References (N papers)
| # | Title | Authors | Year | Journal | Cited | DOI |
```

Sort by citation count. Show top 15.

### 8. Offer next steps

- "Want me to save any of these to your KB?"
- "Want me to dig deeper into one of these citing papers?"
- "Want me to find papers that cite multiple of these?" (intersection)
- "Want me to get AI-based recommendations from these seed papers?"

### 9. Recommendations (if user asks)

```python
seed_dois = [paper.doi] + [p.doi for p in top_citing[:3] if p.doi]
recs = client.get_recommendations(seed_dois)
```

## Examples

```
/dig-deeper 10.1083/jcb.200407073 --kb metabolism
/dig-deeper "galectin-4 sulfatides apical trafficking"
/dig-deeper 10.1038/s41586-024-07159-5
```
