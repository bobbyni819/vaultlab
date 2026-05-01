"""Unit tests for vaultlab.figures.acquisition.

The PMC OA + Springer paths are exercised with a fake polite session and
an in-memory tar.gz built per test.  We verify:

* DOI -> PMCID -> tar URL -> .tar.gz download -> figure extraction.
* NXML caption + label + panel-letter parsing.
* "Unavailable" path for papers with no PMC OA record and no Springer
  figure URLs.
* Cache hit short-circuits the network entirely.
* Tar entries that escape ``cache_dir`` are dropped.
* Canonical cache layout (``cache_dir / <doi-slug> / <figure>.<ext>``).
"""

from __future__ import annotations

import io
import json
import tarfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from vaultlab.figures import acquisition as acq
from vaultlab.figures.acquisition import (
    Figure,
    FigureAcquisitionResult,
    _extract_panels_from_caption,
    _extract_tar_to_dir,
    _parse_elsevier_figures,
    _parse_nxml_figures,
    acquire_figures,
    figure_cache_dir,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    + b"\x00\x00\x00\rIHDR"
    + b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    + b"\x00\x00\x00\rIDATx\xdac\xfc\xff\xff?\x03\x00\x05\xfe\x02\xfe\xa3\x35"
    + b"\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82"
    + (b"\x00" * 200)
)


_SAMPLE_NXML = b"""<?xml version="1.0"?>
<article>
  <body>
    <fig id="fig1">
      <label>Figure 1</label>
      <caption><p>Overview of the system, showing (A) inputs, (B) outputs, and (C) feedback.</p></caption>
      <graphic xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="fig1"/>
    </fig>
    <fig id="fig-S2">
      <label>Figure S2</label>
      <caption><p>Supplementary controls.</p></caption>
      <graphic xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="figS2"/>
    </fig>
  </body>
</article>
"""


