"""vaultlab.slides.annotate — slide-level figure annotation overlays.

This package hosts the imperative annotation primitives used by the
plan-driven deck builder. The figure-understanding pipeline that *generates*
annotation specs lives in :mod:`vaultlab.figures.understand`.
"""

from __future__ import annotations

from vaultlab.slides.annotate.figure_annotations import add_annotations

__all__ = ["add_annotations"]
