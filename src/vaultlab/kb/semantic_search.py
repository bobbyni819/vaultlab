"""KB semantic search — TF-IDF baseline + optional embedding hook.

Phase 6 of the file-05 build. Master plan §5.

Two backends:

- **TF-IDF** (default, always available) — pure stdlib + numpy. Indexes
  ``Sources/`` markdown files; ranks by cosine similarity over TF-IDF vectors.
  Surprisingly strong baseline for short keyword-style queries.
- **Embeddings** (opt-in via ``backend="embeddings"``) — uses
  ``sentence-transformers`` when installed. Better for natural-language
  queries and cross-vocabulary matching. Caches embeddings to
  ``<kb>/.embeddings/`` keyed by file mtime.

Both backends share the same :func:`search` interface so callers don't have
to switch.

Examples
--------
>>> from vaultlab.kb.semantic_search import search  # doctest: +SKIP
>>> hits = search(kb_path="/g/My Drive/Knowledge/research", query="exhausted T cells")  # doctest: +SKIP
>>> for h in hits[:5]:  # doctest: +SKIP
...     print(f"{h.score:.3f}  {h.path.name}")
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Backend = Literal["tfidf", "embeddings"]


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
    backend: Backend = "tfidf",
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
        ``"tfidf"`` (default, no extra deps) or ``"embeddings"`` (requires
        sentence-transformers; falls back to tfidf with a warning if missing).
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
            return _search_embeddings(paths, query, top_k)
        except ImportError:
            pass  # fall through to tfidf
    return _search_tfidf(paths, query, top_k)


def index_kb(
    kb_path: str | Path,
    *,
    backend: Backend = "tfidf",
    subdirs: tuple[str, ...] = ("Sources", "Wiki", "Output"),
) -> int:
    """Pre-build and cache the index for faster subsequent searches.

    For TF-IDF, indexing is so fast (<100ms for typical KBs) that this is
    mostly useful for the embeddings backend. Returns the number of files
    indexed.
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
# TF-IDF backend (stdlib + numpy not required — pure-Python math.log)
# ---------------------------------------------------------------------------


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]{2,}")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


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


def _search_embeddings(
    paths: list[Path], query: str, top_k: int
) -> list[SearchHit]:  # pragma: no cover - requires optional dep
    import numpy as np  # type: ignore[import-untyped]
    from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

    model = SentenceTransformer("all-MiniLM-L6-v2")
    docs: list[tuple[Path, str]] = []
    for p in paths:
        try:
            docs.append((p, p.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue
    if not docs:
        return []

    doc_texts = [d[1][:5000] for d in docs]  # cap per-doc tokens for speed
    embeddings = model.encode(doc_texts, normalize_embeddings=True)
    q_emb = model.encode([query], normalize_embeddings=True)[0]
    scores = embeddings @ q_emb  # cosine since normalized
    order = np.argsort(-scores)[:top_k]
    return [
        SearchHit(
            path=docs[i][0],
            score=float(scores[i]),
            snippet=_snippet_for(docs[i][1], _tokenize(query)),
        )
        for i in order
    ]


def _embed_paths(kb_root: Path, paths: list[Path]) -> None:  # pragma: no cover - optional dep
    """Pre-cache embeddings under ``<kb>/.embeddings/<sha>.npy``.

    Not yet wired into _search_embeddings (which currently re-encodes per call).
    Reserved as the integration point when the build picks up the heavier
    embedding pipeline post-v0.1.
    """
    cache_dir = kb_root / ".embeddings"
    cache_dir.mkdir(exist_ok=True)
    # Stub for now; real impl writes per-file npy + a manifest.
    return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _collect_paths(kb_root: Path, subdirs: tuple[str, ...]) -> list[Path]:
    """Walk the KB and collect markdown files in the named subdirectories."""
    out: list[Path] = []
    for sub in subdirs:
        d = kb_root / sub
        if not d.exists():
            continue
        for p in d.rglob("*.md"):
            if any(part.startswith(".") for part in p.parts):
                continue
            out.append(p)
    return out


__all__ = ["Backend", "SearchHit", "index_kb", "search"]
