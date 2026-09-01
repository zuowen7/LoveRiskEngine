# ADR-0002: Layered architecture and core purity

- **Status:** Accepted
- **Date:** 2026-08-15
- **Decides:** The package is a strict four-layer stack
  `core → storage → services → cli`; a lower layer may never import a
  higher one.

## Context

A relationship decision-support engine has four genuinely different
concerns: the domain logic (what counts as evidence, how cooldowns
decay, what a contradiction is), the persistence (how observations are
stored and queried), the orchestration (how a review composes the
detectors), and the presentation (argv parsing, stdout formatting,
i18n chrome). The temptation in a solo project is to let these bleed
together — one file reaches down for a DB row, another reaches up for a
printer — because there is no reviewer to catch it.

Once the bleed happens, the layers stop being swappable. core/ stops
being unit-testable without a DB harness. services/ stops being callable
from a non-CLI caller (a future GUI, a library import, a test). The
adapter boundary that protects the domain from a persistence choice
collapses, and every refactor thereafter pays for it.

The alternatives:

1. **Unenforced convention.** Document the layers in
   `ARCHITECTURE_AND_PLAN.md` and trust review. For a solo developer
   there is no review; convention without enforcement is a wish.
2. **Enforce with a linter plugin.** Import-linting tools exist but add
   a runtime/CI dependency the project forbids (ADR-0001).
3. **Enforce with an AST invariant test.** No new dependency; the guard
   runs in the existing pytest suite; drift fails the build.

## Decision

- Four layers, ordered `core → storage → services → cli`. A "higher"
  layer (later in the arrow) may import any layer at or before it; a
  "lower" layer may never import a higher one.
- `core/` is pure domain: it imports no `storage`, `services`, or `cli`
  module, directly or via relative imports or the `from package import
  name` alias escape hatch.
- `storage/` imports `core/` only — never `services/` or `cli/`. The
  persistence adapter is a dumb sink, not an orchestrator.
- `services/` imports `core/` and `storage/` only — never `cli/`.
  Orchestrating a review must not couple to argv parsing or stdout
  formatting.
- `cli/` is the top of the stack and may import anything below it.

## Consequences

**We get:** `core/` is unit-testable with no DB and no CLI harness.
`services/` is callable from any future frontend (GUI, library, test)
without dragging the CLI along. The adapter boundary protects the domain
from a future persistence swap (a different DB, an in-memory store).

**We pay:** orchestration that genuinely needs persistence must go
through `storage/` rather than reaching for a DB row directly, which is
one extra indirection. New domain concepts must land in `core/` even
when a storage caller would make the first cut easier.

## Enforcement

`tests/test_invariants.py` enforces every forbidden pair in the matrix
with an AST scan:

- `test_core_does_not_import_storage_services_cli`
- `test_storage_does_not_import_services_or_cli`
- `test_services_does_not_import_cli`

Relative imports are resolved to absolute paths before matching, and
the alias escape hatch (`from love_risk_engine import cli`) is caught.
The scanner itself is proven to fire by
`test_scanner_actually_catches_a_forbidden_import` — a guard that
cannot fail is decoration, so the meta-guard injects a forbidden import
into a temp dir and asserts every import shape is reported.
