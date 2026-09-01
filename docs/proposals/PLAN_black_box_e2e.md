# Implementation Plan — Installed-CLI Black-Box E2E

> Status: **implemented locally 2026-09-01; cross-platform CI run pending push.**

## 1. Boundary under test

The existing command suite calls `main(argv)` in-process. That is the correct
layer for branch attribution and precise handler failures, but it cannot prove
that the packaged console entry point imports, that independent processes see
the same SQLite state, or that process exit codes match command outcomes.

The E2E boundary is therefore:

> `subprocess` → non-editably installed `lre` console script → real command
> handlers → one temporary SQLite file → captured stdout/stderr/exit code →
> direct read-only SQLite inspection.

E2E tests import no `love_risk_engine` module and use no mocks. Standard-library
`sqlite3` is an external observer, never a shortcut into application storage.

## 2. Deterministic harness

Each journey gets its own `tmp_path` and absolute `LRE_DB_PATH`. The subprocess
environment pins English, UTF-8 and non-colour output, removes `PYTHONPATH`, and
runs from the temporary directory. Every invocation captures stdout and stderr,
has a bounded timeout, and asserts its expected exit code.

The runner must resolve a real installed `lre` executable and fail if none is
available. It must never fall back to `python -m love_risk_engine.cli`, because
that would bypass the packaging boundary this layer exists to test.

Assertions use stable semantic fragments and parsed IDs. Full stdout snapshots
are forbidden because timestamps, temporary paths, checksums and cooldown
remaining time are intentionally variable.

## 3. Exit-code contract

- `0`: the requested operation completed.
- `1`: a valid command was rejected or failed at the domain/runtime boundary.
- `2`: argparse rejected invalid syntax or arguments.

The cooldown guard currently prints `BLOCKED` but returns `0`. This slice must
make that rejected exposure write return `1`, while preserving the detailed
stdout explanation and proving the database is unchanged.

## 4. Five independent golden journeys

1. **Fresh user:** init → relationship → observation with alternative
   explanation → state → exposure → first review → timeline/status.
2. **Risk escalation:** observation → unresolved inconsistency → recorded hard
   boundary hit → review. `EXIT` is attributed to the hard boundary; the other
   records are context, not a claimed composite cause.
3. **Cooldown/override:** establish exposure → trigger EXIT cooldown → rejected
   exposure increase → explicit override with reason → visible audit trail.
4. **Import:** generated NDJSON plus deterministic claim rules → chat import →
   persisted contradiction → future-directed promise view → merged timeline.
5. **Disaster recovery:** populate every critical table family → canonical
   direct-SQLite snapshot → export → unlink the temporary database → restore
   directly without a preceding `init` → integrity check → exact semantic
   snapshot equality and user-visible status.

Every journey starts empty; no journey depends on IDs or data created by
another.

## 5. Recovery oracle

SQLite file bytes are not canonical, and export→export comparison could allow
the exporter and restorer to share the same omission. The recovery test instead
enumerates every non-system table through `sqlite_master`, converts rows to
canonical JSON using their real column names, sorts them, and compares the
complete before/after snapshots plus `PRAGMA user_version`.

The guarantee is same-schema recovery only. Cross-version restore remains
explicitly unsupported.

## 6. CI and coverage

- Register an `e2e` pytest marker.
- Keep branch coverage on in-process/unit tests; exclude `e2e` from the
  coverage job because child-process execution is not attributed to the parent.
- Add a dedicated E2E job on Ubuntu and Windows with Python 3.12.
- The job installs pytest, performs non-editable `pip install --no-deps .`, and
  runs only `tests/e2e`.
- No retries: a flaky journey is a defect, not something CI should conceal.

## 7. Acceptance

- The five journeys pass on both CI operating systems.
- Fresh non-editable installation exposes a working `lre` command.
- Every expected success returns `0`; cooldown rejection returns `1` and leaves
  exposure unchanged.
- Recovery snapshots and schema versions are identical.
- Ruff, format, mypy and the existing branch-coverage suite remain green.
