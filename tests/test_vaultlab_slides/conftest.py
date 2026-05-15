"""Memory-pressure mitigation for slides tests.

Background
----------
The full test suite (~2046 tests on 2026-05-15) intermittently hits
``zipfile.MemoryError: Unable to allocate output buffer`` on Windows when
many ``python-pptx`` write paths execute in the same Python process.

Root cause: ``Presentation.save()`` builds the .pptx by writing into an
in-memory ``zipfile.ZipFile`` (backed by a ``BytesIO``). Each call leaves a
small amount of buffered state that Python's allocator won't reuse until
the reference graph is broken. Across 100+ ``pres.save()`` calls in one
process, fragmented allocations starve the next call's output buffer.

The bleed is non-deterministic — the same test passes in isolation and
fails at random positions inside a long suite, depending on host memory
pressure from other processes. The state-doc agent on 2026-05-15
observed 10 such failures on a single run; the CI matrix (Ubuntu) does
not reproduce because Linux's allocator coalesces freed pages more
aggressively.

Fix
---
Force a ``gc.collect()`` after every slides test. That breaks reference
cycles that hold ZipFile internals alive (e.g. lxml ElementTree ↔ pptx
parts), letting the allocator hand the pages back to the next save call.

This is cheap (~1 ms per test, ~300 ms total for the slides suite) and
has no behavioural impact — it just keeps the working set bounded.
"""

from __future__ import annotations

import gc

import pytest


@pytest.fixture(autouse=True)
def _slides_gc_sweep():
    """Force garbage collection after each slides test to release pptx/ZipFile buffers."""
    yield
    # Single full-generation collection is enough to break pptx↔lxml
    # reference cycles. A second pass costs ~10× the runtime for no
    # observable memory gain on the slides suite.
    gc.collect()
