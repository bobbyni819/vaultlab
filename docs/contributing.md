# Contributing — extended guide

The short version is in [`../CONTRIBUTING.md`](../CONTRIBUTING.md). This file goes deeper.

> **Status:** stub. Will be expanded once v0.1.0 ships and the contribution flow is real.

## Maintainer time budget

vaultlab has one maintainer (Bobby), running this as a side project. Issues are reviewed weekly. Don't take silence personally; ping `@bobbyni819` after a week if needed.

## Easy wins for first-time contributors

The lowest-friction contributions:
1. **Add a figure recipe** — pick a published figure style not yet in `vaultlab.figures.recipes/`. Document with ≥3 paper references. Most-impact, least-friction.
2. **Add a tool index entry** — document a Python package vaultlab should know about. Each is a single `.md` file.
3. **Improve a docstring or doc** — find anything unclear, fix it.
4. **Add a test fixture** — case studies that catch regressions.

## Things to avoid contributing without prior discussion

1. New top-level subpackages
2. Changes to AGENTS.md invariants
3. Dependency additions (especially heavy ones — PyTorch, R, Java)
4. Breaking changes to public API

For these, open an issue first.

## Coming in this doc

- Architecture decisions log
- Contributor "office hours" if there's demand
- Recognition (CONTRIBUTORS.md once it exists)
