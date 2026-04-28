# Data privacy

vaultlab uses Anthropic's Claude API. **Prompt content is sent to Anthropic.** vaultlab is **NOT HIPAA-compliant.**

Do **NOT** use vaultlab with:
- Protected Health Information (PHI)
- Personally Identifiable Information (PII) of patients
- Data covered by IRB protocols that prohibit external transmission

## What gets sent to Anthropic

When vaultlab makes an LLM call, the prompt content typically includes:
- Excerpts of your data (cluster markers, gene lists, cell counts, manifest summaries)
- Excerpts of your KB notes (if RAG retrieves them)
- Excerpts of papers (when you've ingested them)
- Excerpts of in-progress manuscripts

This is sent over HTTPS to Anthropic per [their Privacy Policy](https://www.anthropic.com/legal/privacy) and [Terms of Service](https://www.anthropic.com/legal/aup).

## What does NOT get sent

- Raw image data (only metadata + summary statistics from images)
- Patient-identifying metadata in your manifests (vaultlab doesn't introspect; YOU control what enters the prompt)
- Anything you don't explicitly invoke an LLM step on

## What you control

- All vaultlab analyses run on **your own machine** (CPU/GPU). No data leaves your machine for analysis.
- LLM steps are explicit. Every call is logged in `<kb>/.vaultlab/runs/<run_id>/trace.jsonl`.
- You can run `vaultlab demo --no-llm` and most pipelines support `--no-llm` to skip LLM steps entirely.

## Compliance

vaultlab is **NOT** intended for use with regulated data. If your work involves:

- **HIPAA**: vaultlab is not configured for HIPAA-compliant Anthropic access. Use Anthropic's enterprise HIPAA tier and configure manually.
- **GDPR**: same — user responsibility.
- **IRB protocols**: confirm your IRB approves cloud LLM transmission of any data subset that touches the prompt.
- **IACUC, FDA, CLIA, etc.**: same — user responsibility.

By using vaultlab, you take full responsibility for compliance with your institutional, IRB, IACUC, and regulatory obligations.

## First-run acknowledgement

`vaultlab setup` requires explicit acknowledgement of these terms before activating LLM-assisted features. The acknowledgement is stored at `~/.config/vaultlab/acknowledgements.json` with timestamp.

## Reporting privacy issues

See [`SECURITY.md`](../SECURITY.md).
