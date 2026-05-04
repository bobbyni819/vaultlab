"""Tests for vaultlab.slides.figure_populate — paperclip filename resolution."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vaultlab.slides.figure_populate import (
    _is_main_figure_candidate,
    _list_paperclip_figures,
    _normalize_image_to_jpg,
    _pick_main_figure,
    fetch_figure_from_paperclip,
)


# Real ls output captured from `paperclip ls /papers/PMC12688177/figures/`
PMC_LS = (
    "MOL2-19-3465-g001.gif  MOL2-19-3465-g001.jpg  MOL2-19-3465-g002.gif  "
    "MOL2-19-3465-g002.jpg  MOL2-19-3465-g003.jpg  MOL2-19-3465-g004.gif  "
    "MOL2-19-3465-g004.jpg\n"
    "  (read-only — use /.gxl/ for writable storage)\n\n"
    "💡 To save a figure: paperclip cat /papers/PMC12688177/figures/<filename> > <filename>\n"
    "[148ms]\n"
)

# Real ls output for a Springer-style paper
PMC_SPRINGER_LS = (
    "10555_2025_10304_Fig1_HTML.gif  10555_2025_10304_Fig1_HTML.jpg  "
    "10555_2025_10304_Fig2_HTML.gif  10555_2025_10304_Fig2_HTML.jpg  "
    "10555_2025_10304_Fig3_HTML.gif  10555_2025_10304_Fig3_HTML.jpg\n"
    "  (read-only — use /.gxl/ for writable storage)\n"
)

# Real ls output for bioRxiv (TIFF figures!)
BIO_LS = (
    "690313v1_fig1.tif  690313v1_fig2.tif  690313v1_fig3.tif  "
    "690313v1_fige1.tif  690313v1_fige2.tif\n"
    "  (read-only — use /.gxl/ for writable storage)\n"
)

# Real ls output for arXiv (canonical names)
ARXIV_LS = "figure_1.jpg  figure_2.jpg  figure_3.jpg  figure_4.jpg\n"

# A pathological case: paper has only equation glyphs + an icon, no real figure 1
EQU_ONLY_LS = (
    "13073_2025_1457_Article_Equa.gif  13073_2025_1457_Article_Equb.gif  "
    "13073_2025_1457_Article_IEq1.gif  thumb.png\n"
)


def _mk_subprocess_result(stdout: bytes, returncode: int = 0) -> MagicMock:
    r = MagicMock()
    r.stdout = stdout
    r.returncode = returncode
    return r


# --- _list_paperclip_figures ---

def test_list_parses_pmc_listing():
    with patch("vaultlab.slides.figure_populate.subprocess.run",
               return_value=_mk_subprocess_result(PMC_LS.encode("utf-8"))):
        files = _list_paperclip_figures("PMC12688177", paperclip_binary="/fake/paperclip")
    assert "MOL2-19-3465-g001.jpg" in files
    assert "MOL2-19-3465-g004.jpg" in files
    # metadata lines must be filtered
    assert not any("read-only" in f for f in files)
    assert not any("paperclip cat" in f for f in files)


def test_list_parses_springer_html_slugs():
    with patch("vaultlab.slides.figure_populate.subprocess.run",
               return_value=_mk_subprocess_result(PMC_SPRINGER_LS.encode("utf-8"))):
        files = _list_paperclip_figures("PMC11897387", paperclip_binary="/fake/paperclip")
    assert "10555_2025_10304_Fig1_HTML.jpg" in files


def test_list_parses_biorxiv_tiffs():
    with patch("vaultlab.slides.figure_populate.subprocess.run",
               return_value=_mk_subprocess_result(BIO_LS.encode("utf-8"))):
        files = _list_paperclip_figures("bio_e265721d74a0", paperclip_binary="/fake/paperclip")
    assert "690313v1_fig1.tif" in files


def test_list_parses_arxiv_canonical():
    with patch("vaultlab.slides.figure_populate.subprocess.run",
               return_value=_mk_subprocess_result(ARXIV_LS.encode("utf-8"))):
        files = _list_paperclip_figures("arx_2501.06039", paperclip_binary="/fake/paperclip")
    assert files == ["figure_1.jpg", "figure_2.jpg", "figure_3.jpg", "figure_4.jpg"]


def test_list_handles_cp1252_decode():
    """The cp1252 byte separator (0xb7) appears in some paperclip outputs."""
    raw = b"file_a.jpg  file_b.jpg \xb7 trailing-cp1252-byte\n"
    with patch("vaultlab.slides.figure_populate.subprocess.run",
               return_value=_mk_subprocess_result(raw)):
        files = _list_paperclip_figures("xx", paperclip_binary="/fake/paperclip")
    # Should at least pull the two images even if junk follows
    assert "file_a.jpg" in files
    assert "file_b.jpg" in files


def test_list_returns_empty_on_subprocess_failure():
    with patch("vaultlab.slides.figure_populate.subprocess.run",
               return_value=_mk_subprocess_result(b"", returncode=1)):
        files = _list_paperclip_figures("PMCxx", paperclip_binary="/fake/paperclip")
    assert files == []


# --- _pick_main_figure ---

def test_pick_pmc_publisher_slug():
    files = [
        "MOL2-19-3465-g001.gif", "MOL2-19-3465-g001.jpg",
        "MOL2-19-3465-g002.jpg", "MOL2-19-3465-g004.jpg",
    ]
    pick = _pick_main_figure(files)
    # Must pick g001 (figure 1), and JPG over GIF
    assert pick == "MOL2-19-3465-g001.jpg"


def test_pick_springer_html_slug():
    files = [
        "10555_2025_10304_Fig1_HTML.gif", "10555_2025_10304_Fig1_HTML.jpg",
        "10555_2025_10304_Fig2_HTML.jpg",
    ]
    assert _pick_main_figure(files) == "10555_2025_10304_Fig1_HTML.jpg"


def test_pick_biorxiv_tiff_when_only_option():
    files = ["690313v1_fig1.tif", "690313v1_fig2.tif"]
    pick = _pick_main_figure(files)
    assert pick == "690313v1_fig1.tif"


def test_pick_arxiv_canonical():
    files = ["figure_1.jpg", "figure_2.jpg", "figure_3.jpg"]
    assert _pick_main_figure(files) == "figure_1.jpg"


def test_pick_skips_equation_glyphs():
    """Equation glyphs and tables must not be picked as 'figure 1'."""
    files = [
        "13073_2025_1457_Article_Equa.gif",
        "13073_2025_1457_Article_IEq1.gif",
        "13073_2025_1457_Fig1_HTML.jpg",
    ]
    assert _pick_main_figure(files) == "13073_2025_1457_Fig1_HTML.jpg"


def test_pick_returns_none_when_no_figures():
    assert _pick_main_figure(["thumb.png", "logo.gif"]) is None


def test_pick_returns_none_when_only_equations():
    files = [
        "13073_2025_1457_Article_Equa.gif",
        "13073_2025_1457_Article_IEq1.gif",
    ]
    # All filtered out by _is_main_figure_candidate
    assert _pick_main_figure(files) is None


def test_pick_prefers_jpg_over_gif():
    files = ["paper_fig1.gif", "paper_fig1.jpg"]
    assert _pick_main_figure(files) == "paper_fig1.jpg"


# --- _is_main_figure_candidate ---

def test_is_main_figure_candidate_rejects_known_bad():
    bad = [
        "MOL2-19-3465-Equa.gif", "13073_2025_IEq1.gif",
        "scheme1.jpg", "logo.png", "icon.png",
        "thumb_001.jpg", "supp_fig1.jpg", "_si_001.jpg",
        "TblS1.jpg", "graphabs.jpg",
    ]
    for f in bad:
        assert not _is_main_figure_candidate(f), f


def test_is_main_figure_candidate_accepts_real_figs():
    good = [
        "fig1.jpg", "figure_1.png", "MOL2-19-3465-g001.jpg",
        "10555_2025_10304_Fig1_HTML.jpg", "690313v1_fig1.tif",
    ]
    for f in good:
        assert _is_main_figure_candidate(f), f


# --- _normalize_image_to_jpg ---

def test_normalize_passes_jpg_through(tmp_path):
    jpg_bytes = b"\xff\xd8\xff\xe0fakejpgcontent"
    out = tmp_path / "x_figure_1.jpg"
    p = _normalize_image_to_jpg(jpg_bytes, ".jpg", out)
    assert p == out
    assert p.read_bytes() == jpg_bytes


def test_normalize_passes_png_through(tmp_path):
    png_bytes = b"\x89PNG\r\n\x1a\nfakepngcontent"
    out = tmp_path / "x_figure_1.png"
    p = _normalize_image_to_jpg(png_bytes, ".png", out)
    assert p.read_bytes() == png_bytes


def test_normalize_converts_tiff_to_jpg(tmp_path):
    """Pillow round-trip: real TIFF → JPG."""
    pytest.importorskip("PIL")
    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (400, 300), color=(120, 30, 200)).save(buf, format="TIFF")
    out = tmp_path / "x_figure_1.jpg"
    p = _normalize_image_to_jpg(buf.getvalue(), ".tif", out)
    assert p is not None
    assert p.exists()
    # Must be a valid JPEG after conversion
    assert p.read_bytes()[:3] == b"\xff\xd8\xff"
    # Must be loadable
    img = Image.open(p)
    assert img.size == (400, 300)


def test_normalize_returns_none_on_garbage(tmp_path):
    """Pillow can't open arbitrary bytes — should return None gracefully."""
    out = tmp_path / "x.jpg"
    # Force the conversion path with a non-passthrough extension
    p = _normalize_image_to_jpg(b"not really an image", ".tif", out)
    assert p is None


