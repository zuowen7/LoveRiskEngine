# Implementation Plan — Nested Transaction Integrity

> Status: **implemented 2026-09-01, test-first; full four-gate green.**

## 1. Defect and invariant

Before this repair, `Database.transaction()` committed whenever any successful
context exited. A successful inner context therefore committed the SQLite
transaction owned by its outer context, so a later outer failure could not
restore atomicity.

The corrected invariant is:

> A `Database.transaction()` scope owns exactly one transaction boundary.
> The outer scope owns SQLite `BEGIN`/commit/rollback; each nested scope owns
> one uniquely named SQLite savepoint. No successful nested exit may commit
> the outer transaction.

## 2. Chosen semantics

1. The outermost scope explicitly executes `BEGIN`. It commits only after its
   body and all nested scopes succeed; any escaping `BaseException` rolls it
   back.
2. Each nested scope creates a unique, engine-owned `SAVEPOINT`. Success
   releases only that savepoint. Failure rolls back to and then releases only
   that savepoint.
3. If a nested failure is caught by the outer body, outer work before and after
   the failed nested scope may still commit. If it propagates, the outer scope
   rolls back everything.
4. Entering an outer scope while the connection already has an unmanaged
   transaction is rejected. The engine never silently adopts or commits a
   transaction whose boundary it did not create.
5. Cleanup covers `BaseException`, not only `Exception`, and transaction depth
   is restored in `finally` paths even when SQLite cleanup itself fails.
6. If committing the outer scope fails, the connection is rolled back before
   the commit error is re-raised. A failed commit cannot leave a live partial
   transaction behind.
7. Existing write helpers continue to call `_commit()`, which remains a no-op
   at every positive transaction depth.

The yielded raw `sqlite3.Connection` is for SQL execution only. Calling its
`commit()` or `rollback()` inside a managed scope is outside the contract
because no context manager can undo a commit already forced by its caller.

## 3. Test matrix

The regression suite must prove:

- single-scope success commits and single-scope failure rolls back;
- nested success followed by outer failure persists nothing;
- nested and outer success persist everything;
- a propagated inner failure rolls back the complete outer unit;
- a caught inner failure rolls back only the savepoint while preserving valid
  outer work;
- three-level nesting observes the same savepoint isolation;
- a `BaseException` rolls back and restores depth;
- a commit-time failure rolls back and restores depth;
- an unmanaged existing transaction is rejected without changing its data or
  engine depth;
- savepoint creation or cleanup failures poison the outer scope and prevent
  later work from being committed through a lost boundary;
- a nested storage method such as `import_observations()` cannot prematurely
  commit its caller's outer transaction.

The original unconditional nested commit must be demonstrated red before the
implementation changes.

## 4. Scope and constraints

- No schema, migration, export format, network surface, PII field, or runtime
  dependency changes.
- The implementation remains in `storage/database.py` and uses stdlib
  `sqlite3` only.
- `docs/ARCHITECTURE_AND_PLAN.md`, ADR-0004, the live audit register and this
  plan define the transaction contract together.
- The slice finishes only after Ruff lint, Ruff format, mypy and the full
  branch-coverage pytest suite pass.
