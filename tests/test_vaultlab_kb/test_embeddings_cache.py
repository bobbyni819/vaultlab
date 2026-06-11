"""Tests for the opt-in embeddings cache in vaultlab.kb.semantic_search.

The real sentence-transformers model is never loaded here: `_get_model` is
monkeypatched to a deterministic `_FakeModel`, so these tests are fast, offline,
and run under `-m "not llm"`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from vaultlab.kb import semantic_search as ss


class _FakeModel:
    """Deterministic stand-in for SentenceTransformer.

    `encode` maps each text to a fixed-dim unit vector derived from its hash, and
    records every batch it was asked to encode so tests can assert recompute/skip.
    """

    DIM = 8

    def __init__(self) -> None:
        self.encode_calls: list[list[str]] = []

    def encode(self, texts, normalize_embeddings: bool = False):
        self.encode_calls.append(list(texts))
        vecs = []
        for t in texts:
            digest = hashlib.sha256(t.encode("utf-8")).digest()
            v = np.frombuffer(digest[: self.DIM], dtype=np.uint8).astype("float32")
            if normalize_embeddings:
                norm = float(np.linalg.norm(v)) or 1.0
                v = v / norm
            vecs.append(v)
        return np.array(vecs, dtype="float32")

    @property
    def n_encoded(self) -> int:
        return sum(len(batch) for batch in self.encode_calls)


@pytest.fixture
def fake_model(monkeypatch) -> _FakeModel:
    model = _FakeModel()
    monkeypatch.setattr(ss, "_get_model", lambda: model)
    return model


def _make_kb(tmp_path: Path, files: dict[str, str]) -> Path:
    sources = tmp_path / "Sources"
    sources.mkdir()
    for relpath, content in files.items():
        target = sources / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return tmp_path


class TestEmbeddingCache:
    def test_miss_writes_npy_and_manifest(self, tmp_path: Path, fake_model: _FakeModel) -> None:
        kb = _make_kb(tmp_path, {"a.md": "alpha content", "b.md": "beta content"})

        n = ss.index_kb(kb, backend="embeddings")
        assert n == 2

        cache_dir = kb / ".embeddings"
        manifest = json.loads((cache_dir / "manifest.json").read_text())
        assert manifest["model"] == ss._MODEL_NAME
        assert set(manifest["entries"]) == {"Sources/a.md", "Sources/b.md"}
        # One .npy per distinct content, each named by its sha.
        for entry in manifest["entries"].values():
            assert (cache_dir / entry["npy"]).exists()
            assert entry["npy"] == f"{entry['sha']}.npy"
        assert fake_model.n_encoded == 2

    def test_hit_avoids_recompute(self, tmp_path: Path, fake_model: _FakeModel) -> None:
        kb = _make_kb(tmp_path, {"a.md": "alpha content", "b.md": "beta content"})
        paths = ss._collect_paths(kb, ("Sources", "Wiki", "Output"))

        ss._embed_paths(kb, paths)
        assert fake_model.n_encoded == 2  # first pass: both encoded

        fake_model.encode_calls.clear()
        ss._embed_paths(kb, paths)
        assert fake_model.n_encoded == 0  # second pass: all served from cache

    def test_edited_content_new_sha_no_stale_vector(
        self, tmp_path: Path, fake_model: _FakeModel
    ) -> None:
        kb = _make_kb(tmp_path, {"a.md": "version A content"})
        paths = ss._collect_paths(kb, ("Sources", "Wiki", "Output"))
        card = kb / "Sources" / "a.md"

        vecs_a = ss._embed_paths(kb, paths)
        sha_a = ss._content_sha("version A content")
        expected_a = fake_model.encode(["version A content"], normalize_embeddings=True)[0]
        assert np.allclose(vecs_a[card], expected_a)

        # Edit the card; sha must change and the new vector must reflect B, not A.
        card.write_text("version B content totally different", encoding="utf-8")
        sha_b = ss._content_sha("version B content totally different")
        assert sha_b != sha_a

        vecs_b = ss._embed_paths(kb, paths)
        expected_b = fake_model.encode(
            ["version B content totally different"], normalize_embeddings=True
        )[0]
        assert np.allclose(vecs_b[card], expected_b)
        assert not np.allclose(vecs_b[card], expected_a)  # never serves the stale vector

        cache_dir = kb / ".embeddings"
        manifest = json.loads((cache_dir / "manifest.json").read_text())
        assert manifest["entries"]["Sources/a.md"]["sha"] == sha_b
        assert (cache_dir / f"{sha_b}.npy").exists()
        # The superseded vector is evicted, not left orphaned on disk.
        assert not (cache_dir / f"{sha_a}.npy").exists()

    def test_default_path_never_touches_embeddings(self, tmp_path: Path, monkeypatch) -> None:
        # If the default (tfidf) path ever invoked the embeddings backend, this
        # would explode — _get_model raises and .embeddings/ would be created.
        def _boom():
            raise AssertionError("default path must not load the embeddings model")

        monkeypatch.setattr(ss, "_get_model", _boom)
        kb = _make_kb(tmp_path, {"a.md": "exhausted T cells", "b.md": "microbiome"})

        hits = ss.search(kb, "exhausted T cells")  # default backend="tfidf"
        assert hits and hits[0].path.name == "a.md"
        assert not (kb / ".embeddings").exists()

    def test_embeddings_search_returns_ranked_hits(
        self, tmp_path: Path, fake_model: _FakeModel
    ) -> None:
        kb = _make_kb(
            tmp_path,
            {"a.md": "alpha alpha alpha", "b.md": "beta", "c.md": "gamma"},
        )
        hits = ss.search(kb, "alpha alpha alpha", backend="embeddings", top_k=3)
        assert hits
        # The exact-text doc embeds to the query vector → cosine 1.0 → rank 1.
        assert hits[0].path.name == "a.md"
        scores = [h.score for h in hits]
        assert scores == sorted(scores, reverse=True)
