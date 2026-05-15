"""Tests for ``vaultlab demo`` — the one-command first-run experience.

Sub-goal 1.4 of the north-star plan: a fresh user runs ``vaultlab demo`` and
produces a real audit-clean .pptx + provenance sidecars from bundled sample
data, with no network calls and no API keys.

These tests pin the contract:

- :func:`vaultlab.cli.demo.run_demo` writes a .pptx artifact and returns its path
- Provenance sidecars (.provenance.json + .method.md) land next to the .pptx
- Bundled sample data ships inside the package (paper metadata + figures)
- Re-running into the same dir is idempotent (no crashes on existing files)
- Synthetic runtime is fast (<30s) — the 5-min user-facing bar is for the
  end-to-end smoke test, not this unit test
- ``main([...])`` dispatches via the existing CLI argv handler
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from vaultlab.cli import main as cli_main
from vaultlab.cli.demo import main as demo_main
from vaultlab.cli.demo import run_demo

# ---------------------------------------------------------------------------
# Bundled sample data — ships inside the package
# ---------------------------------------------------------------------------


def test_bundled_paper_metadata_is_present():
    """``src/vaultlab/data/demo/paper.json`` must ship with the package."""
    from vaultlab.cli import demo as demo_mod

    paper_path = demo_mod._bundled_paper_path()
    assert paper_path.is_file(), f"Sample paper metadata missing: {paper_path}"
    meta = json.loads(paper_path.read_text(encoding="utf-8"))
    # Minimum required keys
    for key in ("title", "authors", "doi", "abstract"):
        assert key in meta, f"Sample paper.json missing required key: {key}"
    # Must be a real OA paper — not a placeholder
    assert meta["title"], "Sample paper title is empty"
    assert isinstance(meta["authors"], list) and meta["authors"], "Authors must be non-empty list"
    assert meta["doi"], "DOI is empty"


def test_bundled_figures_are_present_and_small():
    """At least one PNG figure ships in ``data/demo/figures/``, all <200KB."""
    from vaultlab.cli import demo as demo_mod

    fig_dir = demo_mod._bundled_figures_dir()
    assert fig_dir.is_dir(), f"Bundled figures dir missing: {fig_dir}"
    pngs = sorted(fig_dir.glob("*.png"))
    assert pngs, f"No PNG figures in {fig_dir}"
    for p in pngs:
        size_kb = p.stat().st_size / 1024
        assert size_kb < 200, f"Bundled figure {p.name} is {size_kb:.0f} KB (must be <200 KB)"


# ---------------------------------------------------------------------------
# run_demo() contract
# ---------------------------------------------------------------------------


def test_run_demo_writes_pptx(tmp_path):
    """``run_demo(out_dir)`` writes a .pptx file and returns its path."""
    out = run_demo(tmp_path / "demo_out")
    assert out.suffix == ".pptx"
    assert out.is_file()
    # Non-trivial size — a real pptx with 5+ slides is >5 KB easily
    assert out.stat().st_size > 5_000, f"Generated deck is suspiciously small: {out.stat().st_size}"


def test_run_demo_writes_provenance_sidecars(tmp_path):
    """The .provenance.json + .method.md sidecars exist next to the .pptx."""
    out = run_demo(tmp_path / "demo_out")
    json_sidecar = out.with_name(out.name + ".provenance.json")
    method_sidecar = out.with_name(out.name + ".method.md")
    assert json_sidecar.is_file(), f"Missing provenance JSON: {json_sidecar}"
    assert method_sidecar.is_file(), f"Missing method markdown: {method_sidecar}"

    # Sanity check the JSON is well-formed and references the demo
    data = json.loads(json_sidecar.read_text(encoding="utf-8"))
    assert data["generated_by"].startswith("vaultlab.cli.demo"), data["generated_by"]
    assert data["kind"] == "slide_deck"
    assert "demo" in data.get("tags", []), data.get("tags")


def test_run_demo_copies_sample_inputs_to_out_dir(tmp_path):
    """Demo copies bundled inputs to ``<out>/inputs/`` so users can inspect them."""
    out = run_demo(tmp_path / "demo_out")
    inputs_dir = out.parent / "inputs"
    assert inputs_dir.is_dir(), f"Inputs dir not created: {inputs_dir}"
    assert (inputs_dir / "paper.json").is_file(), "Sample paper.json not copied"
    figs = list((inputs_dir / "figures").glob("*.png"))
    assert figs, "No figures copied to inputs/"


def test_run_demo_default_out_dir_is_relative(tmp_path, monkeypatch):
    """Calling ``run_demo()`` with no args writes to ``./vaultlab-demo-out``."""
    monkeypatch.chdir(tmp_path)
    out = run_demo()
    assert out.parent.name == "vaultlab-demo-out"
    assert out.is_file()


def test_run_demo_is_idempotent(tmp_path):
    """Running twice into the same dir must not crash."""
    target = tmp_path / "demo_out"
    out1 = run_demo(target)
    assert out1.is_file()
    # Second run — should overwrite cleanly, not raise
    out2 = run_demo(target)
    assert out2.is_file()
    assert out1 == out2


def test_run_demo_fast_synthetic_runtime(tmp_path):
    """Unit-test runtime bar: <30s for the bundled deck (real user bar is <5min)."""
    t0 = time.time()
    run_demo(tmp_path / "demo_out")
    elapsed = time.time() - t0
    assert elapsed < 30.0, f"Demo took {elapsed:.1f}s; must be <30s for the unit bar"


def test_run_demo_no_network_calls(tmp_path, monkeypatch):
    """Demo must not hit the network — it should work fully offline.

    Sentinel: replace ``socket.socket`` so any attempt to open a TCP/UDP
    socket raises. urllib/httpx/requests all ultimately go through
    ``socket.socket``.
    """
    import socket

    real_socket = socket.socket

    class _BlockedSocket:
        def __init__(self, *a, **kw):
            raise RuntimeError("demo attempted a network call; demo must be offline")

    monkeypatch.setattr(socket, "socket", _BlockedSocket)
    try:
        out = run_demo(tmp_path / "demo_out")
        assert out.is_file()
    finally:
        # Restore for any teardown machinery that needs it
        monkeypatch.setattr(socket, "socket", real_socket)


# ---------------------------------------------------------------------------
# CLI dispatch — both ``vaultlab demo`` and ``python -m vaultlab.cli.demo``
# ---------------------------------------------------------------------------


def test_demo_main_with_explicit_out_dir(tmp_path, capsys):
    """``vaultlab demo --out-dir <path>`` exits 0 and prints the artifact path."""
    rc = demo_main(["--out-dir", str(tmp_path / "cli_out")])
    assert rc == 0
    captured = capsys.readouterr().out
    assert "artifact:" in captured
    assert ".pptx" in captured
    assert (tmp_path / "cli_out" / "deck.pptx").is_file()


def test_demo_main_help_does_not_crash(capsys):
    """``vaultlab demo --help`` exits cleanly via argparse SystemExit."""
    with pytest.raises(SystemExit) as exc:
        demo_main(["--help"])
    assert exc.value.code == 0


def test_vaultlab_demo_subcommand_dispatches(tmp_path, capsys):
    """``vaultlab demo --out-dir <path>`` works through the top-level CLI."""
    rc = cli_main(["demo", "--out-dir", str(tmp_path / "top_cli_out")])
    assert rc == 0
    assert (tmp_path / "top_cli_out" / "deck.pptx").is_file()


def test_top_level_usage_mentions_demo(capsys):
    """The CLI help output advertises the new ``demo`` subcommand."""
    rc = cli_main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "demo" in out.lower(), "Top-level usage must mention the demo command"
