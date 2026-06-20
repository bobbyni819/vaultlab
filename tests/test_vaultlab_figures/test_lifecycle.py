from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image

from vaultlab.figures.index import (
    INDEX_FILENAME,
    FigureStage,
    archive_superseded,
    find_existing_for_claim,
    find_figure_pairs,
    get_figure_stage,
    list_by_stage,
    load_figure_index,
    manuscript_figures,
    set_figure_stage,
    update_figure_index,
)


def _figure(path: Path) -> Path:
    Image.new("RGB", (2, 2), color=(128, 64, 32)).save(path)
    return path


def _index_path(kb_root: Path, project_slug: str) -> Path:
    return kb_root / project_slug / INDEX_FILENAME


def _read_index(kb_root: Path, project_slug: str) -> list[dict[str, Any]]:
    raw = json.loads(_index_path(kb_root, project_slug).read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    return [entry for entry in raw if isinstance(entry, dict)]


def test_set_and_get_figure_stage_records_history(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    project = "project"
    fig = _figure(tmp_path / "fig.png")
    entry = update_figure_index(kb_root, project, fig, related_claims=["claim-1"])

    assert get_figure_stage(kb_root, project, figure_id_or_path=entry["path_hash"]) is FigureStage.EXPLORATORY

    changed = set_figure_stage(
        kb_root,
        project,
        figure_id_or_path=entry["path_hash"],
        stage=FigureStage.MANUSCRIPT,
        ts="2026-06-20T09:00:00",
    )

    assert changed is True
    assert get_figure_stage(kb_root, project, figure_id_or_path=fig) is FigureStage.MANUSCRIPT
    stored = _read_index(kb_root, project)[0]
    assert stored["lifecycle_stage"] == "manuscript"
    assert stored["superseded_by"] is None
    assert stored["stage_history"] == [
        {"stage": "manuscript", "ts": "2026-06-20T09:00:00"}
    ]


def test_list_by_stage_and_manuscript_figures_filter(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    project = "project"
    manuscript = update_figure_index(kb_root, project, _figure(tmp_path / "manuscript.png"))
    candidate = update_figure_index(kb_root, project, _figure(tmp_path / "candidate.png"))

    assert set_figure_stage(
        kb_root,
        project,
        figure_id_or_path=manuscript["path_hash"],
        stage=FigureStage.MANUSCRIPT,
        ts="2026-06-20T09:00:00",
    )
    assert set_figure_stage(
        kb_root,
        project,
        figure_id_or_path=candidate["path_hash"],
        stage=FigureStage.CANDIDATE,
        ts="2026-06-20T09:01:00",
    )

    assert [entry["path_hash"] for entry in list_by_stage(kb_root, project, FigureStage.MANUSCRIPT)] == [
        manuscript["path_hash"]
    ]
    assert [entry["path_hash"] for entry in manuscript_figures(kb_root, project)] == [
        manuscript["path_hash"]
    ]


def test_find_existing_for_claim_excludes_archived_by_default(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    project = "project"
    active = update_figure_index(
        kb_root,
        project,
        _figure(tmp_path / "active.png"),
        related_claims=["claim-1", "B cells expand in region A"],
    )
    archived = update_figure_index(
        kb_root,
        project,
        _figure(tmp_path / "archived.png"),
        related_claims=["claim-1", "B cells expand in region A"],
    )
    assert archive_superseded(
        kb_root,
        project,
        figure_id_or_path=archived["path_hash"],
        superseded_by=active["path_hash"],
        ts="2026-06-20T09:02:00",
    )

    by_id = find_existing_for_claim(kb_root, project, claim_id="claim-1")
    by_text = find_existing_for_claim(kb_root, project, claim_text="B cells expand in region A")
    including_archived = find_existing_for_claim(
        kb_root,
        project,
        claim_id="claim-1",
        include_archived=True,
    )

    assert [entry["path_hash"] for entry in by_id] == [active["path_hash"]]
    assert [entry["path_hash"] for entry in by_text] == [active["path_hash"]]
    assert {entry["path_hash"] for entry in including_archived} == {
        active["path_hash"],
        archived["path_hash"],
    }


def test_find_existing_for_claim_supports_claim_dicts(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    project = "project"
    fig = _figure(tmp_path / "claim-dict.png").resolve()
    _index_path(kb_root, project).parent.mkdir(parents=True)
    _index_path(kb_root, project).write_text(
        json.dumps(
            [
                {
                    "path_hash": "claimdicthash",
                    "figure_path": str(fig),
                    "claims": [
                        {
                            "claim_id": "ledger-claim-1",
                            "text": "Macrophages localize to the tumor border.",
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    by_id = find_existing_for_claim(kb_root, project, claim_id="ledger-claim-1")
    by_text = find_existing_for_claim(
        kb_root,
        project,
        claim_text="Macrophages localize to the tumor border.",
    )

    assert [entry["path_hash"] for entry in by_id] == ["claimdicthash"]
    assert [entry["path_hash"] for entry in by_text] == ["claimdicthash"]


def test_archive_superseded_marks_registry_without_deleting_file(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    project = "project"
    fig = _figure(tmp_path / "old.png")
    entry = update_figure_index(kb_root, project, fig)

    changed = archive_superseded(
        kb_root,
        project,
        figure_id_or_path=entry["path_hash"],
        superseded_by="new-figure-id",
        ts="2026-06-20T09:03:00",
    )

    assert changed is True
    assert fig.exists()
    stored = _read_index(kb_root, project)[0]
    assert stored["lifecycle_stage"] == "superseded"
    assert stored["superseded_by"] == "new-figure-id"
    assert stored["stage_history"] == [
        {"stage": "superseded", "ts": "2026-06-20T09:03:00"}
    ]


def test_stageless_legacy_entry_reads_as_exploratory(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    project = "project"
    fig = _figure(tmp_path / "legacy.png").resolve()
    _index_path(kb_root, project).parent.mkdir(parents=True)
    _index_path(kb_root, project).write_text(
        json.dumps(
            [
                {
                    "path_hash": "legacyhash",
                    "figure_path": str(fig),
                    "related_claims": ["legacy claim"],
                }
            ]
        ),
        encoding="utf-8",
    )

    assert get_figure_stage(kb_root, project, figure_id_or_path="legacyhash") is FigureStage.EXPLORATORY
    assert [entry["path_hash"] for entry in list_by_stage(kb_root, project, FigureStage.EXPLORATORY)] == [
        "legacyhash"
    ]


def test_existing_figure_index_update_load_and_pairs_still_work(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    project = "project"
    first = _figure(tmp_path / "first.png")
    second = _figure(tmp_path / "second.png")

    first_entry = update_figure_index(
        kb_root,
        project,
        first,
        source="own",
        recipe_id="marker_dot_plot",
        related_claims=["claim-1"],
        doi_or_data_source="dataset-1",
    )
    refreshed = update_figure_index(
        kb_root,
        project,
        first,
        source="own",
        recipe_id="marker_dot_plot",
        related_claims=["claim-1", "claim-2"],
        doi_or_data_source="dataset-1",
    )
    second_entry = update_figure_index(kb_root, project, second, recipe_id="marker_dot_plot")

    loaded = load_figure_index(kb_root, project)
    pairs = find_figure_pairs(first, kb_root, project)

    assert first_entry["path_hash"] == refreshed["path_hash"]
    assert len(loaded) == 2
    assert {entry["path_hash"] for entry in loaded} == {
        refreshed["path_hash"],
        second_entry["path_hash"],
    }
    assert pairs
    assert pairs[0]["entry"]["path_hash"] == second_entry["path_hash"]