def _make_tar_gz(
    *,
    figures: dict[str, bytes],
    nxml: bytes | None = _SAMPLE_NXML,
    article_dir: str = "PMC9999999",
) -> bytes:
    """Build an in-memory PMC-style tar.gz with figures + an NXML."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        if nxml is not None:
            info = tarfile.TarInfo(name=f"{article_dir}/article.nxml")
            info.size = len(nxml)
            tar.addfile(info, io.BytesIO(nxml))
        for name, content in figures.items():
            info = tarfile.TarInfo(name=f"{article_dir}/{name}")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def _make_oa_xml(href: str = "https://example.test/pkg.tar.gz") -> bytes:
    """Build a minimal PMC OA service XML response."""
    return (
        b'<?xml version="1.0"?><OA><records><record id="PMC1">'
        b'<link format="tgz" updated="x" href="' + href.encode() + b'"/>'
        b"</record></records></OA>"
    )


def _make_oa_error_xml() -> bytes:
    return (
        b'<?xml version="1.0"?><OA><records></records>'
        b'<error code="idIsNotOpenAccess">not OA</error></OA>'
    )


@dataclass
class _FakeResponse:
    status_code: int
    content: bytes = b""
    _json: dict[str, Any] | None = None
    headers: dict[str, str] | None = None

    def json(self) -> dict[str, Any]:
        if self._json is None:
            raise ValueError("no json")
        return self._json


class _FakeSession:
    """Tiny stand-in for :class:`acquisition._PoliteSession`.

    ``script`` is a list of ``((source, url_substring), response)`` pairs
    consumed in order.  Unmatched calls return 404.
    """

    def __init__(self, script: list[tuple[tuple[str, str], _FakeResponse]]):
        self._script = list(script)
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def get(
        self,
        source: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        stream: bool = False,
        allow_redirects: bool = True,
    ) -> _FakeResponse | None:
        self.calls.append((source, url, params))
        for i, ((s, frag), resp) in enumerate(self._script):
            if s == source and frag in url:
                self._script.pop(i)
                if resp.headers is None:
                    resp.headers = {}
                return resp
        return _FakeResponse(status_code=404, headers={})


# ---------------------------------------------------------------------------
# _extract_panels_from_caption
# ---------------------------------------------------------------------------


class TestPanelExtraction:
    def test_extracts_simple_panel_letters(self) -> None:
        caption = "Overview showing (A) inputs, (B) outputs, and (C) feedback."
        # The (A), (B), (C) all appear as separate single-letter groups.
        assert _extract_panels_from_caption(caption) == ["A", "B", "C"]

    def test_extracts_grouped_panels(self) -> None:
        caption = "Panels (A, B, C) describe the controls."
        assert _extract_panels_from_caption(caption) == ["A", "B", "C"]

    def test_dedupes_panels(self) -> None:
        caption = "(A) shows X. (A) again. (B) shows Y."
        assert _extract_panels_from_caption(caption) == ["A", "B"]

    def test_handles_empty_caption(self) -> None:
        assert _extract_panels_from_caption("") == []

    def test_ignores_non_letter_content(self) -> None:
        # No bare single letters in parens -> no panels.
        assert _extract_panels_from_caption("Figure shows the result.") == []


# ---------------------------------------------------------------------------
# _parse_nxml_figures
# ---------------------------------------------------------------------------


class TestNxmlParsing:
    def test_parses_label_and_caption(self) -> None:
        meta = _parse_nxml_figures(_SAMPLE_NXML)
        # Keys are the basenames referenced by <graphic xlink:href="...">.
        assert "fig1" in meta
        assert meta["fig1"]["id"] == "fig1"
        assert meta["fig1"]["label"] == "Figure 1"
        assert "Overview of the system" in meta["fig1"]["caption"]

    def test_parses_supplementary_figure(self) -> None:
        meta = _parse_nxml_figures(_SAMPLE_NXML)
        assert "figS2" in meta
        assert meta["figS2"]["id"] == "fig-S2"
        assert meta["figS2"]["label"] == "Figure S2"

    def test_returns_empty_on_bad_xml(self) -> None:
        assert _parse_nxml_figures(b"<not xml") == {}


# ---------------------------------------------------------------------------
# _extract_tar_to_dir
# ---------------------------------------------------------------------------


class TestTarExtraction:
    def test_extracts_figures_and_nxml(self, tmp_path: Path) -> None:
        tar_bytes = _make_tar_gz(
            figures={
                "fig1.png": _PNG_BYTES,
                "figS2.jpg": b"jpegdata" + (b"\xff" * 200),
            },
        )
        figs, nxml = _extract_tar_to_dir(tar_bytes, tmp_path)
        names = sorted(p.name for p in figs)
        assert names == ["figS2.jpg", "fig1.png"][::-1] or names == ["fig1.png", "figS2.jpg"]
        assert nxml == _SAMPLE_NXML
        for f in figs:
            assert f.parent == tmp_path
            assert f.read_bytes()  # file actually wrote bytes

    def test_skips_non_figure_extensions(self, tmp_path: Path) -> None:
        tar_bytes = _make_tar_gz(
            figures={
                "fig1.png": _PNG_BYTES,
                "supplement.txt": b"not a figure" * 20,
                "spreadsheet.xlsx": b"PK\x03\x04" + (b"\x00" * 200),
            }
        )
        figs, _ = _extract_tar_to_dir(tar_bytes, tmp_path)
        assert [p.name for p in figs] == ["fig1.png"]

    def test_traversal_attempts_stay_inside_target_dir(self, tmp_path: Path) -> None:
        # Build a tar that names entries with ``../`` prefixes.  Even if the
        # implementation strips to basename, the resulting file MUST be inside
        # the target dir — never the parent.
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            data = b"x" * 200
            info = tarfile.TarInfo(name="../escape.png")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
            info2 = tarfile.TarInfo(name="real/fig1.png")
            info2.size = len(_PNG_BYTES)
            tar.addfile(info2, io.BytesIO(_PNG_BYTES))
        figs, _ = _extract_tar_to_dir(buf.getvalue(), tmp_path)
        # Whatever survives, it MUST live under tmp_path; the parent dir
        # must not have been touched.
        for f in figs:
            assert tmp_path in f.parents
        assert not (tmp_path.parent / "escape.png").exists()
        # The legitimate file is still there.
        assert any(p.name == "fig1.png" for p in figs)


# ---------------------------------------------------------------------------
# acquire_figures — full PMC OA tar path
# ---------------------------------------------------------------------------


class TestAcquireFiguresPmcPath:
    def test_full_pipeline_returns_figures_with_captions(
        self, tmp_path: Path
    ) -> None:
        tar_bytes = _make_tar_gz(
            figures={
                "fig1.png": _PNG_BYTES,
                "figS2.jpg": b"jpegdata" + (b"\xff" * 200),
            },
        )
        session = _FakeSession(
            [
                # idconv: DOI -> PMCID
                (
                    ("pmc", "idconv"),
                    _FakeResponse(
                        status_code=200,
                        _json={"records": [{"pmcid": "PMC1234567"}]},
                    ),
                ),
                # OA service: PMCID -> tar URL
                (
                    ("pmc", "oa.fcgi"),
                    _FakeResponse(
                        status_code=200,
                        content=_make_oa_xml("https://oa.test/pkg.tar.gz"),
                    ),
                ),
                # Tar download
                (
                    ("pmc", "oa.test"),
                    _FakeResponse(status_code=200, content=tar_bytes),
                ),
            ]
        )

        result = acquire_figures(
            "10.1/test",
            cache_dir=tmp_path,
            apis={},
            _session=session,  # type: ignore[arg-type]
        )

        assert result.source == "pmc-tar"
        assert result.error is None
        assert len(result.figures) == 2

        # Figures cached under canonical layout.
        paper_dir = figure_cache_dir("10.1/test", tmp_path)
        names = sorted(f.file_path.name for f in result.figures)
        assert names == ["fig1.png", "figS2.jpg"]
        for f in result.figures:
            assert f.file_path.parent == paper_dir
            assert f.file_path.exists()

        # NXML caption + label + panels found.
        by_id = {f.figure_id: f for f in result.figures}
        assert by_id["fig1"].label == "Figure 1"
        assert "Overview of the system" in by_id["fig1"].caption
        assert by_id["fig1"].panels == ["A", "B", "C"]
        assert by_id["fig-S2"].label == "Figure S2"

        # Manifest persisted.
        manifest = paper_dir / ".figures.json"
        assert manifest.exists()
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["source"] == "pmc-tar"
        assert len(data["figures"]) == 2

    def test_cache_hit_short_circuits(self, tmp_path: Path) -> None:
        # Pre-populate the cache directory + manifest pointing at a file.
        paper_dir = figure_cache_dir("10.1/test", tmp_path)
        paper_dir.mkdir(parents=True)
        cached_path = paper_dir / "fig1.png"
        cached_path.write_bytes(_PNG_BYTES)
        manifest = {
            "doi": "10.1/test",
            "source": "pmc-tar",
            "error": None,
            "figures": [
                {
                    "figure_id": "fig1",
                    "file_path": str(cached_path),
                    "caption": "cached caption",
                    "label": "Figure 1",
                    "panels": ["A"],
                }
            ],
        }
        (paper_dir / ".figures.json").write_text(json.dumps(manifest), encoding="utf-8")

        # Empty session — any HTTP call would 404.
        session = _FakeSession([])
        result = acquire_figures(
            "10.1/test",
            cache_dir=tmp_path,
            apis={},
            _session=session,  # type: ignore[arg-type]
        )
        assert result.source == "cache"
        assert len(result.figures) == 1
        assert result.figures[0].caption == "cached caption"
        assert session.calls == []  # never touched the network


# ---------------------------------------------------------------------------
# acquire_figures — unavailable path
# ---------------------------------------------------------------------------


class TestAcquireFiguresUnavailable:
    def test_no_pmcid_and_no_springer_returns_unavailable(
        self, tmp_path: Path
    ) -> None:
        session = _FakeSession(
            [
                # idconv: no PMCID
                (
                    ("pmc", "idconv"),
                    _FakeResponse(status_code=200, _json={"records": [{}]}),
                ),
                # No springer key configured -> tier skipped, no entry needed.
            ]
        )
        result = acquire_figures(
            "10.9999/missing",
            cache_dir=tmp_path,
            apis={},  # no springer key
            _session=session,  # type: ignore[arg-type]
        )
        assert result.source == "unavailable"
        assert "no API source" in (result.error or "")
        assert result.figures == []

        # Manifest still saved so a future run knows we tried.
        paper_dir = figure_cache_dir("10.9999/missing", tmp_path)
        assert (paper_dir / ".figures.json").exists()

    def test_paper_outside_oa_subset_returns_unavailable(
        self, tmp_path: Path
    ) -> None:
        session = _FakeSession(
            [
                (
                    ("pmc", "idconv"),
                    _FakeResponse(
                        status_code=200,
                        _json={"records": [{"pmcid": "PMC1234567"}]},
                    ),
                ),
                # OA service responds with an error (not in OA subset).
                (
                    ("pmc", "oa.fcgi"),
                    _FakeResponse(status_code=200, content=_make_oa_error_xml()),
                ),
            ]
        )
        result = acquire_figures(
            "10.1/closed",
            cache_dir=tmp_path,
            apis={},
            _session=session,  # type: ignore[arg-type]
        )
        assert result.source == "unavailable"
        assert result.figures == []

    def test_empty_doi_returns_unavailable_without_network(self, tmp_path: Path) -> None:
        session = _FakeSession([])
        result = acquire_figures(
            "",
            cache_dir=tmp_path,
            apis={},
            _session=session,  # type: ignore[arg-type]
        )
        assert result.source == "unavailable"
        assert result.error == "empty doi"
        assert session.calls == []


# ---------------------------------------------------------------------------
# Elsevier ScienceDirect path
# ---------------------------------------------------------------------------


_SAMPLE_ELS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<full-text-retrieval-response
  xmlns="http://www.elsevier.com/xml/svapi/article/dtd"
  xmlns:ce="http://www.elsevier.com/xml/common/dtd"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  xmlns:xocs="http://www.elsevier.com/xml/xocs/dtd"
  xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/"
  xmlns:dc="http://purl.org/dc/elements/1.1/">
  <coredata>
    <prism:pii>S0092867418309048</prism:pii>
  </coredata>
  <originalText>
    <xocs:doc>
      <xocs:meta>
        <xocs:pii-unformatted>S0092867418309048</xocs:pii-unformatted>
      </xocs:meta>
      <xocs:serial-item>
        <ce:figure id="fig1">
          <ce:label>Figure 1</ce:label>
          <ce:caption>
            <ce:simple-para>Overview showing (A) panel A, (B) panel B, and (C) feedback.</ce:simple-para>
          </ce:caption>
          <ce:link locator="gr1" xlink:href="pii:S0092867418309048/gr1"/>
        </ce:figure>
        <ce:figure id="fig2">
          <ce:label>Figure 2</ce:label>
          <ce:caption>
            <ce:simple-para>Second figure caption text.</ce:simple-para>
          </ce:caption>
          <ce:link locator="gr2" xlink:href="pii:S0092867418309048/gr2"/>
        </ce:figure>
      </xocs:serial-item>
    </xocs:doc>
  </originalText>
</full-text-retrieval-response>
"""


