"""Backfill anonymous-author summaries in vaultlab Wiki/Summaries.

Walks every ``Wiki/Summaries/*.md`` file, detects frontmatter where
``authors`` is missing/empty/blank, runs the chain backfill
(OpenAlex -> CrossRef-by-DOI -> Semantic Scholar -> bioRxiv), and
rewrites the frontmatter in place when authors are recovered. Also
backfills ``year``, ``title``, ``journal`` if those were empty AND we
have them from the recovery source.

Outputs a JSON log: ``Wiki/Summaries/_backfill-log-<timestamp>.json``
with the recovery source per DOI and the unresolvable list. Truly
unresolvable DOIs additionally land in ``docs/known-unresolvable-dois.md``.

Usage::

    python scripts/_backfill_anonymous_authors.py \\
        --kb "G:/My Drive/Knowledge/vaultlab" \\
        [--limit 50]            # cap papers processed (debug)
        [--dry-run]             # don't write files

Idempotent: re-running on already-backfilled summaries is a no-op.
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import logging
import re
import sys
from pathlib import Path

# Force stdout/stderr to UTF-8 on Windows so DOI Unicode characters
# (e.g. U+2010 hyphen) don't crash logging via cp1252.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

# Make repo `src/` importable when run as `python scripts/...`
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "src"))

import yaml  # noqa: E402  (after sys.path)

from vaultlab.research.corpus import (  # noqa: E402
    Corpus,
    _default_author_chain,
    backfill_authors_via_chain,
    has_anonymous_author,
)
from vaultlab.research.paper import Paper  # noqa: E402
from vaultlab.research.sources.crossref import CrossRefClient  # noqa: E402
from vaultlab.research.sources.openalex import OpenAlexClient  # noqa: E402

logger = logging.getLogger(__name__)


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict, str, str]:
    """Return ``(fm_dict, fm_yaml_block, body)``. Raises on malformed."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("no frontmatter")
    yaml_block = m.group(1)
    body = text[m.end() :]
    fm = yaml.safe_load(yaml_block) or {}
    if not isinstance(fm, dict):
        raise ValueError("frontmatter is not a mapping")
    return fm, yaml_block, body


def _is_anonymous(fm: dict) -> bool:
    """True iff frontmatter has missing / empty / blank-only authors."""
    authors = fm.get("authors")
    if authors in (None, "", []):
        return True
    if not isinstance(authors, list):
        return True
    return not any(isinstance(a, str) and a.strip() for a in authors)


def _doi_from_frontmatter(fm: dict, fallback_filename: str) -> str:
    doi = (fm.get("doi") or "").strip().lower()
    if doi:
        return doi
    # Fall back to deriving from the slugified filename (rev of slugify_doi).
    return fallback_filename.replace(".md", "").replace("_", "/", 1)


