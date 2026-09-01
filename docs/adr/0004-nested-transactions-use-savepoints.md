# ADR-0004: Nested transactions use SQLite savepoints

- **Status:** Accepted
- **Date:** 2026-09-01
- **Decides:** `Database.transaction()` explicitly owns the outer SQLite
  transaction and gives every nested scope an isolated savepoint.

## Context

The storage API promised that only the outermost transaction context commits,
but every successful context called `commit()`. A successful inner context
therefore committed all pending connection writes, including work performed by
the outer context, and a later outer rollback could not undo them.

A depth-only patch that skips the inner commit repairs that one path but leaves
the semantics of a caught inner failure undefined: rolling back the connection
would silently erase valid outer work. The alternatives were a flat
rollback-only transaction or genuine nested savepoints. The API is used for
composable storage operations, so a caller must be able to catch a failed
nested operation without losing unrelated outer work.

## Decision

- The outermost managed scope starts with explicit `BEGIN` and alone owns the
  final connection commit or rollback.
- Every nested scope creates a unique engine-generated SQLite `SAVEPOINT`.
  Success releases that savepoint; failure rolls back to it and then releases
  it.
- An inner failure that propagates still causes the outer context to roll back
  the complete unit. An inner failure caught by the outer body removes only
  inner work, after which the outer transaction may continue.
- Cleanup catches `BaseException`. Depth restoration is unconditional, and a
  failed outer commit is followed by rollback before the error is re-raised.
- An already-active SQLite transaction at outer entry is rejected rather than
  silently adopted. Callers may execute SQL on the yielded connection but may
  not directly commit or roll it back inside a managed scope.

## Consequences

**We get:** nested storage methods are composable without premature commits;
outer atomicity matches the documented contract; caught inner failures have
deterministic isolation; interruption and commit-failure paths do not leak the
engine's depth state.

**We pay:** nested scopes issue savepoint SQL, and callers with a manually
opened transaction must resolve it before entering `Database.transaction()`.
The yielded raw SQLite connection cannot technically prevent a caller from
forcing its own commit, so direct boundary control remains explicitly outside
the managed API contract.

## Enforcement

`tests/test_database_integrity.py` covers the single-level, nested-success,
propagated-failure, caught-failure, sibling and three-level, `BaseException`,
commit-failure, unmanaged-transaction, savepoint-fault and
nested-storage-method paths. The full pytest gate runs with branch coverage,
and the proposal test matrix records the semantic states that ordinary line
coverage cannot express.
