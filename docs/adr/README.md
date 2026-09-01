# Architecture Decision Records

A catalog of decisions that shape LoveRiskEngine — the load-bearing ones a
future maintainer (often: future-you) must understand before changing the
shape of the project. This is the sediment layer: proposals
(`docs/proposals/`) capture *what we plan to do*; ADRs capture *what we
decided and why it stuck*.

## When to write an ADR

Write one when a decision is:

- **Hard to reverse.** Touching a layer boundary, the zero-dependency
  contract, the local-only invariant, or the score semantics (0–10
  indicators, not probabilities).
- **Already enforced by code.** If a test or a gate makes the decision
  unbreakable, the ADR explains *why that gate exists* so nobody "fixes" the
  gate by deleting it.
- **Crosses a slice.** A decision that spans more than one
  `docs/proposals/` plan belongs here so the rationale isn't scattered
  across proposals that get archived.

Do **not** write an ADR for routine choices (which linter, indent size,
test runner). Those live in `CONTRIBUTING.md` and `pyproject.toml`.

## Format

Each ADR is a single Markdown file `NNNN-kebab-title.md`, numbered from
`0001`. Once an ADR is merged it is **immutable** — superseding it means
writing a new ADR that points back at the old one's number. We do not
rewrite history; future-you needs to see what past-you believed.

Every ADR uses this template:

```markdown
# ADR-NNNN: Title

- **Status:** Proposed | Accepted | Deprecated | Superseded by ADR-MMMM
- **Date:** YYYY-MM-DD
- **Decides:** one sentence, the decision itself

## Context

The force that produced the decision. What constraint were we under? What
alternatives were on the table? What would happen if we did nothing?

## Decision

What we chose, stated precisely enough that a reader can tell whether a
given change violates it.

## Consequences

What we get and what we pay. Name the cost honestly — every decision
trades something. If a gate now enforces this, link the gate.

## Enforcement

The specific test, hook, or doc that fails the build if the decision is
violated. "Trusted on review" is not enforcement.
```

## Index

- [0001 — Zero runtime dependencies, local-only](0001-zero-runtime-deps-local-only.md)
- [0002 — Layered architecture and core purity](0002-layered-architecture-core-purity.md)
- [0003 — Scores are evidence indicators, not probabilities](0003-scores-are-indicators-not-probabilities.md)
