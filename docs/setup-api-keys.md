# Literature API key setup for vaultlab

This walks through getting the **literature search API keys** that power vaultlab's `vaultlab.research` module, and clarifies when (if ever) you need an Anthropic API key.

## Anthropic API key — do you need one?

Short answer: **most users do not.** It depends on how you call vaultlab.

| How you call vaultlab | Anthropic API key? | Why |
|---|---|---|
| Slash commands inside a Claude Code session (e.g. `/lit-arc`, `/build-deck`) | **No** | Claude Code provides LLM access via your existing subscription. The vaultlab slash command body delegates the "read this PDF, write this paragraph" work back to your Claude Code session via the `reader=` / `narrator=` callbacks on `run_lit_arc` (and the equivalent prepare/render pairs on individual functions). No SDK call is made. |
| Plain Python script that calls `summarize_paper(...)` or `run_lit_arc(...)` directly with no callbacks | **Yes** | Those functions hit `anthropic.Messages.create` via the SDK. Get a key at https://console.anthropic.com and put it in `ANTHROPIC_API_KEY` (or `anthropic_api_key` in `~/.config/research/research_apis.json`). |
| MCP server / headless CLI / CI job | **Yes** | Same as Python-API mode — there is no Claude Code session to delegate to. |

If you only ever invoke vaultlab from inside a Claude Code session, you can skip the Anthropic section entirely and just configure the literature keys below.

### Force the Claude-Code-callable path explicitly

The new path is opt-in via callbacks. Concretely:

```python
from vaultlab.research import run_lit_arc, prepare_summary_task, render_summary_from_response

# Inside a slash command body — Claude Code reads the PDF in-session.
result = run_lit_arc(
    topic,
    kb_root=kb_root,
    reader=my_claude_code_reader,      # Read PDF in-session, return JSON
    narrator=my_claude_code_narrator,  # Read summaries, return arc paragraphs
)
```

If you call `run_lit_arc(topic, kb_root=...)` with no callbacks, vaultlab uses the SDK path — and **that** path needs an Anthropic API key.

See `.claude/commands/lit-arc.md` for the canonical Claude-Code body.

---

## Literature API keys

This walks through getting the **literature search API keys** that power vaultlab's `vaultlab.research` module.

## Quick summary

For most users, **NCBI is the only one you need.** The others are nice-to-have.

| Service | Get one | Friction | Recommended? |
|---|---|---|---|
| **NCBI E-utilities** | https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/ | 5 min | ✅ Strongly |
| **Semantic Scholar** | https://www.semanticscholar.org/product/api | 5 min for personal | ✅ Recommended |
| **bioRxiv** | https://api.biorxiv.org/ — public, no key | 0 min | ✅ Auto |
| **CrossRef** | https://www.crossref.org/services/metadata-delivery/rest-api/ — public, no key | 0 min | ✅ Auto |
| **paperclip MCP** | Public hosted at https://paperclip.gxl.ai | 0 min for client; potentially institutional verify | Recommended for exploratory |
| **Springer Nature** | https://dev.springernature.com/ | Variable; institutional or applied-for | Optional |
| **Elsevier (ScienceDirect)** | https://dev.elsevier.com/ | Institutional approval (Duke has access) | Optional; institutional |

If you're at a university with Springer/Elsevier access (most R1 universities), check with your library before applying personally — you may already have institutional access tokens.

---

## NCBI E-utilities (PubMed) — get this one

Without an API key, NCBI rate-limits you to 3 requests/second. With a key, 10 requests/second + Higher daily quotas. For any serious lit search, this matters.

### Steps

1. Create a free NCBI account at https://www.ncbi.nlm.nih.gov/account/
2. Sign in
3. Click your username → "Account settings"
4. Scroll to "API Key Management"
5. Click "Create an API Key"
6. Copy the key

### Configure in vaultlab

Edit `~/.config/vaultlab/secrets.toml` (create if missing):

```toml
[literature]
ncbi_api_key = "your-key-here"
ncbi_email = "you@example.com"  # required by NCBI; used for low-priority emails about API issues
```

Or via environment variable (overrides the config file):

```bash
export NCBI_API_KEY="..."
export NCBI_EMAIL="you@example.com"
```

### Verify it works

