"""Region merging - collapse fragmented same-motif components into single boxes.

A receptor drawn in BioRender often has a dark outline that breaks the
filled-color interior into multiple connected components. The 39-fragment
"endogenous-tcr-blue" output we saw on figure 1 is exactly this - a single
visual receptor split into 5-7 separate components per instance.

This module merges connected-component fragments belonging to the same motif
when they are spatially close. Three strategies:

- :func:`merge_regions` - default, dilation-based. Inflate each region's bbox
  by ``dilation_px`` then merge any pair whose inflated boxes overlap.
- :func:`merge_regions_by_proximity` - alternative, centroid-distance-based.
  Merge regions whose centroids are within ``max_distance_px``.
- :func:`group_horizontal_strip` - merge regions that fall in the same
  vertical band (useful when receptors stack vertically and we want one box
  per receptor stack).
"""

from __future__ import annotations

from collections.abc import Sequence

from vaultlab.figures.understand.color_motif import Region


def merge_regions(
    regions: Sequence[Region],
    *,
    dilation_px: int = 8,
) -> list[Region]:
    """Merge same-motif regions whose dilated bboxes overlap.

    The merged region keeps the parent motif name; bbox is the union; area is
    the sum; centroid is the area-weighted centroid.

    Parameters
    ----------
    regions
        Output of :func:`extract_regions`.
    dilation_px
        How many pixels to inflate each bbox before testing for overlap. Larger
        = more aggressive merging. ~8-15 px works for typical figures; tune
        based on the typical inter-fragment gap.

    Returns
    -------
    list[Region]
        Merged regions, sorted by descending area within each motif.
    """
    by_motif: dict[str, list[Region]] = {}
    for r in regions:
        by_motif.setdefault(r.motif_name, []).append(r)

    out: list[Region] = []
    for group in by_motif.values():
        out.extend(_merge_within_motif(group, dilation_px=dilation_px))
    return out


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _merge_within_motif(regions: list[Region], *, dilation_px: int) -> list[Region]:
    """Union-find style merge: any pair whose inflated bboxes overlap → group."""
    n = len(regions)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    for i in range(n):
        for j in range(i + 1, n):
            if _bboxes_overlap_dilated(regions[i].bbox_px, regions[j].bbox_px, dilation_px):
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    out: list[Region] = []
    for member_idxs in groups.values():
        members = [regions[i] for i in member_idxs]
        out.append(_combine(members))
    out.sort(key=lambda r: -r.area_px)
    return out


def _bboxes_overlap_dilated(
    a: tuple[int, int, int, int],
    b: tuple[int, int, int, int],
    dilation: int,
) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    # Inflate each by dilation before overlap test
    ax0d, ay0d, ax1d, ay1d = ax0 - dilation, ay0 - dilation, ax1 + dilation, ay1 + dilation
    bx0d, by0d, bx1d, by1d = bx0 - dilation, by0 - dilation, bx1 + dilation, by1 + dilation
    return not (ax1d <= bx0d or bx1d <= ax0d or ay1d <= by0d or by1d <= ay0d)


def _combine(members: list[Region]) -> Region:
    """Merge a group into one Region - union bbox, summed area, weighted centroid."""
    x0 = min(m.bbox_px[0] for m in members)
    y0 = min(m.bbox_px[1] for m in members)
    x1 = max(m.bbox_px[2] for m in members)
    y1 = max(m.bbox_px[3] for m in members)
    total_area = sum(m.area_px for m in members)
    cx = sum(m.centroid_px[0] * m.area_px for m in members) // max(total_area, 1)
    cy = sum(m.centroid_px[1] * m.area_px for m in members) // max(total_area, 1)
    return Region(
        motif_name=members[0].motif_name,
        bbox_px=(x0, y0, x1, y1),
        area_px=total_area,
        centroid_px=(cx, cy),
    )


__all__ = ["merge_regions"]
