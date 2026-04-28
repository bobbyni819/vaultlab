# Contributing to vaultlab

Thanks for your interest. vaultlab is a side project under active alpha development; contributions are welcome with realistic expectations on response time.

## Important: read first

- 📖 [`README.md`](README.md) — what vaultlab is
- 📖 [`AGENTS.md`](AGENTS.md) — invariants every code change must preserve (REQUIRED)
- 📖 [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) — Contributor Covenant 2.1

## Maintainer cadence (be honest about expectations)

vaultlab has one maintainer (Bobby). Issues are reviewed **weekly** (typically weekends). For urgent issues, mention `@bobbyni819` in the issue.

## How to contribute

### Reporting bugs

1. Run `vaultlab doctor` and include the output
2. Open an issue using the [bug template](.github/ISSUE_TEMPLATE/bug.md)
3. Include: minimal reproducer, expected vs actual, your platform + Python version

### Requesting features

1. Open an issue using the [feature template](.github/ISSUE_TEMPLATE/feature.md)
2. Describe the use case before proposing a solution
3. Check if it fits an existing subpackage before suggesting a new one

### Adding code

The lowest-friction contributions are:

| What you want to add | Use template | See |
|---|---|---|
| A new figure recipe | [`templates/recipe/`](templates/recipe/) | [Add a figure recipe](#add-a-figure-recipe) |
| A new agent role | [`templates/role/`](templates/role/) | [Add an agent role](#add-an-agent-role) |
| A new tool index entry | [`templates/tool_index_entry/`](templates/tool_index_entry/) | Document a Python package |
| A new data modality | [`templates/data_modality/`](templates/data_modality/) | New wet-lab data type wrapper |
| A new slash command | [`templates/slash_command/`](templates/slash_command/) | [Add a slash command](#add-a-slash-command) |
| A new pipeline phase | `vaultlab phase scaffold <name>` | Use the scaffold |

### Add a figure recipe

1. Copy `templates/recipe/` to `src/vaultlab/figures/recipes/<recipe_name>/`
2. Fill in `<recipe_name>.py` (renders the figure) and `<recipe_name>.md` (when to use, references)
3. **Required:** add ≥3 published examples to `vaultlab.figures.corpus/sources.json` under the recipe name. Recipes without provenance fail review.
4. Add a unit test in `tests/test_vaultlab_figures/test_recipe_<recipe_name>.py`
5. Run `pytest tests/test_vaultlab_figures/test_recipe_<recipe_name>.py` — must pass
6. Run `vaultlab claude validate` — must pass
7. Open PR

### Add an agent role

1. Copy `templates/role/` to `src/vaultlab/roles/<role_name>/`
2. Fill in `role.py` (thin loader; ~15 lines) and `prompt.md` (the actual prompt — be opinionated, include anti-laziness rules)
3. Register the role in `src/vaultlab/roles/__init__.py`
4. Add to `tests/test_vaultlab/test_role_invariants.py` so role-mode consistency is tested
5. Run `pytest tests/test_vaultlab/test_role_invariants.py` — must pass

### Add a slash command

1. Copy `templates/slash_command/` to `.claude/commands/<command-name>.md`
2. Fill in: description, inputs, outputs, implementation (Python imports), test plan
3. Run `vaultlab claude validate` — must pass
4. Run a smoke test: invoke the command in Claude Code on a tiny test project
5. Update `docs/slash_commands.md` if the command is user-facing

## Development workflow

### Setup

```bash
git clone https://github.com/bobbyni819/vaultlab && cd vaultlab
python -m venv .venv && source .venv/bin/activate    # on Windows: .venv\Scripts\activate
pip install -e ".[dev,all]"
pre-commit install
```

### Testing

```bash
pytest tests/                              # all tests (CI: -m "not llm")
pytest tests/test_vaultlab_<package>/      # one subpackage
pytest --cov=vaultlab tests/               # with coverage
pytest -m "not slow and not llm"           # quick run during dev
```

### Linting + type-checking

```bash
ruff check src/ tests/              # lint
ruff format src/ tests/             # format
mypy src/vaultlab                   # strict type-check on public API
```

### Pre-commit hooks

Pre-commit runs ruff, ruff-format, mypy, and basic checks (no debug statements, no large files). Configure with `pre-commit install`.

## DCO sign-off

Contributions require a DCO sign-off. This is a one-line statement that you have the right to contribute the code. Sign off with:

```bash
git commit -s -m "your commit message"
```

This adds a `Signed-off-by: Your Name <email@example.com>` footer to your commit. CI checks for this on every PR.

If you forget, amend with: `git commit --amend -s --no-edit && git push --force-with-lease`.

## Pull request checklist

- [ ] Issue opened first (for non-trivial changes)
- [ ] Branch from `main`
- [ ] Tests pass: `pytest -m "not llm"`
- [ ] Linting passes: `ruff check src/ tests/`
- [ ] Type-checking passes: `mypy src/vaultlab`
- [ ] Slash commands validated: `vaultlab claude validate`
- [ ] DCO signed: every commit has `Signed-off-by:`
- [ ] AGENTS.md invariants preserved
- [ ] Docs updated if user-facing
- [ ] CHANGELOG.md updated (if applicable)

## License

By contributing, you agree your code is released under the [MIT License](LICENSE).

## Questions

- Use [GitHub Discussions](https://github.com/bobbyni819/vaultlab/discussions) for questions
- Use [GitHub Issues](https://github.com/bobbyni819/vaultlab/issues) for bugs and features
- Use the maintainer's email (in profile) for security issues only