def _write_back(
    path: Path,
    fm: dict,
    body: str,
    *,
    dry_run: bool,
) -> None:
    """Re-emit the file with updated frontmatter, preserving body."""
    new_fm = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
    new_text = f"---\n{new_fm}\n---\n{body}"
    if dry_run:
        return
    path.write_text(new_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--kb",
        default="G:/My Drive/Knowledge/vaultlab",
        help="Path to the vaultlab KB root (contains Wiki/Summaries/)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process at most N anonymous summaries (0 = all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the chain but don't write any files",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose progress logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    kb_root = Path(args.kb).expanduser()
    summaries_dir = kb_root / "Wiki" / "Summaries"
    if not summaries_dir.is_dir():
        print(f"Wiki/Summaries not found at {summaries_dir}", file=sys.stderr)
        return 2

    # Phase 1: enumerate anonymous summaries
    candidates: list[tuple[Path, dict, str]] = []
    skipped_malformed: list[str] = []
    for path in sorted(summaries_dir.glob("*.md")):
        if path.name.startswith("_"):  # skip indexes / logs
            continue
        try:
            text = path.read_text(encoding="utf-8")
            fm, _, body = _parse_frontmatter(text)
        except Exception as exc:
            skipped_malformed.append(f"{path.name}: {exc}")
            continue
        if _is_anonymous(fm):
            candidates.append((path, fm, body))

    print(f"Found {len(candidates)} anonymous summaries (of "
          f"{len(list(summaries_dir.glob('*.md')))} total).")
    if skipped_malformed:
        print(f"Skipped {len(skipped_malformed)} malformed files.")

    if args.limit and args.limit > 0:
        candidates = candidates[: args.limit]
        print(f"--limit cap: processing {len(candidates)}")

    # Phase 2: load each into a Corpus and run the chain. We process in
    # small batches to keep memory low and to ensure progress reporting.
    chain = _default_author_chain()
    crossref_client = CrossRefClient()  # re-used for journal/year backfill
    openalex_client = OpenAlexClient()

    recovered: dict[str, dict] = {}
    unresolvable: list[str] = []

    for i, (path, fm, body) in enumerate(candidates, 1):
        doi = _doi_from_frontmatter(fm, path.name)
        if not doi:
            unresolvable.append(path.name)
            continue

        # Build a single-paper corpus and backfill.
        paper = Paper(
            title=fm.get("title") or "",
            doi=doi,
            year=int(fm.get("year") or 0),
            journal=fm.get("journal") or "",
            authors=[],  # forces backfill
            source_api="frontmatter",
        )
        corpus = Corpus(topic="backfill", seeds=[])
        corpus.papers[doi] = paper

        result = backfill_authors_via_chain(corpus, chain=chain)

        if doi not in result:
            unresolvable.append(doi)
            print(f"[{i}/{len(candidates)}] {doi}: UNRESOLVABLE")
            continue

        recovered_authors = result[doi]["authors"]
        source = result[doi]["source"]

        # Try to also recover title/year/journal if the source returned
        # them — helps Tier-C stubs that had ``year: 0``.
        if not paper.title or paper.year == 0 or not paper.journal:
            try:
                if source == "openalex":
                    full = openalex_client.resolve_doi(doi)
                else:
                    full = crossref_client.resolve_doi(doi)
            except Exception:
                full = None
            if full is not None:
                if not paper.title and full.title:
                    paper.title = full.title
                if paper.year == 0 and full.year:
                    paper.year = full.year
                if not paper.journal and full.journal:
                    paper.journal = full.journal

        # Rewrite frontmatter
        fm["authors"] = recovered_authors
        if paper.title and not fm.get("title"):
            fm["title"] = paper.title
        if paper.year and not fm.get("year"):
            fm["year"] = paper.year
        if paper.journal and not fm.get("journal"):
            fm["journal"] = paper.journal
        # Provenance breadcrumb so future audits know how this got filled.
        fm["authors_backfill_source"] = source
        fm["authors_backfilled_at"] = dt.datetime.now().isoformat(timespec="seconds")

        _write_back(path, fm, body, dry_run=args.dry_run)
        recovered[doi] = {
            "source": source,
            "authors": recovered_authors,
            "n_authors": len(recovered_authors),
            "file": path.name,
        }
        print(
            f"[{i}/{len(candidates)}] {doi}: {len(recovered_authors)} authors "
            f"via {source}"
        )

    # Phase 3: summary log
    log = {
        "ran_at": dt.datetime.now().isoformat(timespec="seconds"),
        "kb_root": str(kb_root),
        "dry_run": args.dry_run,
        "n_anonymous_found": len(candidates),
        "n_recovered": len(recovered),
        "n_unresolvable": len(unresolvable),
        "by_source": _tally_sources(recovered),
        "recovered": recovered,
        "unresolvable": unresolvable,
        "skipped_malformed": skipped_malformed,
    }
    log_path = (
        summaries_dir
        / f"_backfill-log-{dt.datetime.now():%Y-%m-%d-%H%M%S}.json"
    )
    if not args.dry_run:
        log_path.write_text(
            json.dumps(log, indent=2, default=str), encoding="utf-8"
        )

    # Update the known-unresolvable docs list (only when not dry-run).
    if unresolvable and not args.dry_run:
        repo_root = Path(__file__).resolve().parent.parent
        ul_path = repo_root / "docs" / "known-unresolvable-dois.md"
        ul_path.parent.mkdir(parents=True, exist_ok=True)
        existing = (
            ul_path.read_text(encoding="utf-8") if ul_path.exists() else ""
        )
        block = (
            f"\n## Run {dt.datetime.now():%Y-%m-%d %H:%M:%S}\n\n"
            f"Tried OpenAlex, CrossRef-by-DOI, Semantic Scholar, bioRxiv. "
            f"None returned authors:\n\n"
        )
        for d in sorted(unresolvable):
            block += f"- `{d}`\n"
        ul_path.write_text(existing + block, encoding="utf-8")

    print()
    print("=" * 60)
    print(f"Recovered: {len(recovered)} / {len(candidates)}")
    print(f"Unresolvable: {len(unresolvable)}")
    print(f"By source: {log['by_source']}")
    if not args.dry_run:
        print(f"Log: {log_path}")
    return 0


def _tally_sources(recovered: dict[str, dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for entry in recovered.values():
        out[entry["source"]] = out.get(entry["source"], 0) + 1
    return out


if __name__ == "__main__":
    raise SystemExit(main())