class TestParseElsevierFigures:
    def test_extracts_pii_label_caption_locator(self) -> None:
        pii, figs = _parse_elsevier_figures(_SAMPLE_ELS_XML)
        assert pii == "S0092867418309048"
        assert len(figs) == 2
        assert figs[0]["id"] == "fig1"
        assert figs[0]["label"] == "Figure 1"
        assert "panel A" in figs[0]["caption"]
        assert figs[0]["locator"] == "gr1"
        assert figs[1]["locator"] == "gr2"

    def test_returns_empty_on_bad_xml(self) -> None:
        pii, figs = _parse_elsevier_figures(b"<not xml")
        assert pii == ""
        assert figs == []


_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    + (b"\x00" * 200)
    + b"\xff\xd9"
)


class TestAcquireFiguresElsevier:
    def test_elsevier_falls_back_when_pmc_misses(self, tmp_path: Path) -> None:
        session = _FakeSession(
            [
                # PMC idconv: no PMCID (skip PMC tier)
                (
                    ("pmc", "idconv"),
                    _FakeResponse(status_code=200, _json={"records": [{}]}),
                ),
                # Elsevier article retrieval returns the XML.
                (
                    ("elsevier", "/content/article/doi/"),
                    _FakeResponse(
                        status_code=200,
                        content=_SAMPLE_ELS_XML,
                        headers={"Content-Type": "text/xml;charset=UTF-8"},
                    ),
                ),
                # First figure: high-res object download succeeds.
                (
                    ("elsevier", "1-s2.0-S0092867418309048-gr1_lrg.jpg"),
                    _FakeResponse(
                        status_code=200,
                        content=_JPEG_BYTES,
                        headers={"Content-Type": "image/jpeg;charset=UTF-8"},
                    ),
                ),
                # Second figure: high-res 404, fall back to standard.
                (
                    ("elsevier", "1-s2.0-S0092867418309048-gr2_lrg.jpg"),
                    _FakeResponse(status_code=404, headers={}),
                ),
                (
                    ("elsevier", "1-s2.0-S0092867418309048-gr2.jpg"),
                    _FakeResponse(
                        status_code=200,
                        content=_JPEG_BYTES,
                        headers={"Content-Type": "image/jpeg"},
                    ),
                ),
            ]
        )
        result = acquire_figures(
            "10.1016/j.cell.2018.07.010",
            cache_dir=tmp_path,
            apis={"elsevier_key": "fake-key"},
            _session=session,  # type: ignore[arg-type]
        )
        assert result.source == "elsevier-api"
        assert result.error is None
        assert len(result.figures) == 2

        by_id = {f.figure_id: f for f in result.figures}
        # Caption + label preserved
        assert by_id["fig1"].label == "Figure 1"
        assert "panel A" in by_id["fig1"].caption
        assert by_id["fig1"].panels == ["A", "B", "C"]
        # File saved on disk under canonical layout
        paper_dir = figure_cache_dir("10.1016/j.cell.2018.07.010", tmp_path)
        for f in result.figures:
            assert f.file_path.parent == paper_dir
            assert f.file_path.exists()
            assert f.file_path.suffix == ".jpg"

        # Manifest persisted with elsevier-api source.
        manifest = paper_dir / ".figures.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["source"] == "elsevier-api"

    def test_elsevier_skipped_without_key(self, tmp_path: Path) -> None:
        # PMC misses, Elsevier never queried because no key, Springer never has key either.
        session = _FakeSession(
            [
                (
                    ("pmc", "idconv"),
                    _FakeResponse(status_code=200, _json={"records": [{}]}),
                ),
            ]
        )
        result = acquire_figures(
            "10.1016/j.cell.test",
            cache_dir=tmp_path,
            apis={},  # no elsevier_key
            _session=session,  # type: ignore[arg-type]
        )
        assert result.source == "unavailable"
        # We should not have made any elsevier-tier calls
        assert not any(s == "elsevier" for s, _u, _p in session.calls)


