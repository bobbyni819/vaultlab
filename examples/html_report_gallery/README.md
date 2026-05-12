# HTML report gallery — vaultlab.report smoke test

Runs all 6 HTML consumers + 3 interactive editors that ship with
`vaultlab.report` against realistic-shaped fake data. Open the
generated `index.html` to inspect every output side by side.

## Run it

```bash
python examples/html_report_gallery/run_gallery.py
# or open the index in your default browser automatically:
python examples/html_report_gallery/run_gallery.py --open
```

Writes to `examples/html_report_gallery/output/`:

- `index.html` — landing page with cards linking to each consumer
- `deck-audit.html` — `vaultlab.slides.audit_html`
- `litarc.html` — `vaultlab.research.litarc_html`
- `reasoning.html` — `vaultlab.workflows.reasoning_html`
- `citation-audit.html` — `vaultlab.citations.report_html`
- `dossier.html` — `vaultlab.kb.dossier_html`
- `deck-preview.html` — `vaultlab.slides.preview_html`
- `slide-reorder.html` — `vaultlab.report.editors.build_slide_reorder_editor`
- `citation-triage.html` — `vaultlab.report.editors.build_citation_triage_editor`
- `deckplan-tuner.html` — `vaultlab.report.editors.build_deckplan_tuner`

## When to use this

- After editing `vaultlab.report._components` or one of the consumer
  modules — run it to manually inspect that the visual output is still
  correct (the test suite checks structure but not aesthetics).
- As a reference when wiring `vaultlab.report` into a new consumer
  module (copy the pattern from one of the calls in `run_gallery.py`).
- After a fresh `pip install vaultlab[research,citations,slides,kb,figures]`
  to confirm the HTML system is wired end-to-end.

## Tests

`tests/test_examples/test_html_gallery.py` invokes the script end-to-end
in a tmp_path and asserts every expected output is generated and
opens as a parseable HTML document.

## Related

- `Wiki/Concepts/html-output-system.md` — concept article
- `src/vaultlab/report/SKILL.md` — when-to-use HTML vs Markdown
- `Output/Plans/html-and-nature-skills-2026-05-12.html` — the v0.0.4
  plan that drove the system
