"""Citation graph builder for analyzing paper citation networks.

Builds directed citation graphs from seed papers using Semantic Scholar
data (via ResearchClient). Supports depth-limited traversal, cluster
detection, seminal paper identification, and export to Mermaid/Markdown.
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict, deque
from datetime import date
from typing import TYPE_CHECKING

from vaultlab.research.paper import Paper

if TYPE_CHECKING:
    from vaultlab.research import ResearchClient

logger = logging.getLogger(__name__)


class CitationGraph:
    """Build citation networks from seed papers.

    Uses a ResearchClient to fetch citations and references, then stores
    the resulting graph as nodes (doi -> Paper) and directed edges.

    Args:
        research_client: A configured ResearchClient instance.
    """

    def __init__(self, research_client: ResearchClient):
        self.client = research_client
        self.nodes: dict[str, Paper] = {}  # doi -> Paper
        self.edges: list[tuple[str, str, str]] = []  # (from_doi, to_doi, type)
        self._edge_set: set[tuple[str, str, str]] = set()  # for dedup

    def build(self, seed_dois: list[str], depth: int = 1) -> None:
        """Build graph from seed papers.

        For each seed paper at each depth level, fetches both papers that
        cite it (cited_by edges) and papers it references (cites edges).
        Recurses up to ``depth`` levels, adding new papers and edges.

        Args:
            seed_dois: List of DOIs to start from.
            depth: How many levels deep to traverse (1 = direct only).
        """
        if depth < 1:
            return

        # Queue: (doi, current_depth)
        queue: deque[tuple[str, int]] = deque()
        visited: set[str] = set()

        # Seed the queue
        for doi in seed_dois:
            doi = doi.strip()
            if not doi:
                continue
            # Try to get the seed paper metadata
            paper = self.client.get_paper(doi)
            if paper and paper.doi:
                self._add_node(paper)
                queue.append((paper.doi, 0))
            else:
                # Create a minimal node so we can still traverse
                placeholder = Paper(doi=doi, title=f"[{doi}]")
                self._add_node(placeholder)
                queue.append((doi, 0))

        while queue:
            current_doi, current_depth = queue.popleft()
            if current_doi in visited:
                continue
            visited.add(current_doi)

            if current_depth >= depth:
                continue

            # Get papers that cite this one
            try:
                citations = self.client.get_citations(current_doi)
                for citing_paper in citations:
                    if citing_paper.doi:
                        self._add_node(citing_paper)
                        self._add_edge(citing_paper.doi, current_doi, "cites")
                        if current_depth + 1 < depth:
                            queue.append((citing_paper.doi, current_depth + 1))
            except Exception as e:
                logger.warning("Failed to get citations for %s: %s", current_doi, e)

            # Get papers this one references
            try:
                references = self.client.get_references(current_doi)
                for ref_paper in references:
                    if ref_paper.doi:
                        self._add_node(ref_paper)
                        self._add_edge(current_doi, ref_paper.doi, "cites")
                        if current_depth + 1 < depth:
                            queue.append((ref_paper.doi, current_depth + 1))
            except Exception as e:
                logger.warning("Failed to get references for %s: %s", current_doi, e)

        logger.info(
            "Citation graph built: %d nodes, %d edges",
            len(self.nodes),
            len(self.edges),
        )

    def _add_node(self, paper: Paper) -> None:
        """Add a paper to the graph, merging if already present."""
        doi = paper.doi
        if not doi:
            return
        if doi in self.nodes:
            # Merge new info into existing node
            self.nodes[doi].merge(paper)
        else:
            self.nodes[doi] = paper

    def _add_edge(self, from_doi: str, to_doi: str, edge_type: str) -> None:
        """Add a directed edge, deduplicating."""
        key = (from_doi, to_doi, edge_type)
        if key not in self._edge_set:
            self._edge_set.add(key)
            self.edges.append(key)

    def get_seminal_papers(self, top_n: int = 5) -> list[Paper]:
        """Papers with most incoming citations in the graph.

        An incoming citation means another paper in the graph cites this one.
        Papers with many in-graph citations are likely seminal works.

        Args:
            top_n: Number of top papers to return.

        Returns:
            List of Papers sorted by in-graph citation count (descending).
        """
        incoming: dict[str, int] = defaultdict(int)
        for _from_doi, to_doi, edge_type in self.edges:
            if edge_type == "cites":
                incoming[to_doi] += 1

        # Sort by incoming count, break ties by global citation_count
        ranked = sorted(
            incoming.items(),
            key=lambda x: (x[1], self.nodes.get(x[0], Paper()).citation_count),
            reverse=True,
        )

        results = []
        for doi, _count in ranked[:top_n]:
            if doi in self.nodes:
                results.append(self.nodes[doi])
        return results

    def get_clusters(self) -> list[list[str]]:
        """Group papers by citation connectivity (connected components).

        Treats the citation graph as undirected for connectivity analysis.
        Returns groups of DOIs that are connected through citation chains.

        Returns:
            List of clusters, each cluster being a list of DOIs.
            Sorted by cluster size (largest first).
        """
        if not self.nodes:
            return []

        # Build adjacency list (undirected)
        adj: dict[str, set[str]] = defaultdict(set)
        for from_doi, to_doi, _type in self.edges:
            adj[from_doi].add(to_doi)
            adj[to_doi].add(from_doi)

        visited: set[str] = set()
        clusters: list[list[str]] = []

        for doi in self.nodes:
            if doi in visited:
                continue
            # BFS from this node
            cluster: list[str] = []
            bfs_queue: deque[str] = deque([doi])
            while bfs_queue:
                current = bfs_queue.popleft()
                if current in visited:
                    continue
                visited.add(current)
                cluster.append(current)
                for neighbor in adj.get(current, set()):
                    if neighbor not in visited and neighbor in self.nodes:
                        bfs_queue.append(neighbor)
            clusters.append(cluster)

        # Sort by size descending
        clusters.sort(key=len, reverse=True)
        return clusters

    def to_mermaid(self) -> str:
        """Export as Mermaid diagram for Obsidian.

        Generates a Mermaid flowchart with papers as nodes and citation
        edges as arrows. Paper titles are truncated to 40 characters.

        Returns:
            Mermaid diagram string.
        """
        lines = ["graph LR"]

        # Define nodes with short labels
        node_ids: dict[str, str] = {}
        for i, (doi, paper) in enumerate(self.nodes.items()):
            node_id = f"P{i}"
            node_ids[doi] = node_id
            # Truncate title for readability
            title = paper.title[:40] + "..." if len(paper.title) > 40 else paper.title
            # Escape quotes in title
            title = title.replace('"', "'")
            year = f" ({paper.year})" if paper.year else ""
            lines.append(f'    {node_id}["{title}{year}"]')

        # Define edges
        for from_doi, to_doi, edge_type in self.edges:
            from_id = node_ids.get(from_doi)
            to_id = node_ids.get(to_doi)
            if from_id and to_id:
                if edge_type == "cites":
                    lines.append(f"    {from_id} --> {to_id}")
                else:
                    lines.append(f"    {from_id} -.-> {to_id}")

        return "\n".join(lines)

    def to_markdown(self) -> str:
        """Export as markdown table with citation counts.

        Includes both global citation count (from the API) and in-graph
        citation count (how many papers in this graph cite it).

        Returns:
            Markdown-formatted string with paper table.
        """
        # Calculate in-graph citations
        in_graph: dict[str, int] = defaultdict(int)
        for _from_doi, to_doi, edge_type in self.edges:
            if edge_type == "cites":
                in_graph[to_doi] += 1

        lines = [
            "# Citation Graph",
            "",
            f"**Papers:** {len(self.nodes)} | **Edges:** {len(self.edges)}",
            "",
            "| # | Title | Authors | Year | Journal | DOI | Global Citations | In-Graph Citations |",
            "|---|-------|---------|------|---------|-----|-----------------|-------------------|",
        ]

        # Sort by in-graph citations, then global
        sorted_papers = sorted(
            self.nodes.values(),
            key=lambda p: (in_graph.get(p.doi, 0), p.citation_count),
            reverse=True,
        )

        for i, paper in enumerate(sorted_papers, 1):
            authors = ", ".join(paper.authors[:3])
            if len(paper.authors) > 3:
                authors += " et al."
            title = paper.title[:60] + "..." if len(paper.title) > 60 else paper.title
            ig = in_graph.get(paper.doi, 0)
            lines.append(
                f"| {i} | {title} | {authors} | {paper.year or '-'} | "
                f"{paper.journal or '-'} | {paper.doi} | {paper.citation_count} | {ig} |"
            )

        # Add clusters section
        clusters = self.get_clusters()
        if clusters and len(clusters) > 1:
            lines.extend(["", "## Clusters", ""])
            for i, cluster in enumerate(clusters, 1):
                titles = []
                for doi in cluster[:5]:
                    p = self.nodes.get(doi)
                    if p:
                        short = p.title[:40] + "..." if len(p.title) > 40 else p.title
                        titles.append(short)
                more = f" (+{len(cluster) - 5} more)" if len(cluster) > 5 else ""
                lines.append(f"**Cluster {i}** ({len(cluster)} papers): {', '.join(titles)}{more}")

        # Add seminal papers section
        seminal = self.get_seminal_papers(top_n=5)
        if seminal:
            lines.extend(["", "## Seminal Papers (most cited in graph)", ""])
            for i, paper in enumerate(seminal, 1):
                ig = in_graph.get(paper.doi, 0)
                lines.append(
                    f"{i}. **{paper.title}** ({paper.year or '?'}) "
                    f"- {ig} in-graph citations, {paper.citation_count} global"
                )

        return "\n".join(lines)

    def save_to_kb(self, kb_dir: str) -> str:
        """Save graph as markdown to Wiki/Summaries/citation-graph-{date}.md.

        Args:
            kb_dir: Path to the knowledge base root directory.

        Returns:
            Path to the saved markdown file.
        """
        summaries_dir = os.path.join(kb_dir, "Wiki", "Summaries")
        os.makedirs(summaries_dir, exist_ok=True)

        today = date.today().isoformat()
        filename = f"citation-graph-{today}.md"
        filepath = os.path.join(summaries_dir, filename)

        content = self.to_markdown()

        # Add Mermaid diagram at the end
        mermaid = self.to_mermaid()
        content += f"\n\n## Graph Visualization\n\n```mermaid\n{mermaid}\n```\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info("Citation graph saved to %s", filepath)
        return filepath
