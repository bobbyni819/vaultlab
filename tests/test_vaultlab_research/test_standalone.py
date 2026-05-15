"""Standalone integration test for vaultlab.research.

Implements north-star Criterion #3 ("plug-in companion"): the primary
entrypoints of ``vaultlab.research`` must be invocable from a fresh
``tmp_path`` fixture without any prior vaultlab state (no KB, no
``~/.config/`` entries, no cached API config).

External network calls are mocked — the test verifies the public surface
plugs in cleanly, not that PubMed is reachable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_research_client_runs_standalone_from_fresh_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``ResearchClient`` initializes against a fresh-state config and
    ``client.search(...)`` returns Paper objects when the underlying API
    layer is mocked.

    Demonstrates: a new user with no ``~/.config/bobby_research/`` and no
    KB-relative ``research_apis.json`` can still construct the client by
    pointing ``VAULTLAB_RESEARCH_API_CONFIG`` at a one-key JSON file.
    """
    # Fully isolate from any host-machine config.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))

    # Minimal config — one key turns on at least one source so
    # ``get_config`` doesn't raise FileNotFoundError.
    api_config = tmp_path / "research_apis.json"
    api_config.write_text(json.dumps({"ncbi_api_key": "test-fake-key"}))
    monkeypatch.setenv("VAULTLAB_RESEARCH_API_CONFIG", str(api_config))

    # Reset module-level cache so a previous test's config doesn't leak.
    from vaultlab.research import config as research_config

    research_config.reload()

    from vaultlab.research import Paper, ResearchClient

    # Mock the unified_search underneath ``ResearchClient.search`` so the
    # test never hits the network.
    fake_paper = Paper(
        title="Standalone test paper",
        authors=["Test A"],
        year=2026,
        journal="Journal of Standalone Tests",
        doi="10.0000/test.0001",
    )

    def fake_unified_search(query, max_results, sources, **clients):
        return [fake_paper]

    monkeypatch.setattr(
        "vaultlab.research.search.unified_search",
        fake_unified_search,
    )

    client = ResearchClient(config_path=str(api_config))
    results = client.search("anything", max_results=5)

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0].doi == "10.0000/test.0001"
    assert results[0].title.startswith("Standalone")