# ---------------------------------------------------------------------------
# acquire_figures — Springer fallback path
# ---------------------------------------------------------------------------


class TestAcquireFiguresSpringer:
    def test_springer_falls_back_when_pmc_misses(self, tmp_path: Path) -> None:
        session = _FakeSession(
            [
                # PMC idconv: no PMCID (skip PMC tier)
                (
                    ("pmc", "idconv"),
                    _FakeResponse(status_code=200, _json={"records": [{}]}),
                ),
                # Springer OA returns a record WITH a figures array.
                (
                    ("springer", "openaccess"),
                    _FakeResponse(
                        status_code=200,
                        _json={
                            "records": [
                                {
                                    "figures": [
                                        {
                                            "id": "fig1",
                                            "url": "https://springer.test/figs/fig1.png",
                                            "caption": "Springer fig (A) panel",
                                            "label": "Figure 1",
                                        }
                                    ]
                                }
                            ]
                        },
                    ),
                ),
                # The actual figure download.
                (
                    ("springer", "springer.test/figs/fig1.png"),
                    _FakeResponse(
                        status_code=200,
                        content=_PNG_BYTES,
                        headers={"Content-Type": "image/png"},
                    ),
                ),
            ]
        )
        result = acquire_figures(
            "10.1007/springer.test",
            cache_dir=tmp_path,
            apis={"springer_open_access_api_key": "k"},
            _session=session,  # type: ignore[arg-type]
        )
        assert result.source == "springer-api"
        assert len(result.figures) == 1
        fig = result.figures[0]
        assert fig.figure_id == "fig1"
        assert fig.label == "Figure 1"
        assert fig.panels == ["A"]
        assert fig.file_path.exists()
        assert fig.file_path.suffix == ".png"


