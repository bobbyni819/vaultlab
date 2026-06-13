"""Recipe invariant meta-test (NEXT_STEPS B8 + B12).

Every figure recipe registered in ``vaultlab.figures.recipes`` must satisfy a
small structural contract so the recipe library stays trustworthy:

- a non-empty ``RECIPE_VERSION`` string;
- an ``ANCHOR_PAPERS`` tuple of **>= 3** entries — the rule that makes a recipe
  trustworthy: its layout is lifted from real published figures, not an AI
  guess (CLAUDE.md commitment #8). An entry counts when it names an accredited
  published source OR a well-established OSS tool / gallery (e.g. scanpy,
  squidpy), matching commitment #8's "accredited published work OR well-tested
  OSS project" wording;
- a callable ``render()`` whose ``output_path`` and ``title`` are keyword-only;
- a module ``__all__`` of exactly ``{ANCHOR_PAPERS, RECIPE_VERSION, render}``.

This is the automated enforcement of ``templates/recipe/README.md``'s
"Recipes without 3+ references fail review" — previously a manual-review
convention with no code check (NEXT_STEPS B12), and the first per-recipe test
coverage (NEXT_STEPS B8).
"""

from __future__ import annotations

import inspect
from types import ModuleType

import pytest

import vaultlab.figures.recipes as recipes

RECIPE_NAMES = sorted(recipes.__all__)

# The minimum number of anchor references every recipe must cite. See the
# module docstring + CLAUDE.md commitment #8 for the rationale.
MIN_ANCHOR_PAPERS = 3


def _module(name: str) -> ModuleType:
    return getattr(recipes, name)


def test_registry_nonempty() -> None:
    assert RECIPE_NAMES, "no recipes registered in vaultlab.figures.recipes.__all__"


@pytest.mark.parametrize("name", RECIPE_NAMES)
def test_recipe_has_version(name: str) -> None:
    mod = _module(name)
    version = getattr(mod, "RECIPE_VERSION", None)
    assert isinstance(version, str) and version.strip(), (
        f"{name}.RECIPE_VERSION must be a non-empty string"
    )


@pytest.mark.parametrize("name", RECIPE_NAMES)
def test_recipe_has_three_anchor_papers(name: str) -> None:
    """B12: >= 3 anchor references per recipe (commitment #8)."""
    mod = _module(name)
    anchors = getattr(mod, "ANCHOR_PAPERS", None)
    assert isinstance(anchors, tuple), f"{name}.ANCHOR_PAPERS must be a tuple"
    assert all(isinstance(a, str) and a.strip() for a in anchors), (
        f"{name}.ANCHOR_PAPERS entries must be non-empty strings"
    )
    assert len(anchors) >= MIN_ANCHOR_PAPERS, (
        f"{name}.ANCHOR_PAPERS has only {len(anchors)} entries; recipes require "
        f">= {MIN_ANCHOR_PAPERS} (a layout lifted from >= {MIN_ANCHOR_PAPERS} real "
        "published figures / established OSS galleries — commitment #8)."
    )


@pytest.mark.parametrize("name", RECIPE_NAMES)
def test_recipe_render_contract(name: str) -> None:
    mod = _module(name)
    render = getattr(mod, "render", None)
    assert callable(render), f"{name}.render is not callable"
    params = inspect.signature(render).parameters
    for kw in ("output_path", "title"):
        assert kw in params, f"{name}.render is missing keyword arg {kw!r}"
        assert params[kw].kind is inspect.Parameter.KEYWORD_ONLY, (
            f"{name}.render({kw}=...) must be keyword-only"
        )


@pytest.mark.parametrize("name", RECIPE_NAMES)
def test_recipe_all_exports(name: str) -> None:
    mod = _module(name)
    assert set(getattr(mod, "__all__", [])) == {
        "ANCHOR_PAPERS",
        "RECIPE_VERSION",
        "render",
    }, f"{name}.__all__ must be exactly ANCHOR_PAPERS, RECIPE_VERSION, render"