# --- fetch_figure_from_paperclip end-to-end (mocked) ---

def test_fetch_pmc_picks_publisher_slug(tmp_path):
    """Full flow: list → pick → cat → save. Must use the publisher slug."""
    pmc_jpg = b"\xff\xd8\xff\xe0" + b"X" * 50_000  # > min_bytes

    def fake_run(cmd, **kw):
        if "ls" in cmd:
            return _mk_subprocess_result(PMC_LS.encode("utf-8"))
        if "cat" in cmd:
            # Confirm we asked for the right file (publisher slug, NOT figure_1.jpg)
            path_arg = cmd[-1]
            assert "MOL2-19-3465-g001.jpg" in path_arg, (
                f"fetcher must use publisher slug, got: {path_arg}"
            )
            return _mk_subprocess_result(pmc_jpg)
        return _mk_subprocess_result(b"")

    with patch("vaultlab.slides.figure_populate.subprocess.run", side_effect=fake_run):
        p = fetch_figure_from_paperclip(
            "PMC12688177", cache_dir=tmp_path,
            paperclip_binary="/fake/paperclip",
        )
    assert p is not None
    assert p.exists()
    assert p.stat().st_size > 50_000


def test_fetch_returns_none_when_no_figures(tmp_path):
    def fake_run(cmd, **kw):
        if "ls" in cmd:
            return _mk_subprocess_result(EQU_ONLY_LS.encode("utf-8"))
        return _mk_subprocess_result(b"")

    with patch("vaultlab.slides.figure_populate.subprocess.run", side_effect=fake_run):
        p = fetch_figure_from_paperclip(
            "PMC11963362", cache_dir=tmp_path,
            paperclip_binary="/fake/paperclip",
        )
    assert p is None