In a Claude Code session:

```
> /lit-search "M2 channel proton transport" --max-results 5
```

(Once `/lit-search` is implemented in v0.1.0; for now `vaultlab doctor` checks the key.)

---

## Semantic Scholar (S2)

Provides cleaner citation graphs + paper-similarity search than PubMed alone. Public API works without a key (low rate limit); personal key gets higher limits.

### Steps

1. Apply at https://www.semanticscholar.org/product/api
2. Fill the form (research use is approved quickly)
3. Receive your API key by email (~24h turnaround)

### Configure

```toml
[literature]
semantic_scholar_api_key = "..."
```

---

## paperclip MCP (8M-paper corpus)

Public hosted MCP server at https://paperclip.gxl.ai. Provides grep/map/reduce queries over a curated 8M-paper biomedical corpus. **No personal key needed for client access.**

If your institution restricts MCP server connections, work with IT; otherwise just point vaultlab at it:

```toml
[literature]
paperclip_mcp_url = "https://paperclip.gxl.ai"  # default
```

---

## Springer Nature (institutional)

If your institution doesn't already have access, you can apply for a personal API account.

### Steps

1. Register at https://dev.springernature.com/
2. Wait for approval (variable; check spam folder)
3. Once approved, generate a key in the developer portal

### Configure

```toml
[literature]
springer_api_key = "..."
```

---

## Elsevier / ScienceDirect (institutional)

ScienceDirect API access is **institutional only** — you cannot apply as an individual researcher. If Duke (or your university) has a developer agreement, you can issue a key under that.

### Steps for institutional users

1. Talk to your library's data services team
2. They issue you a developer key tied to the institutional agreement
3. Configure in vaultlab

```toml
[literature]
elsevier_api_key = "..."
elsevier_inst_token = "..."  # institutional token
```

---

## CrossRef (no key needed)

CrossRef's REST API is fully public and unlimited for normal use. vaultlab uses it automatically.

```toml
# No config needed — vaultlab queries CrossRef without auth
```

---

## bioRxiv (no key needed)

bioRxiv's API is fully public. vaultlab queries it automatically.

```toml
# No config needed — vaultlab queries bioRxiv without auth
```

---

## What if I don't have all these keys?

vaultlab gracefully degrades. With ONLY NCBI, you get:
- Full PubMed search
- CrossRef + bioRxiv (no keys)
- Semantic Scholar (lower rate limits via public API)
- paperclip MCP (no key needed)

That covers ~95% of biomedical literature searches.

What you LOSE without Springer / Elsevier:
- Springer-specific full-text retrieval (you can still find Springer papers via PubMed; you just can't pull full text via Springer's own API)
- ScienceDirect full-text retrieval (same; manual download still works)

For most v0.1.0 use cases, **NCBI alone is enough.** Add others as you actually hit rate limits.

---

## Configuration discipline

Keys live in `~/.config/vaultlab/secrets.toml` (per-machine, gitignored). Never commit this file.

Or use environment variables (per-session, useful for CI/scripts):

```bash
export NCBI_API_KEY=...
export NCBI_EMAIL=...
export SEMANTIC_SCHOLAR_API_KEY=...
export SPRINGER_API_KEY=...
export ELSEVIER_API_KEY=...
```

vaultlab reads env vars first, then the config file.

---

## Verify everything works

```bash
vaultlab doctor
```

Output should show one line per literature source:

```
✓ Literature APIs:
  ✓ NCBI E-utilities (key configured)
  ✓ Semantic Scholar (key configured)
  ✓ paperclip MCP (reachable at paperclip.gxl.ai)
  ✓ CrossRef (public)
  ✓ bioRxiv (public)
  ⚠ Springer Nature — no key configured (skipping)
  ⚠ Elsevier — no key configured (skipping)
```

Everything with a ✓ is wired in to `/lit-search` and `/cite audit`. Things with ⚠ are skipped silently.

## See also

- [`getting-started.md`](getting-started.md) — overall first-10-minutes walkthrough
- [`setup-google.md`](setup-google.md) — Google Workspace OAuth (for life-context, not literature)
- `vaultlab.research.sources` — Python API
- `docs/comparison.md` — vs PaperQA / FutureHouse / scanpy
