Audit a codebase for shallow vs deep modules and propose refactoring toward deep modules with simple interfaces. Inspired by John Ousterhout's "A Philosophy of Software Design" and Matt Pocock's "Claude Code for real engineers" talk.

The point: AI (and humans) reason much better about codebases organized into a few large modules with clean interfaces than about codebases sprawling across many small shallow modules. Better architecture = better AI output.

## When to use

- A file has grown beyond ~1000 lines and reasoning about it has become hard
- AI keeps making mistakes that suggest it's not finding the right module
- A new feature would touch 10+ files in a way that suggests poor boundaries
- Bobby explicitly invokes `/improve-architecture <file or dir>`
- Before adding a major new feature to a complex existing module

## Definitions

- **Deep module** — lots of functionality hidden behind a simple interface. You can use it without reading its internals.
- **Shallow module** — small amount of functionality with a complex interface. You have to read the implementation to use it.
- **Good architecture** — few deep modules with stable interfaces, lots of internal complexity hidden.
- **Bad architecture** — many shallow modules, internals leak through interfaces, callers need to know implementation details.

## Step 1: Survey

Identify the target. Either:
- A specific file or directory Bobby points to
- The largest file in the project (find it with `wc -l` on all source files)
- A module that came up as problematic in a recent session

Scan for shallow-module symptoms:
- Files <100 lines that are imported in only 1-2 places
- Helper modules whose only purpose is to be called by one other file
- Functions whose docstrings describe their internals rather than their purpose
- Many small classes that always travel together
- A 2000+ line file that lives in one function (`create_app`, `__init__`, `main`)
- Long parameter lists where most params come from the same source

## Step 2: Identify the natural boundaries

Walk the code and list:

1. **Cohesive groups** — sets of functions/classes that are about the same thing (camera management, motion detection, alerts, recording). These want to be deep modules.
2. **Crossing concerns** — code that touches many groups (logging, config loading, error handling). These often signal missing abstractions.
3. **Hidden dependencies** — places where module A imports B, but B's surface doesn't say it depends on A's data. These need explicit interfaces.
4. **Callers** — for each candidate boundary, list everything that uses it. Few callers = ready for refactor; many callers = define the interface carefully.

## Step 3: Propose deep modules

For each cohesive group, draft:

```markdown
### Module: <name>

**Purpose:** One sentence. What does this hide from callers?

**Interface (public surface):**
- `function_a(...) -> X` — what it does
- `function_b(...) -> Y` — what it does

**Internals (hidden):**
- All the implementation details, helpers, constants

**Callers:**
- Files that use this module
- What they actually need from it (helps refine the interface)
```

A good interface:
- 3-7 public functions/classes (any more = probably two modules)
- No leaking implementation types in signatures
- Documented in terms of WHAT, not HOW
- Stable across reasonable changes to internals

A bad interface:
- 30 public functions with overlapping concerns
- Returns raw dicts that callers have to know the shape of
- Documented as "calls _internal_helper which does X"

## Step 4: Plan the refactor

Order changes from least- to most-disruptive:

1. **Extract** — pull cohesive code out of giant files into new modules
2. **Encapsulate** — wrap loose helpers behind a single public function
3. **Hide** — make currently-public things private (`_underscore` prefix in Python)
4. **Replace** — swap callers from old surface to new interface, one at a time
5. **Delete** — remove the now-unused old code

Show Bobby the plan BEFORE touching code. Each refactor step should be small enough to ship and test independently.

## Step 5: Execute one step at a time

For each step:
- Make the change
- Run the relevant tests
- If green, commit with a clear message (`Extract <module> from <file>`)
- If red, stop and investigate before continuing

Do NOT batch a 12-step refactor into one giant commit.

## Specific targets in bobby-tools

Two files are well-known shallow-architecture problems:

| File | Lines | Issue |
|------|-------|-------|
| `src/bobby_home/stream.py` | ~2,400 | All Flask routes inline in `create_app()` factory |
| `src/bobby_dashboard/_api.py` | ~3,500 | All routes inline, no Blueprints |

Both should be split into Flask Blueprints organized by domain (motion, recording, alerts, sessions, terminals, auth, etc.). The architecture review at `docs/plans/2026-04-17-dashboard-state-bleed-analysis.md` and the bobby_home review (in conversation history) both recommend this.

## Anti-patterns

- Refactoring without tests in place
- Renaming things just to rename them (it's not a refactor)
- Making interfaces "flexible" (more options = more shallow)
- Premature abstraction — wait until you have 3 examples of a pattern before extracting it
- Big-bang rewrites — always do small steps with passing tests between

## Deliverable

End the skill run with:

1. List of identified shallow modules and proposed deep modules
2. Ordered refactor plan
3. Estimated effort (in commits, not hours)
4. The first concrete commit to make if Bobby green-lights it