def test_fetch_uses_cache_on_second_call(tmp_path):
    """Second call must NOT hit the subprocess at all."""
    pmc_jpg = b"\xff\xd8\xff\xe0" + b"X" * 50_000

    call_count = {"n": 0}
    def fake_run(cmd, **kw):
        call_count["n"] += 1
        if "ls" in cmd:
            return _mk_subprocess_result(PMC_LS.encode("utf-8"))
        return _mk_subprocess_result(pmc_jpg)

    with patch("vaultlab.slides.figure_populate.subprocess.run", side_effect=fake_run):
        p1 = fetch_figure_from_paperclip(
            "PMC12688177", cache_dir=tmp_path, paperclip_binary="/fake/paperclip",
        )
        first_calls = call_count["n"]
        p2 = fetch_figure_from_paperclip(
            "PMC12688177", cache_dir=tmp_path, paperclip_binary="/fake/paperclip",
        )
    assert p1 == p2
    assert call_count["n"] == first_calls  # cache hit, no second subprocess


def test_fetch_converts_biorxiv_tiff(tmp_path):
    """bioRxiv stores TIFFs; must convert to JPG before insert."""
    pytest.importorskip("PIL")
    from PIL import Image
    import os
    # Use noise so post-JPG-encode size clears the 8KB threshold
    img = Image.frombytes("RGB", (600, 400), os.urandom(600 * 400 * 3))
    buf = BytesIO()
    img.save(buf, format="TIFF")
    tif_bytes = buf.getvalue()

    def fake_run(cmd, **kw):
        if "ls" in cmd:
            return _mk_subprocess_result(BIO_LS.encode("utf-8"))
        if "cat" in cmd:
            return _mk_subprocess_result(tif_bytes)
        return _mk_subprocess_result(b"")

    with patch("vaultlab.slides.figure_populate.subprocess.run", side_effect=fake_run):
        p = fetch_figure_from_paperclip(
            "bio_e265721d74a0", cache_dir=tmp_path,
            paperclip_binary="/fake/paperclip",
        )
    assert p is not None
    assert p.suffix == ".jpg"
    # Verify it's a real JPEG, not a TIFF stuffed into a .jpg file
    assert p.read_bytes()[:3] == b"\xff\xd8\xff"
