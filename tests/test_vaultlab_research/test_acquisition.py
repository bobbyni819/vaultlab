"""Unit tests for vaultlab.research.acquisition.

All HTTP traffic is faked via a ``_PoliteSession`` stub.  The waterfall is
exercised end-to-end with deterministic responses so we can verify:

* Cache hits short-circuit the entire waterfall.
* Tier ordering: Unpaywall -> PMC -> bioRxiv -> Springer -> Elsevier.
* HTTP 404 / 401 / 403 from one tier moves to the next instead of failing
  the whole acquisition.
* Licence captured per tier.
* ``skip_paywalled`` halts at the OA boundary.
* PDF magic-number / Content-Type guard rejects HTML landing pages.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from vaultlab.research import acquisition as acq
from vaultlab.research.acquisition import (
    AcquisitionResult,
    acquire_pdf,
    acquire_pdfs_for_corpus,
    cache_path_for,
    doi_slug,
)
from vaultlab.research.corpus import Corpus
from vaultlab.research.paper import Paper

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_PDF_BYTES = b"%PDF-1.4\n" + (b"x" * 2000)
_HTML_BYTES = b"<html><body>Login required</body></html>" + (b" " * 2000)


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
    """In-memory stand-in for :class:`acquisition._PoliteSession`.

    ``script`` maps ``(source, url_substring)`` -> ``_FakeResponse``.  The
    first matching entry is consumed; missing entries return a 404.
    """

    def __init__(self, script: list[tuple[tuple[str, str], _FakeResponse]]):
        # list-of-pairs to preserve order and allow a single source/url
        # substring to be queried multiple times.
        self._script = list(script)
        self.calls: list[tuple[str, str]] = []

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
        self.calls.append((source, url))
        for i, ((s, frag), resp) in enumerate(self._script):
            if s == source and frag in url:
                self._script.pop(i)
                if resp.headers is None:
                    resp.headers = {}
                return resp
        return _FakeResponse(status_code=404, headers={})


def _seed(doi: str, year: int = 2020) -> Paper:
    return Paper(title=doi, doi=doi, year=year, source_api="seed")


def _make_corpus(dois: list[str]) -> Corpus:
    seeds = [_seed(d) for d in dois]
    papers = {d.lower(): p for d, p in zip(dois, seeds, strict=False)}
    return Corpus(topic="test", seeds=seeds, papers=papers, references={})


# ---------------------------------------------------------------------------
# doi_slug + cache_path_for
# ---------------------------------------------------------------------------


class TestDoiSlug:
    def test_slashes_and_dots(self):
        # Bobby 2026-04-30 slug-unification: doi_slug now delegates to
        # vaultlab.kb.paths.slugify_doi (dot format wins) so summary
        # frontmatter source_pdf paths actually resolve.
        assert doi_slug("10.1126/science.1225829") == "10.1126_science.1225829"

    def test_lowercased(self):
        assert doi_slug("10.1038/S41586-024-07159-5") == "10.1038_s41586-024-07159-5"

    def test_strips_whitespace(self):
        assert doi_slug("  10.1/a  ") == "10.1_a"

    def test_matches_kb_paths_slugify(self):
        """Single source of truth — round-trip with vaultlab.kb.paths."""
        from vaultlab.kb.paths import slugify_doi

        for d in [
            "10.1126/science.1225829",
            "10.1038/s41586-023-05915-x",
            "10.1101/2024.01.02.123456",
        ]:
            assert doi_slug(d) == slugify_doi(d)

    def test_cache_path_uses_slug(self, tmp_path: Path):
        p = cache_path_for("10.1/a", tmp_path)
        assert p == tmp_path / "10.1_a.pdf"

    def test_cache_path_back_compat_resolves_legacy_dash_format(
        self, tmp_path: Path
    ):
        """399 PDFs already on disk under the dash-format slug must still resolve.

        Pre-2026-04-30 ``doi_slug`` produced ``10-1126_science-1225829``;
        existing PDFs + extracted figures live at that path. The
        :func:`cache_path_for` resolver now tries the canonical dot-format
        first, then falls back to the dash-format if the legacy file
        already exists.
        """
        from vaultlab.research.acquisition import _legacy_doi_slug

        doi = "10.1126/science.1225829"
        legacy = tmp_path / f"{_legacy_doi_slug(doi)}.pdf"
        legacy.write_bytes(_PDF_BYTES)

        resolved = cache_path_for(doi, tmp_path)
        assert resolved == legacy
        assert resolved.exists()

    def test_cache_path_prefers_dot_format_when_both_exist(
        self, tmp_path: Path
    ):
        """If both formats live on disk the canonical dot-format wins."""
        from vaultlab.research.acquisition import _legacy_doi_slug

        doi = "10.1/a"
        canonical = tmp_path / "10.1_a.pdf"
        legacy = tmp_path / f"{_legacy_doi_slug(doi)}.pdf"
        canonical.write_bytes(_PDF_BYTES)
        legacy.write_bytes(_PDF_BYTES)

        resolved = cache_path_for(doi, tmp_path)
        assert resolved == canonical


# ---------------------------------------------------------------------------
# Cache short-circuit
# ---------------------------------------------------------------------------


class TestCacheShortCircuit:
    def test_existing_pdf_returns_cache_result(self, tmp_path: Path):
        target = tmp_path / "10.1_a.pdf"
        target.write_bytes(_PDF_BYTES)

        # An empty session means any HTTP call would 404 — proving we never
        # touched the network.
        session = _FakeSession([])
        result = acquire_pdf(
            "10.1/a",
            cache_dir=tmp_path,
            apis={},
            _session=session,  # type: ignore[arg-type]
        )
        assert result.source == "cache"
        assert result.pdf_path == target
        assert session.calls == []

    def test_too_small_cache_file_is_ignored(self, tmp_path: Path):
        target = tmp_path / "10.1_a.pdf"
        target.write_bytes(b"%PDF-tiny")
        session = _FakeSession(
            [
                (
                    ("unpaywall", "10.1/a"),
                    _FakeResponse(
                        status_code=200,
                        _json={
                            "best_oa_location": {
                                "url_for_pdf": "https://oa.example/a.pdf",
                                "license": "cc-by",
                            }
                        },
                    ),
                ),
                (
                    ("unpaywall", "oa.example"),
                    _FakeResponse(
                        status_code=200,
                        content=_PDF_BYTES,
                        headers={"Content-Type": "application/pdf"},
                    ),
                ),
            ]
        )
        result = acquire_pdf(
            "10.1/a",
            cache_dir=tmp_path,
            apis={},
            _session=session,  # type: ignore[arg-type]
        )
        assert result.source == "unpaywall"


# ---------------------------------------------------------------------------
# Tier 1: Unpaywall
# ---------------------------------------------------------------------------


class TestUnpaywallTier:
    def test_success_short_circuits_remaining_tiers(self, tmp_path: Path):
        session = _FakeSession(
            [
                (
                    ("unpaywall", "10.1/a"),
                    _FakeResponse(
                        status_code=200,
                        _json={
                            "best_oa_location": {
                                "url_for_pdf": "https://oa.example/a.pdf",
                                "license": "cc-by",
                            },
                            "oa_locations": [],
                        },
                    ),
                ),
                (
                    ("unpaywall", "oa.example"),
                    _FakeResponse(
                        status_code=200,
                        content=_PDF_BYTES,
                        headers={"Content-Type": "application/pdf"},
                    ),
                ),
            ]
        )
        result = acquire_pdf(
            "10.1/a",
            cache_dir=tmp_path,
            apis={"springer_open_access_api_key": "k", "elsevier_key": "e"},
            _session=session,  # type: ignore[arg-type]
        )
        assert result.source == "unpaywall"
        assert result.license == "cc-by"
        assert result.pdf_path is not None
        assert result.pdf_path.read_bytes().startswith(b"%PDF-")
        # No PMC / Springer / Elsevier calls were made.
        sources_touched = {s for s, _ in session.calls}
        assert sources_touched == {"unpaywall"}

    def test_404_falls_through_to_pmc(self, tmp_path: Path):
        session = _FakeSession(
            [
                (("unpaywall", "10.1/a"), _FakeResponse(status_code=404)),
                (
                    ("pmc", "idconv"),
                    _FakeResponse(
                        status_code=200,
                        _json={"records": [{"pmcid": "PMC12345"}]},
                    ),
                ),
                (
                    ("pmc", "PMC12345"),
                    _FakeResponse(
                        status_code=200,
                        content=_PDF_BYTES,
                        headers={"Content-Type": "application/pdf"},
                    ),
                ),
            ]
        )
        result = acquire_pdf(
            "10.1/a",
            cache_dir=tmp_path,
            apis={},
            _session=session,  # type: ignore[arg-type]
        )
        assert result.source == "pmc"
        assert result.license == "pmc-oa"

    def test_unpaywall_pmc_url_in_url_field_falls_back(self, tmp_path: Path):
        """When Unpaywall has no url_for_pdf but has a PMC ``url``, use it."""
        session = _FakeSession(
            [
                (
                    ("unpaywall", "10.1/a"),
                    _FakeResponse(
                        status_code=200,
                        _json={
                            "best_oa_location": {
                                "url_for_pdf": None,
                                "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1234",
                                "license": None,
                            }
                        },
                    ),
                ),
                # The downloader requests EuropePMC's render URL.
                (
                    ("unpaywall", "europepmc.org/articles/PMC1234"),
                    _FakeResponse(
                        status_code=200,
                        content=_PDF_BYTES,
                        headers={"Content-Type": "application/pdf"},
                    ),
                ),
            ]
        )
        result = acquire_pdf(
            "10.1/a",
            cache_dir=tmp_path,
            apis={},
            _session=session,  # type: ignore[arg-type]
        )
        assert result.source == "unpaywall"
        assert result.license == "pmc-oa"

    def test_unpaywall_rewrites_ncbi_pmc_pdf_url(self, tmp_path: Path):
        """An ``url_for_pdf`` on pmc.ncbi.nlm.nih.gov gets rewritten to EuropePMC."""
        session = _FakeSession(
            [
                (
                    ("unpaywall", "10.1/a"),
                    _FakeResponse(
                        status_code=200,
                        _json={
                            "best_oa_location": {
                                "url_for_pdf": (
                                    "https://pmc.ncbi.nlm.nih.gov/articles/"
                                    "PMC9999/pdf/main.pdf"
                                ),
                                "license": "cc-by",
                            }
                        },
                    ),
                ),
                (
                    ("unpaywall", "europepmc.org/articles/PMC9999"),
                    _FakeResponse(
                        status_code=200,
                        content=_PDF_BYTES,
                        headers={"Content-Type": "application/pdf"},
                    ),
                ),
            ]
        )
        result = acquire_pdf(
            "10.1/a",
            cache_dir=tmp_path,
            apis={},
            _session=session,  # type: ignore[arg-type]
        )
        assert result.source == "unpaywall"
        assert result.license == "cc-by"

    def test_html_landing_page_rejected(self, tmp_path: Path):
        """If Unpaywall returns a URL that serves HTML, fall through."""
        session = _FakeSession(
            [
                (
                    ("unpaywall", "10.1/a"),
                    _FakeResponse(
                        status_code=200,
                        _json={
                            "best_oa_location": {
                                "url_for_pdf": "https://landing.example/a",
                                "license": "cc-by",
                            }
                        },
                    ),
                ),
                (
                    ("unpaywall", "landing.example"),
                    _FakeResponse(
                        status_code=200,
                        content=_HTML_BYTES,
                        headers={"Content-Type": "text/html"},
                    ),
                ),
                # PMC fallback succeeds
                (
                    ("pmc", "idconv"),
                    _FakeResponse(
                        status_code=200,
                        _json={"records": [{"pmcid": "PMC9"}]},
                    ),
                ),
                (
                    ("pmc", "PMC9"),
                    _FakeResponse(
                        status_code=200,
                        content=_PDF_BYTES,
                        headers={"Content-Type": "application/pdf"},
                    ),
                ),
            ]
        )
        result = acquire_pdf(
            "10.1/a",
            cache_dir=tmp_path,
            apis={},
            _session=session,  # type: ignore[arg-type]
        )
        assert result.source == "pmc"


# ---------------------------------------------------------------------------
# Tier 3: bioRxiv
# ---------------------------------------------------------------------------


class TestBiorxivTier:
    def test_biorxiv_doi_prefix_picks_biorxiv(self, tmp_path: Path):
        doi = "10.1101/2024.01.15.575555"
        session = _FakeSession(
            [
                (("unpaywall", doi), _FakeResponse(status_code=404)),
                (("pmc", "idconv"), _FakeResponse(status_code=404)),
                (
                    ("biorxiv", "biorxiv.org"),
                    _FakeResponse(
                        status_code=200,
                        content=_PDF_BYTES,
                        headers={"Content-Type": "application/pdf"},
                    ),
                ),
            ]
        )
        result = acquire_pdf(
            doi,
            cache_dir=tmp_path,
            apis={},
            _session=session,  # type: ignore[arg-type]
        )
        assert result.source == "biorxiv"
        assert result.license == "cc-by"

    def test_non_biorxiv_doi_skips_tier(self, tmp_path: Path):
        """A non-10.1101 DOI should not even attempt the bioRxiv URL."""
        session = _FakeSession(
            [
                (("unpaywall", "10.1/a"), _FakeResponse(status_code=404)),
                (("pmc", "idconv"), _FakeResponse(status_code=404)),
                (
                    ("springer", "springer"),
                    _FakeResponse(status_code=200, _json={"records": []}),
                ),
                (
                    ("springer", "link.springer"),
                    _FakeResponse(
                        status_code=200,
                        content=_PDF_BYTES,
                        headers={"Content-Type": "application/pdf"},
                    ),
                ),
            ]
        )
        result = acquire_pdf(
            "10.1/a",
            cache_dir=tmp_path,
            apis={"springer_open_access_api_key": "k"},
            _session=session,  # type: ignore[arg-type]
        )
        # Did not attempt bioRxiv at all.
        biorxiv_calls = [c for c in session.calls if c[0] == "biorxiv"]
        assert biorxiv_calls == []
        assert result.source == "springer"


# ---------------------------------------------------------------------------
# skip_paywalled
# ---------------------------------------------------------------------------


class TestSkipPaywalled:
    def test_skips_springer_and_elsevier(self, tmp_path: Path):
        session = _FakeSession(
            [
                (("unpaywall", "10.1/a"), _FakeResponse(status_code=404)),
                (("pmc", "idconv"), _FakeResponse(status_code=404)),
            ]
        )
        result = acquire_pdf(
            "10.1/a",
            cache_dir=tmp_path,
            apis={"springer_open_access_api_key": "k", "elsevier_key": "e"},
            skip_paywalled=True,
            _session=session,  # type: ignore[arg-type]
        )
        assert result.source == "failed"
        # Confirm we never touched paywalled tiers.
        sources_touched = {s for s, _ in session.calls}
        assert "springer" not in sources_touched
        assert "elsevier" not in sources_touched


# ---------------------------------------------------------------------------
# Tier 5: Elsevier
# ---------------------------------------------------------------------------


class TestElsevierTier:
    def test_403_falls_through_to_failed(self, tmp_path: Path):
        session = _FakeSession(
            [
                (("unpaywall", "10.1/a"), _FakeResponse(status_code=404)),
                (("pmc", "idconv"), _FakeResponse(status_code=404)),
                (
                    ("springer", "springer"),
                    _FakeResponse(status_code=200, _json={"records": []}),
                ),
                (
                    ("springer", "link.springer"),
                    _FakeResponse(status_code=404),
                ),
                (
                    ("elsevier", "elsevier"),
                    _FakeResponse(status_code=403),
                ),
            ]
        )
        result = acquire_pdf(
            "10.1/a",
            cache_dir=tmp_path,
            apis={"springer_open_access_api_key": "k", "elsevier_key": "e"},
            _session=session,  # type: ignore[arg-type]
        )
        assert result.source == "failed"
        assert result.error and "no source had pdf" in result.error

    def test_no_api_key_skips_elsevier(self, tmp_path: Path):
        """Without an Elsevier key the tier should be silently skipped."""
        session = _FakeSession(
            [
                (("unpaywall", "10.1/a"), _FakeResponse(status_code=404)),
                (("pmc", "idconv"), _FakeResponse(status_code=404)),
                (
                    ("springer", "springer"),
                    _FakeResponse(status_code=200, _json={"records": []}),
                ),
                (
                    ("springer", "link.springer"),
                    _FakeResponse(status_code=404),
                ),
            ]
        )
        result = acquire_pdf(
            "10.1/a",
            cache_dir=tmp_path,
            apis={},
            _session=session,  # type: ignore[arg-type]
        )
        assert result.source == "failed"
        elsevier_calls = [c for c in session.calls if c[0] == "elsevier"]
        assert elsevier_calls == []


# ---------------------------------------------------------------------------
# License capture
# ---------------------------------------------------------------------------


class TestLicenseCapture:
    @pytest.mark.parametrize(
        "license_input,expected",
        [
            ("cc-by", "cc-by"),
            ("CC-BY-NC", "cc-by-nc"),
            ("", "unknown"),
            (None, "unknown"),
        ],
    )
    def test_unpaywall_license(
        self, license_input: str | None, expected: str, tmp_path: Path
    ):
        session = _FakeSession(
            [
                (
                    ("unpaywall", "10.1/a"),
                    _FakeResponse(
                        status_code=200,
                        _json={
                            "best_oa_location": {
                                "url_for_pdf": "https://oa.example/a.pdf",
                                "license": license_input,
                            }
                        },
                    ),
                ),
                (
                    ("unpaywall", "oa.example"),
                    _FakeResponse(
                        status_code=200,
                        content=_PDF_BYTES,
                        headers={"Content-Type": "application/pdf"},
                    ),
                ),
            ]
        )
        result = acquire_pdf(
            "10.1/a",
            cache_dir=tmp_path,
            apis={},
            _session=session,  # type: ignore[arg-type]
        )
        assert result.license == expected


# ---------------------------------------------------------------------------
# Empty / weird DOI
# ---------------------------------------------------------------------------


class TestBadInput:
    def test_empty_doi_returns_failed(self, tmp_path: Path):
        result = acquire_pdf(
            "", cache_dir=tmp_path, apis={}
        )
        assert result.source == "failed"
        assert result.error == "empty doi"


# ---------------------------------------------------------------------------
# Batch helper
# ---------------------------------------------------------------------------


class TestBatchAcquireForCorpus:
    def test_runs_for_each_paper_with_doi(self, monkeypatch, tmp_path: Path):
        called: list[str] = []

        def fake_acquire(
            doi: str, *, cache_dir, apis, skip_paywalled, timeout
        ) -> AcquisitionResult:
            called.append(doi)
            return AcquisitionResult(
                doi=doi,
                pdf_path=tmp_path / f"{doi}.pdf",
                source="cache",
                license="cc-by",
            )

        monkeypatch.setattr(acq, "acquire_pdf", fake_acquire)

        corpus = _make_corpus(["10.1/a", "10.1/b", "10.1/c"])
        results = acquire_pdfs_for_corpus(
            corpus,
            cache_dir=tmp_path,
            parallel=1,
            apis={},
        )
        assert set(results.keys()) == {"10.1/a", "10.1/b", "10.1/c"}
        assert sorted(called) == ["10.1/a", "10.1/b", "10.1/c"]

    def test_progress_callback(self, monkeypatch, tmp_path: Path):
        def fake_acquire(
            doi, *, cache_dir, apis, skip_paywalled, timeout
        ) -> AcquisitionResult:
            return AcquisitionResult(
                doi=doi, pdf_path=None, source="failed", license=None, error="x"
            )

        monkeypatch.setattr(acq, "acquire_pdf", fake_acquire)

        corpus = _make_corpus(["10.1/a", "10.1/b"])
        events: list[tuple[str, int, int]] = []
        acquire_pdfs_for_corpus(
            corpus,
            cache_dir=tmp_path,
            parallel=1,
            progress=lambda d, done, total: events.append((d, done, total)),
        )
        assert [e[1:] for e in events] == [(1, 2), (2, 2)]

    def test_aggressive_retry_reattempts_failed_dois_with_paywalled(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        """``aggressive_retry=True`` re-runs failed DOIs with skip_paywalled=False."""
        calls: list[tuple[str, bool]] = []

        def fake_acquire(
            doi, *, cache_dir, apis, skip_paywalled, timeout
        ) -> AcquisitionResult:
            calls.append((doi, skip_paywalled))
            # First pass (skip_paywalled=True): a fails, b succeeds.
            # Second pass (skip_paywalled=False) for a: succeeds.
            if doi == "10.1/a" and skip_paywalled:
                return AcquisitionResult(
                    doi=doi, pdf_path=None, source="failed",
                    license=None, error="paywalled",
                )
            return AcquisitionResult(
                doi=doi,
                pdf_path=tmp_path / f"{doi}.pdf",
                source="springer" if doi == "10.1/a" else "cache",
                license="subscription" if doi == "10.1/a" else "cc-by",
            )

        monkeypatch.setattr(acq, "acquire_pdf", fake_acquire)
        corpus = _make_corpus(["10.1/a", "10.1/b"])
        results = acquire_pdfs_for_corpus(
            corpus,
            cache_dir=tmp_path,
            parallel=1,
            apis={},
            skip_paywalled=True,
            aggressive_retry=True,
        )
        # 10.1/a was first tried with skip_paywalled=True (failed), then
        # retried with skip_paywalled=False (succeeded via Springer).
        a_calls = [sp for d, sp in calls if d == "10.1/a"]
        assert a_calls == [True, False], f"unexpected call order: {calls}"
        # Final result for 10.1/a is the retry's success.
        assert results["10.1/a"].source == "springer"
        assert results["10.1/a"].pdf_path is not None
        # 10.1/b was only called once (it succeeded the first time).
        b_calls = [sp for d, sp in calls if d == "10.1/b"]
        assert b_calls == [True]

    def test_aggressive_retry_off_skips_paywalled_retry(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        """Default (aggressive_retry=False) leaves failed DOIs alone."""
        calls: list[tuple[str, bool]] = []

        def fake_acquire(
            doi, *, cache_dir, apis, skip_paywalled, timeout
        ) -> AcquisitionResult:
            calls.append((doi, skip_paywalled))
            return AcquisitionResult(
                doi=doi, pdf_path=None, source="failed",
                license=None, error="paywalled",
            )

        monkeypatch.setattr(acq, "acquire_pdf", fake_acquire)
        corpus = _make_corpus(["10.1/a", "10.1/b"])
        results = acquire_pdfs_for_corpus(
            corpus,
            cache_dir=tmp_path,
            parallel=1,
            apis={},
            skip_paywalled=True,
            aggressive_retry=False,
        )
        # Each DOI called exactly once — no retry.
        assert len(calls) == 2
        assert all(r.source == "failed" for r in results.values())
