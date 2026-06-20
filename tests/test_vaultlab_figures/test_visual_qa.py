from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


def _render_small_png(path: Path) -> Path:
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(2, 2))
    ax.plot([0, 1, 2], [0, 1, 0])
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return path


def test_visual_qa_runs_layout_audit_and_writes_sidecars(tmp_path: Path) -> None:
    from vaultlab.figures.understand.visual_qa import VisualQAResult, visual_qa_figure

    png = _render_small_png(tmp_path / "toy.png")

    result = visual_qa_figure(png, run_vision=False)

    assert isinstance(result, VisualQAResult)
    assert result.png == str(png)
    assert result.vision_ran is False
    assert result.layout_severity in {"pass", "warn", "fail"}
    assert result.verdict in {"PASS", "WARN", "FAIL"}
    assert any(finding.source == "layout" for finding in result.findings)
    assert any(
        finding.source == "layout" and finding.severity == "pass" for finding in result.findings
    )
    assert (tmp_path / "toy.png.visual_qa.json").exists()
    assert (tmp_path / "toy.png.visual_qa.md").exists()
    assert "Visual QA" in result.to_markdown()
    assert result.to_dict()["verdict"] == result.verdict


def test_visual_qa_fake_vision_failure_controls_verdict(tmp_path: Path) -> None:
    from vaultlab.figures.understand.visual_qa import visual_qa_figure

    png = _render_small_png(tmp_path / "toy.png")

    def fake_verify_fn(**_: Any) -> dict[str, Any]:
        return {
            "defects": [
                {
                    "severity": "fail",
                    "message": "axis labels collide with tick labels",
                    "fix": "Increase bottom margin and rerender.",
                }
            ],
            "legibility": "Key labels are not readable.",
            "supports_conclusion": False,
        }

    result = visual_qa_figure(
        png,
        conclusion="The toy line rises then falls.",
        run_vision=True,
        verify_fn=fake_verify_fn,
    )

    assert result.verdict == "FAIL"
    assert result.vision_ran is True
    assert any(
        finding.source == "vision" and finding.severity == "fail"
        and "axis labels collide" in finding.message
        for finding in result.findings
    )


def test_visual_qa_skips_vision_gracefully_without_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vaultlab.figures.understand import visual_qa as module
    from vaultlab.figures.understand.visual_qa import visual_qa_figure

    png = _render_small_png(tmp_path / "toy.png")

    def no_key(_: str | None) -> str:
        raise RuntimeError("no API key")

    monkeypatch.setattr(module, "_resolve_api_key", no_key)

    result = visual_qa_figure(png, run_vision=True)

    assert result.vision_ran is False
    assert any(
        finding.source == "vision" and finding.severity == "pass"
        and "vision QA skipped: no API key" in finding.message
        for finding in result.findings
    )


def test_visual_qa_markdown_lists_fix_items(tmp_path: Path) -> None:
    from vaultlab.figures.understand.visual_qa import VisualQAFinding, VisualQAResult

    result = VisualQAResult(
        verdict="WARN",
        findings=[
            VisualQAFinding(
                source="vision",
                severity="warn",
                message="legend is hard to read",
                fix="Increase legend font size.",
            )
        ],
        layout_severity="pass",
        vision_ran=True,
        png=str(tmp_path / "toy.png"),
    )

    markdown = result.to_markdown()

    assert "## What to fix" in markdown
    assert "Increase legend font size." in markdown
