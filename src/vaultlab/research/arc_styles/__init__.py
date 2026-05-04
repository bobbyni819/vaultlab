"""Arc-style prompt registry.

Each ``.md`` file in this package is one rendering style for a
literature lineage arc — same corpus, different framing. The Python
loader (``arc_styles_loader.py``) reads these files and uses them to
override the narrator's system prompt and structural requirements.

Per vaultlab's META PRINCIPLE #1: "Markdown is the user-facing
interface; Python is the engine." Each style is a markdown file with
a YAML frontmatter declaring its name, audience, and structural
requirements; the body is the system prompt + structural guidance the
narrator uses.

Available styles (filename without .md suffix is the style id):

* ``journal_club`` — punchy 3-paragraph intro for journal-club audience
* ``review_paper_strict`` — comprehensive review with thesis, head-to-
  head comparisons, methodology paragraph, hedging discipline
* ``slide_deck_script`` — speaker notes feeding into /build-deck
* ``grant_aims`` — 1-2 paragraph NIH-style background section
* ``precise_scientific`` — tight prose, hedging-strict, citation-heavy

Adding a new style: drop a ``<name>.md`` file in this directory with
the standard frontmatter shape, and it becomes available via
``--style <name>`` immediately. No Python changes required.
"""
