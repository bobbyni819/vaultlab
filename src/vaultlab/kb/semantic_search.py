"""KB semantic search — BM25 lexical default + optional embedding hook.

Phase 6 of the file-05 build. Master plan §5.

Three backends:

- **BM25** (default, always available) — Okapi BM25, pure stdlib. Indexes
  markdown files and ranks by BM25 score (term-frequency saturation + document
  length normalization). A strictly stronger lexical baseline than TF-IDF cosine
  for keyword-style queries.
- **TF-IDF** (opt-in via ``backend="tfidf"``) — the previous lexical default;
  cosine over TF-IDF vectors. Retained for comparison/benchmarking.
- **Embeddings** (opt-in via ``backend="embeddings"``) — uses
  ``sentence-transformers`` when installed. Better for natural-language
  queries and cross-vocabulary matching. Caches embeddings to
  ``<kb>/.embeddings/`` keyed by content hash. Falls back to BM25 if the
  dependency is missing.

All backends share the same :func:`search` interface so callers don't have
to switch.

Examples
--------
>>> from vaultlab.kb.semantic_search import search  # doctest: +SKIP
>>> hits = search(kb_path="/g/My Drive/Knowledge/research", query="exhausted T cells")  # doctest: +SKIP
>>> for h in hits[:5]:  # doctest: +SKIP
...     print(f"{h.score:.3f}  {h.path.name}")
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import warnings
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Backend = Literal["bm25", "tfidf", "embeddings"]

# Model used by the opt-in embeddings backend. The content hash keys on this name
# too, so switching models can never serve a vector cached for a different model.
_MODEL_NAME = "all-MiniLM-L6-v2"
_EMBED_TEXT_CAP = 5000  # chars per doc fed to the encoder (matches prior behavior)


@dataclass
class SearchHit:
    """One search result."""

    path: Path
    score: float
    snippet: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def search(
    kb_path: str | Path,
    query: str,
    *,
    top_k: int = 10,
    backend: Backend = "bm25",
    subdirs: tuple[str, ...] = ("Sources", "Wiki", "Output"),
) -> list[SearchHit]:
    """Search the KB for files matching ``query``.

    Parameters
    ----------
    kb_path
        Root folder of the knowledge base.
    query
        Free-form query string.
    top_k
        Number of hits to return. Default 10.
    backend
        ``"bm25"`` (default, no extra deps), ``"tfidf"`` (legacy lexical), or
        ``"embeddings"`` (requires sentence-transformers; falls back to bm25 if
        missing).
    subdirs
        KB subdirectories to scan. Defaults to the canonical three.

    Returns
    -------
    list[SearchHit]
        Hits in descending score order. Empty if no matches.
    """
    kb_root = Path(kb_path)
    if not kb_root.exists():
        return []

    paths = _collect_paths(kb_root, subdirs)
    if not paths:
        return []

    if backend == "embeddings":
        try:
            return _search_embeddings(paths, query, top_k, kb_root)
        except ImportError:
            warnings.warn(
                "sentence-transformers not installed; falling back to the bm25 backend.",
                ImportWarning,
                stacklevel=2,
            )  # fall through to the lexical default (bm25)
    if backend == "tfidf":
        return _search_tfidf(paths, query, top_k)
    return _search_bm25(paths, query, top_k)


def index_kb(
    kb_path: str | Path,
    *,
    backend: Backend = "bm25",
    subdirs: tuple[str, ...] = ("Sources", "Wiki", "Output"),
) -> int:
    """Pre-build and cache the index for faster subsequent searches.

    For the lexical backends (bm25/tfidf), indexing is so fast (<100ms for typical
    KBs) that this is mostly useful for the embeddings backend. Returns the number
    of files indexed.
    """
    kb_root = Path(kb_path)
    if not kb_root.exists():
        return 0
    paths = _collect_paths(kb_root, subdirs)
    if backend == "embeddings":
        try:
            _embed_paths(kb_root, paths)
        except ImportError:
            pass
    return len(paths)


# ---------------------------------------------------------------------------
# Lexical backends (pure stdlib — no numpy)
# ---------------------------------------------------------------------------


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]{2,}")

_BM25_K1 = 1.5  # term-frequency saturation
_BM25_B = 0.75  # document-length normalization strength


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _search_bm25(
    paths: list[Path], query: str, top_k: int, *, k1: float = _BM25_K1, b: float = _BM25_B
) -> list[SearchHit]:
    """Okapi BM25 ranking (default lexical backend).

    Improves on TF-IDF cosine via term-frequency saturation (a term repeated 10×
    is not 10× as relevant) and document-length normalization (long documents do
    not win by sheer size). Uses the non-negative IDF form so common terms never
    contribute a negative score.
    """
    docs: list[tuple[Path, str, Counter[str], int]] = []
    for p in paths:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        tokens = _tokenize(text)
        docs.append((p, text, Counter(tokens), len(tokens)))

    if not docs:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    n_docs = len(docs)
    df: Counter[str] = Counter()
    for _, _, tf, _length in docs:
        df.update(tf.keys())
    total_len = sum(length for _, _, _, length in docs)
    avgdl = total_len / n_docs if total_len else 1.0  # 1.0 guards all-empty docs

    def idf(term: str) -> float:
        n = df.get(term, 0)
        # +1 inside the log keeps IDF (and therefore every score term) >= 0.
        return math.log(1 + (n_docs - n + 0.5) / (n + 0.5))

    q_terms = set(query_tokens)
    hits: list[SearchHit] = []
    for path, text, tf, length in docs:
        score = 0.0
        for term in q_terms:
            f = tf.get(term, 0)
            if not f:
                continue
            denom = f + k1 * (1 - b + b * length / avgdl)
            score += idf(term) * (f * (k1 + 1)) / denom
        if score > 0.0:
            hits.append(SearchHit(path=path, score=score, snippet=_snippet_for(text, query_tokens)))

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:top_k]


# ---------------------------------------------------------------------------
# TF-IDF backend (legacy lexical — opt-in via backend="tfidf")
# ---------------------------------------------------------------------------


def _search_tfidf(paths: list[Path], query: str, top_k: int) -> list[SearchHit]:
    docs: list[tuple[Path, str, list[str]]] = []
    for p in paths:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        docs.append((p, text, _tokenize(text)))

    if not docs:
        return []

    # Document frequency for IDF
    df: Counter[str] = Counter()
    for _, _, tokens in docs:
        df.update(set(tokens))
    n_docs = len(docs)

    def idf(term: str) -> float:
        return math.log((n_docs + 1) / (df.get(term, 0) + 1)) + 1

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []
    query_vec: dict[str, float] = {}
    qcounter = Counter(query_tokens)
    for term, count in qcounter.items():
        query_vec[term] = count * idf(term)
    query_norm = math.sqrt(sum(v * v for v in query_vec.values())) or 1.0

    hits: list[SearchHit] = []
    for path, text, tokens in docs:
        if not tokens:
            continue
        tf = Counter(tokens)
        # Build doc vector restricted to query terms (sparse dot product)
        dot = 0.0
        for term, qweight in query_vec.items():
            if term in tf:
                dot += tf[term] * idf(term) * qweight
        if dot == 0.0:
            continue
        # Approximate doc norm via the terms we touched + remaining
        doc_norm = math.sqrt(sum((c * idf(t)) ** 2 for t, c in tf.items())) or 1.0
        score = dot / (doc_norm * query_norm)
        snippet = _snippet_for(text, query_tokens)
        hits.append(SearchHit(path=path, score=score, snippet=snippet))

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:top_k]


def _snippet_for(text: str, query_tokens: list[str]) -> str:
    """Return ~200 chars of the document around the first query-token match."""
    lower = text.lower()
    for q in query_tokens:
        idx = lower.find(q)
        if idx != -1:
            start = max(0, idx - 80)
            end = min(len(text), idx + 120)
            return text[start:end].replace("\n", " ").strip()
    return text[:200].replace("\n", " ").strip()


# ---------------------------------------------------------------------------
# Embeddings backend — opt-in via sentence-transformers
# ---------------------------------------------------------------------------


def _get_model():  # pragma: no cover - requires optional dep; tests monkeypatch this seam
    """Load the sentence-transformers model. Single seam so tests can inject a
    fake encoder without downloading the real model. Raises ImportError if the
    optional dependency is absent (callers fall back to tfidf)."""
    from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

    return SentenceTransformer(_MODEL_NAME)


def _content_sha(text: str) -> str:
    """Content hash keyed on (model, text). An edited card → new sha (so a stale
    vector is never served); a model change → new sha (no cross-model collision)."""
    h = hashlib.sha256()
    h.update(_MODEL_NAME.encode("utf-8"))
    h.update(b"\x00")
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def _embeddings_cache_dir(kb_root: Path) -> Path:
    return kb_root / ".embeddings"


def _load_manifest(cache_dir: Path) -> dict:
    """Read the cache manifest; a missing/corrupt manifest is treated as empty."""
    manifest_path = cache_dir / "manifest.json"
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"model": _MODEL_NAME, "entries": {}}
    if not isinstance(data, dict) or data.get("model") != _MODEL_NAME:
        # Different model (or malformed) — rebuild rather than serve foreign vectors.
        return {"model": _MODEL_NAME, "entries": {}}
    data.setdefault("entries", {})
    return data


def _save_manifest(cache_dir: Path, manifest: dict) -> None:
    (cache_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )


def _embed_paths(kb_root: Path, paths: list[Path], model=None) -> dict:
    """Embed ``paths``, persisting a per-file ``.npy`` cache under
    ``<kb>/.embeddings/`` plus a ``manifest.json`` mapping relpath → content sha.

    On a cache hit (``<sha>.npy`` present and the manifest sha matches the current
    file content) the stored vector is loaded; on a miss the doc is (batch-)encoded,
    written to ``<sha>.npy``, and the manifest updated. Returns ``{path: vector}``
    for every readable path. Raises ImportError if the model can't be loaded.
    """
    import numpy as np  # type: ignore[import-untyped]

    cache_dir = _embeddings_cache_dir(kb_root)
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(cache_dir)
    entries: dict = manifest["entries"]

    readable: list[tuple[Path, str, str, str]] = []  # (path, relkey, sha, capped_text)
    for p in paths:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        try:
            relkey = str(p.relative_to(kb_root))
        except ValueError:
            relkey = str(p)
        capped = text[:_EMBED_TEXT_CAP]
        readable.append((p, relkey, _content_sha(capped), capped))

    # Partition into hits (cached npy present + sha matches) and misses.
    vectors: dict = {}
    misses: list[tuple[Path, str, str, str]] = []
    for p, relkey, sha, capped in readable:
        npy_path = cache_dir / f"{sha}.npy"
        if entries.get(relkey, {}).get("sha") == sha and npy_path.exists():
            try:
                vectors[p] = np.load(npy_path)
                continue
            except (OSError, ValueError):
                pass  # corrupt cache file — recompute
        misses.append((p, relkey, sha, capped))

    if misses:
        model = model or _get_model()
        encoded = np.asarray(
            model.encode([capped for _, _, _, capped in misses], normalize_embeddings=True)
        )
        for (p, relkey, sha, _capped), vec in zip(misses, encoded):
            vec = np.asarray(vec)
            np.save(cache_dir / f"{sha}.npy", vec)
            entries[relkey] = {"sha": sha, "npy": f"{sha}.npy"}
            vectors[p] = vec
        _save_manifest(cache_dir, manifest)
        _evict_orphans(cache_dir, entries)

    return vectors


def _evict_orphans(cache_dir: Path, entries: dict) -> None:
    """Delete ``.npy`` files no longer referenced by any manifest entry, so a card
    edited N times leaves one vector on disk, not N. Content-addressed, so a sha is
    removed only when *no* entry points at it (shared content stays)."""
    referenced = {e.get("sha") for e in entries.values()}
    for npy in cache_dir.glob("*.npy"):
        if npy.stem not in referenced:
            try:
                npy.unlink()
            except OSError:
                pass


def _search_embeddings(
    paths: list[Path], query: str, top_k: int, kb_root: Path
) -> list[SearchHit]:
    import numpy as np  # type: ignore[import-untyped]

    model = _get_model()
    vectors = _embed_paths(kb_root, paths, model=model)
    if not vectors:
        return []

    # doc_paths[i] must align with matrix row i — relies on dict insertion order.
    doc_paths = list(vectors.keys())
    matrix = np.stack([vectors[p] for p in doc_paths])
    q_emb = np.asarray(model.encode([query], normalize_embeddings=True))[0]
    scores = matrix @ q_emb  # cosine since both sides are normalized
    order = np.argsort(-scores)[:top_k]

    query_tokens = _tokenize(query)
    hits: list[SearchHit] = []
    for i in order:
        p = doc_paths[i]
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        hits.append(
            SearchHit(path=p, score=float(scores[i]), snippet=_snippet_for(text, query_tokens))
        )
    return hits


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


_TEXT_GLOBS = ("*.md", "*.txt")


def _collect_paths(kb_root: Path, subdirs: tuple[str, ...]) -> list[Path]:
    """Walk the KB and collect text files in the named subdirectories.

    Indexes ``.md`` and ``.txt`` files. When a named subdir does not exist the
    KB root itself is searched as a fallback (supports flat corpora dumped
    directly into the KB root).

    Dot-prefixed segments *inside* the KB (``.obsidian/``, ``.git/``,
    ``.embeddings/``) are skipped. Dot-prefixed components in the KB root's own
    path are deliberately ignored — otherwise a KB mounted under e.g. Google
    Drive's ``.shortcut-targets-by-id`` shortcut would collect zero files.
    """
    out: list[Path] = []
    seen: set[Path] = set()

    def _add(paths):
        for p in paths:
            if p not in seen:
                seen.add(p)
                out.append(p)

    for sub in subdirs:
        d = kb_root / sub
        if not d.exists():
            continue
        for glob in _TEXT_GLOBS:
            _add(
                p for p in d.rglob(glob)
                if not any(part.startswith(".") for part in p.relative_to(d).parts)
            )
    # Always include files directly in the KB root (supports flat corpora).
    for glob in _TEXT_GLOBS:
        _add(
            p for p in kb_root.glob(glob)
            if not any(part.startswith(".") for part in p.relative_to(kb_root).parts)
        )
    return out


__all__ = ["Backend", "SearchHit", "index_kb", "search"]
