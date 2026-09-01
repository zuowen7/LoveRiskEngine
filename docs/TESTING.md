# Testing philosophy

This is the *why* behind the test suite — `CONTRIBUTING.md` House Rules
cover the *what*. Read this before adding a test or chasing a missing
line.

## Coverage is a map, not a score

The total (98–99%) is not the point. The point is the **missing-lines
column** — that is where the next bug lives. A 99% suite with the 1% in
the wrong place (a CLI command, a return-type migration path) is more
dangerous than a 90% suite whose gaps are all in defensive branches.

Read the report as a map: `coverage report` then scan for any file
below 100% and ask "is that gap load-bearing?" The floor is 95%
(`fail_under` in `pyproject.toml`, mirrored in CI) — below that the
build fails outright. Above it, the missing lines are a review item,
not a pass.

## What we deliberately do not test

Some branches are unreachable through any real call path — the data
cannot occur, or a guard above them makes them dead. Two precedents:

- `core/evidence.py` — the zero-observation branch. `run_hooks` always
  returns at least one finding in production, so "no warnings" never
  happens.
- `core/hooks.py` — the no-hook-fired branch. Same shape.

We do **not** write contrived tests to hit these. A test that
manufactures impossible data to tick a coverage line is a test that
can teach a wrong lesson: it implies the branch is reachable. Instead,
exercise the formatting function directly as a unit test and **say so
in the docstring** (see `tests/test_database_integrity.py` for the
pattern), so nobody hunts for a CLI invocation that does not exist.

The trade is honest: we ship 98–99% instead of 100%, and the remaining
1–2% is documented defensive code, not a gap we are pretending is
covered.

## Test fakes must be able to fail

House Rule #8 (`CONTRIBUTING.md`). The `timeline` crash survived a green
suite because the test fed `build_timeline` a hand-rolled `_DictRow` that
matched neither production shape. When a function consumes something the
layer above it produces, feed it the real return value at least once:

```python
events = build_timeline([], db.list_boundary_hits(rid), [], [])
```

Fakes are for inputs you genuinely cannot construct, not for ones you
cannot be bothered to.

## Mutation guards — proving the suite can fail

Coverage proves a line ran. It does not prove the line was *checked*.
A line that runs but whose result is never asserted is covered in
number only. Mutation testing closes that gap: mutate the code, run the
suite, and if the suite still passes the mutation, the suite was not
testing that path.

Two tracks ship here:

1. **`mutmut` config** (`[tool.mutmut]` in `pyproject.toml`) for WSL/CI.
   `mutmut` does not run natively on Windows (upstream #397), so the
   config targets the safety-critical modules (`core/decision.py`,
   `core/cooldown.py`) and runs in CI.
2. **Hand-written mutation guards**
   (`tests/test_mutation_guard.py`) — seven guards that run on Windows
   with no extra dependency. Each injects a mutation (a reversed
   comparison, a dropped guard, a flipped default) via `monkeypatch` and
   asserts the observable behaviour changes. If a mutation slips through
   silently, the guard fails — proving the existing tests would have
   caught the bug.

The hand-written guards are not a substitute for `mutmut`; they are the
Windows-runnable subset that catches the highest-cost mutations
(hard-boundary bypass, priority inversion, default-flip).

## Property-based tests without a dependency

`tests/test_timeutil_properties.py` runs 200 randomized inputs per
property using the stdlib `random` with a fixed seed (`20260901`). This
is the stdlib alternative to `hypothesis` — chosen because adding
`hypothesis` as a dev dependency would widen the install surface against
ADR-0001's spirit (zero runtime deps, minimal dev surface).

The fixed seed means a failure is reproducible: if a property breaks,
the same seed regenerates the same counterexample. The trade is that
the search is shallow (200 samples, no shrinking) — fine for invariant
checks (parse-round-trips, antisymmetry) that either hold or fail
loudly, less fine for edge-finding where `hypothesis` would shine.

## The meta-guard: test the test

An invariant test that cannot fail is decoration. The pattern shows up
twice in this suite:

- `tests/test_invariants.py::test_scanner_actually_catches_a_forbidden_import`
  injects a forbidden import into a temp dir and asserts the layer
  scanner reports every import shape (direct, `from`, relative, alias
  escape hatch). This guard found a real scanner bug (double-reporting
  `from X import Y`) on its first run — the value of "test the test."
- The hand-written mutation guards (above) are the same pattern applied
  to the production suite: prove the tests fail when the code is wrong.

When you add an invariant test, add the meta-guard that proves it fires.
A guard with no failure path is a comment.

## How CLI tests run

House Rule in `CONTRIBUTING.md` "Tests" section: call `main(argv)`
in-process against `LRE_DB_PATH` in `tmp_path`. Subprocess tests lose
branch attribution (the coverage belongs to the child process, not the
suite), which is usually the opposite of why the test was written.

## Why the four gates, not just pytest

`ruff check` + `ruff format --check` + `mypy` + `pytest` are the four
gates. Each catches a different failure mode:

- **ruff check** — the bug-shaped lint findings (unused imports,
  mutable defaults, `==` on `sqlite3.Row`). House Rule #2 is the
  canonical example.
- **ruff format --check** — drift in style that makes diffs unreadable
  in review. A reformatted file shows up as a 1-line diff, not a
  200-line reformat.
- **mypy** — the return-type migrations (House Rule #7). Advisory for
  untested callers, but the only automated check that a return-type
  change is consistent across the package.
- **pytest** — behaviour. The only gate that proves the code does what
  it says.

CI runs all four on Python 3.11 / 3.12 / 3.13. A red CI should be rare
because the pre-commit + pre-push hooks re-run them before the push
leaves the machine (House Rule #9).
