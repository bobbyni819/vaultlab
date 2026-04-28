# Compliance disclaimer

**vaultlab is NOT HIPAA-compliant. vaultlab is NOT IRB-approved by any institution. vaultlab is alpha-stage research software.**

If you intend to use vaultlab with regulated data (PHI, PII, IRB-protected, IACUC-protected, FDA/CLIA-relevant data), STOP and consult your institutional compliance office.

## Anthropic's HIPAA-compliant tier

Anthropic offers a HIPAA-compliant Claude API tier for enterprise customers. vaultlab does **NOT** automatically configure or use this tier. If you have institutional HIPAA-compliant access to Claude:

1. Configure your `ANTHROPIC_API_KEY` to point at the HIPAA-compliant endpoint per Anthropic's enterprise documentation
2. Confirm with your IT/compliance office that vaultlab's prompt content fits within your BAA terms
3. Test with non-PHI data first

vaultlab does not validate that your Anthropic configuration is HIPAA-compliant. **You are responsible** for that verification.

## What if I accidentally sent PHI to Claude?

If you accidentally include PHI in a prompt to Anthropic via vaultlab:

1. Stop using vaultlab on the affected project immediately
2. Notify your institution's compliance office
3. Contact Anthropic's enterprise support for incident handling guidance
4. Review your `<kb>/.vaultlab/runs/<run_id>/trace.jsonl` to identify which prompts contained the data

vaultlab logs every LLM call to facilitate this audit.

## Other regulatory contexts

- **GDPR (EU researchers):** same caveats apply. vaultlab does not anonymize data; user responsibility.
- **CLIA / clinical lab:** vaultlab is research software, not clinical software. Do not use for clinical decisions.
- **FDA-regulated workflows:** vaultlab outputs are NOT FDA-validated. They are research artifacts.

## Citation in regulated contexts

If you cite vaultlab in a regulated submission (e.g., IND application), you take responsibility for the validity of that citation. vaultlab makes no representations about clinical or regulatory validity.

## See also

- [`docs/data-privacy.md`](data-privacy.md) — what data leaves your machine
- [`SECURITY.md`](../SECURITY.md) — reporting security issues
