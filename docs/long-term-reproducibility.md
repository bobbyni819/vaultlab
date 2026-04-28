# Long-term reproducibility

vaultlab is intentionally NOT pinned to specific Claude model versions. We use whatever Anthropic's most-recent robust model is at runtime. This means:

✓ As Claude improves, vaultlab gets better automatically
✓ Citation-verification gets more accurate; hallucination rates drop
✓ Cluster interpretations get richer

✗ Specific text/annotation outputs are NOT byte-identical year over year
✗ A 2026 cluster annotation may differ from a 2028 re-run on the same data

## What IS reproducible across years

- The pipeline structure (which steps ran, with what parameters)
- All non-LLM steps (segmentation, clustering, statistics) — fully deterministic with seeds (default 42)
- The `.provenance.json` record (full audit trail per output)
- The `.method.md` narrative (full method description per output)
- Citation existence (DOI/PMID checks are deterministic)

## What is NOT byte-reproducible

- LLM-generated text (annotations, captions, drafts) — these may improve over time
- LLM-judged citation verdicts (a stronger model may upgrade `WEAKLY_SUPPORTED` → `SUPPORTED` or vice versa)

## Best practice for citing analyses in papers

When reporting an analysis in a paper, **snapshot the LLM-generated outputs** by checking them into your project's KB at the time of analysis. Future re-runs verify the methodology, not the prose.

Specifically, store:
- The figure (PNG)
- Its `.provenance.json` and `.method.md`
- Any LLM-generated cluster annotations / captions / draft sections — committed to your KB at the time you locked the analysis

When a reviewer asks *"can I reproduce this?"* — they re-run the methodology (deterministic), not the prose (improves over time).

## Per-output provenance schema

Every output writes a `<output>.provenance.json` recording:

```json
{
  "produced_at": "2026-04-28T14:30:00Z",
  "produced_by": "vaultlab.figures.recipes.umap_clusters",
  "vaultlab_version": "0.1.0",
  "vaultlab_git_commit": "5ba9d27f",
  "claude_model": "claude-opus-4-7",
  "claude_temperature": 0.0,
  "key_packages": {"scanpy": "1.10.2", "leidenalg": "0.10.1"},
  "inputs": [{"path": "...", "sha256": "..."}],
  "params": {"resolution": 0.8, "random_state": 42},
  "outputs": [{"path": "Figure_1.png", "sha256": "..."}]
}
```

The `claude_model` field captures which model was used. A 2028 re-run that used a newer model will have a different `claude_model` field — that's the audit trail.

## What vaultlab guarantees forward (file 21 forward-compat)

- `.vaultlab-project.json` schema is **additive only** — old configs keep working
- `manifest.json` per-run schema is **additive only**
- KB folder layout is **additive only**
- Slash command names are **stable** (deprecation warnings before removal)
- Role identifiers are **stable** (prompts can change; identifiers cannot)
- Output folder naming (`runs/<run-id>/`) is **stable**

vaultlab v0.1's outputs remain readable + interpretable in v0.2, v0.3, etc.

## What vaultlab does NOT promise

- **Identical LLM text outputs** between vaultlab versions
- **Identical citation verdicts** when Claude models change
- **Backwards compatibility for v0.0.x scaffold artifacts** (alpha — pre-stability)

## Self-hosted models?

vaultlab does not currently support self-hosted models (Llama, Qwen, etc.). If a user contributes a clean adapter, we'd accept it — but it's not on the v0.1 or v0.2 roadmap.
