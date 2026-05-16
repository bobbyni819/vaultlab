"""vaultlab — Claude Code setup for biological research.

Literature, knowledge base, data analysis, figures, and manuscripts in
one workspace. Runs inside Claude Code; KB is plain markdown on
whatever cloud sync you already use.

This is the slim public barrel. The full surface is at submodule level:

    from vaultlab.research import ResearchClient, search_papers
    from vaultlab.citations import audit_file, EvidenceRecord
    from vaultlab.kb import init_kb, ingest, search
    from vaultlab.figures import ManuscriptFigure, recipes
    from vaultlab.slides import Deck
    from vaultlab.manuscript import ManuscriptProject
    from vaultlab.data import discover, ingest as data_ingest
    from vaultlab.config import ProjectConfig, load_project_config

For the orchestration core (meetings, roles, runner, workflows), see:

    from vaultlab.meetings import build_meeting, Agenda
    from vaultlab.runner import ClaudeCodeRunner, bounded_loop
    from vaultlab.workflows import run_workflow

See README.md, CLAUDE.md, and AGENTS.md.
"""

from __future__ import annotations

__version__ = "0.0.6"

__all__ = [
    "__version__",
]