# ---------------------------------------------------------------------------
# Gap 3 — figure-cache manifest sample (evening-5 2026-04-30)
#
# The .figures.json sidecar must carry the canonical "path" field, real
# size_bytes, the source tier, fetched_at timestamp, and an errors list.
# These tests pin the shape so the system-state §14 sample stays accurate.
# ---------------------------------------------------------------------------


class TestFigureManifestShape:
    def test_manifest_has_canonical_fields(self, tmp_path: Path) -> None:
        """A successful PMC OA acquisition writes a manifest with the
        new gap-3 shape: doi/source/fetched_at/figures[{path, size_bytes,
        caption, panels, page}]/errors.
        """
        tar_bytes = _make_tar_gz(figures={"fig1.png": _PNG_BYTES})
        session = _FakeSession(
            [
                (
                    ("pmc", "idconv"),
                    _FakeResponse(
                        status_code=200,
                        _json={"records": [{"pmcid": "PMC1"}]},
                    ),
                ),
                (
                    ("pmc", "oa.fcgi"),
                    _FakeResponse(
                        status_code=200,
                        content=_make_oa_xml("https://oa.test/p.tar.gz"),
                    ),
                ),
                (
                    ("pmc", "oa.test"),
                    _FakeResponse(status_code=200, content=tar_bytes),
                ),
            ]
        )
        acquire_figures(
            "10.5/manifest",
            cache_dir=tmp_path,
            apis={},
            _session=session,  # type: ignore[arg-type]
        )
        paper_dir = figure_cache_dir("10.5/manifest", tmp_path)
        data = json.loads((paper_dir / ".figures.json").read_text(encoding="utf-8"))

        # Top-level shape
        assert data["doi"] == "10.5/manifest"
        assert data["source"] == "pmc-tar"
        assert "fetched_at" in data
        assert data["fetched_at"].endswith("Z")
        assert data["errors"] == []  # success → empty list

        # Per-figure shape: every required gap-3 key is present.
        assert len(data["figures"]) == 1
        fig0 = data["figures"][0]
        for key in ("path", "size_bytes", "caption", "panels", "page"):
            assert key in fig0, f"manifest figure missing {key!r}"
        # path is the canonical field
        assert fig0["path"].endswith("fig1.png")
        # size_bytes is the actual file size, not a placeholder
        assert fig0["size_bytes"] == len(_PNG_BYTES)
        # page is reserved (None today)
        assert fig0["page"] is None
        # Panels parsed from caption
        assert "A" in fig0["panels"]

    def test_manifest_errors_populated_on_unavailable(self, tmp_path: Path) -> None:
        """Unavailable papers still get a manifest, and the ``errors``
        list carries the failure reason (gap-3 spec)."""
        session = _FakeSession(
            [
                (
                    ("pmc", "idconv"),
                    _FakeResponse(status_code=200, _json={"records": [{}]}),
                ),
            ]
        )
        acquire_figures(
            "10.9/missing",
            cache_dir=tmp_path,
            apis={},
            _session=session,  # type: ignore[arg-type]
        )
        paper_dir = figure_cache_dir("10.9/missing", tmp_path)
        data = json.loads((paper_dir / ".figures.json").read_text(encoding="utf-8"))
        assert data["source"] == "unavailable"
        assert data["figures"] == []
        # errors is a list (gap-3) and carries the unavailable reason
        assert isinstance(data["errors"], list)
        assert any("no API source" in e for e in data["errors"])

    def test_legacy_manifest_still_loads(self, tmp_path: Path) -> None:
        """Older manifests written before evening-5 used ``file_path``
        (no ``path``); the loader must still resolve them so existing
        caches don't go stale."""
        paper_dir = figure_cache_dir("10.1/legacy", tmp_path)
        paper_dir.mkdir(parents=True)
        cached = paper_dir / "fig1.png"
        cached.write_bytes(_PNG_BYTES)
        legacy_manifest = {
            "doi": "10.1/legacy",
            "source": "pmc-tar",
            "error": None,
            "figures": [
                {
                    "figure_id": "fig1",
                    "file_path": str(cached),  # legacy key only
                    "caption": "legacy",
                    "label": "Figure 1",
                    "panels": ["A"],
                }
            ],
        }
        (paper_dir / ".figures.json").write_text(
            json.dumps(legacy_manifest), encoding="utf-8"
        )
        session = _FakeSession([])
        result = acquire_figures(
            "10.1/legacy",
            cache_dir=tmp_path,
            apis={},
            _session=session,  # type: ignore[arg-type]
        )
        assert result.source == "cache"
        assert len(result.figures) == 1
        assert result.figures[0].file_path == cached
