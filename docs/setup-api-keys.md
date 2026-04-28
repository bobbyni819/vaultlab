# API key setup for vaultlab

> **Status:** stub. Full walkthrough lands as part of `vaultlab setup` CLI implementation.

vaultlab uses external APIs for literature search and LLM operations. Most are optional; only Anthropic is strongly recommended.

## Required (recommended)

| Service | Why | Get one |
|---|---|---|
| **Anthropic Claude** | Powers all LLM-assisted steps (cluster annotation, citation verification, manuscript drafting). vaultlab works without it but loses most value. | https://console.anthropic.com |

## Optional

| Service | What it adds | Get one |
|---|---|---|
| NCBI E-utilities | Higher rate limits for PubMed (3/s vs 1/s). Recommended for serious lit search. | https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/ |
| Semantic Scholar | Higher rate limits for paper retrieval | https://www.semanticscholar.org/product/api |
| Springer Nature | Springer-specific full-text retrieval | https://dev.springernature.com/ |
| bioRxiv | bioRxiv preprint API access | https://api.biorxiv.org/ |
| Elsevier (ScienceDirect) | Elsevier full-text where authorized | https://dev.elsevier.com/ |
| paperclip MCP | Exploratory grep across 8M papers | https://paperclip.gxl.ai |

## How to configure

```bash
vaultlab setup            # interactive — asks for each key, validates, stores
```

Stored at `~/.config/vaultlab/keys.json` (gitignored, per-machine).

You can also set environment variables (override config file):

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export NCBI_API_KEY="..."
```

## Demo without keys

```bash
vaultlab demo pbmc3k --no-llm
```

Runs the full pipeline using **canned annotations and captions**. Useful for first impressions before committing to API keys.

## Coming in this doc

- Per-service step-by-step screenshots
- Cost expectations per pipeline run
- How to rotate keys
- HIPAA-tier Anthropic setup (link to Anthropic enterprise; not handled by vaultlab)
