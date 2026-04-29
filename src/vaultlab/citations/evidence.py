"""Evidence index --- cached verification results for fast re-lookup."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any


class EvidenceIndex:
    """Machine-readable index mapping DOI -> verified claims.

    Stored at <kb_dir>/Sources/.evidence_index.json.
    Prevents re-verifying the same claim against the same paper.
    """

    def __init__(self, kb_dir: str):
        self._path = os.path.join(kb_dir, "Sources", ".evidence_index.json")
        self._data: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self._path):
            try:
                with open(self._path, encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, PermissionError):
                self._data = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        tmp_path = self._path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
        # Atomic rename (on Windows, need to remove target first)
        if os.path.exists(self._path):
            os.replace(tmp_path, self._path)
        else:
            os.rename(tmp_path, self._path)

    def lookup(self, doi: str, claim: str) -> dict[str, Any] | None:
        """Look up a previously verified claim for a paper.

        Args:
            doi: Paper DOI.
            claim: The claim text to look up.

        Returns:
            Dict with status, evidence_chunk, confidence, etc. or None.
        """
        doi = doi or ""
        doi_key = doi.lower().strip()
        paper_data = self._data.get(doi_key)
        if not paper_data:
            return None

        claim_key = claim.strip().lower()
        for entry in paper_data.get("claims", []):
            if entry.get("claim", "").strip().lower() == claim_key:
                return entry

        return None

    def store(
        self,
        doi: str,
        claim: str,
        status: str,
        evidence_chunk: str,
        chunk_location: str,
        confidence: float,
        source_file: str,
    ) -> None:
        """Store a verified claim in the index.

        Args:
            doi: Paper DOI.
            claim: The claim text.
            status: Verification status string.
            evidence_chunk: The evidence passage.
            chunk_location: Where in the paper.
            confidence: Confidence score.
            source_file: File where this citation was found.
        """
        doi = doi or ""
        doi_key = doi.lower().strip()
        claim_key = claim.strip().lower()

        if doi_key not in self._data:
            self._data[doi_key] = {"claims": []}

        # Check if claim already exists
        for entry in self._data[doi_key]["claims"]:
            if entry.get("claim", "").strip().lower() == claim_key:
                # Add source file if new
                if source_file not in entry.get("source_files", []):
                    entry.setdefault("source_files", []).append(source_file)
                self._save()
                return

        # New claim
        self._data[doi_key]["claims"].append(
            {
                "claim": claim,
                "status": status,
                "evidence_chunk": evidence_chunk,
                "chunk_location": chunk_location,
                "confidence": confidence,
                "verified_date": datetime.now().strftime("%Y-%m-%d"),
                "source_files": [source_file],
            }
        )
        self._save()

    def list_all(self) -> list[dict]:
        """List all verified papers with their claims.

        Returns:
            List of dicts with doi, claim_count, and latest_date for each paper.
        """
        result = []
        for doi, paper_data in sorted(self._data.items()):
            claims = paper_data.get("claims", [])
            latest = max(
                (c.get("verified_date", "") for c in claims),
                default="",
            )
            result.append(
                {
                    "doi": doi,
                    "claim_count": len(claims),
                    "latest_verified": latest,
                    "statuses": [c.get("status", "") for c in claims],
                }
            )
        return result

    def stats(self) -> dict[str, int]:
        """Return stats about the evidence index."""
        total_papers = len(self._data)
        total_claims = sum(len(p.get("claims", [])) for p in self._data.values())
        return {"total_papers": total_papers, "total_claims": total_claims}
