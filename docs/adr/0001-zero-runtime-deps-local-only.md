# ADR-0001: Zero runtime dependencies, local-only

- **Status:** Accepted
- **Date:** 2026-08-15
- **Decides:** The shipped package depends on the Python standard library
  only; no outbound network call, no surveillance, no new PII fields.

## Context

LoveRiskEngine handles intimate relationship data — observations about
people the user knows personally. That makes the trust bar brutal: any
network dependency, however convenient, is an exfiltration surface the
user cannot audit. The same applies to PII: a "helpful" field capturing
a contact's real name or handle turns the local store into a dossier, and
dossiers get leaked.

The alternatives on the table were:

1. **Use rich/pandas/requests for convenience.** Faster to build, but
   every transitive dependency becomes a supply-chain liability, and
   `requests` in particular is an open network door.
2. **Allow network for "optional" features** (telemetry, update checks,
   cloud sync). Each opt-in is a default the user has to remember to
   turn off; defaults that leak are worse than no feature.
3. **Zero runtime deps, local-only.** Slower to build (we reimplement
   what a library would give us), but the trust story is one sentence
   and the audit surface is the repo itself.

The project exists to be a decision-support tool that a user can run on
a disconnected machine and trust by inspection. Anything that erodes that
erodes the whole point.

## Decision

- Shipped code under `love_risk_engine/` depends on the Python standard
  library only. No `requests`, `httpx`, `aiohttp`, `socket`, `urllib`,
  `smtplib`, `ftplib`, `telnetlib`, or any third-party runtime package.
- Optional presentation dependencies (e.g. `rich`) are soft-imported
  with a plain-text fallback, so their absence never breaks the CLI.
- No outbound network call is made by any code path. Local-only is the
  contract, not a setting.
- No new PII field is added without amending this ADR and the canonical
  architecture doc.

## Consequences

**We get:** a trust story a user can verify by reading `pyproject.toml`
and grepping for network imports. A reproducible install. A tool that
runs offline.

**We pay:** we reimplement things a library would give us for free
(ISO-8601 parsing, ANSI color, table formatting). Adding a genuinely
useful runtime dep now requires an ADR amending this one — the friction
is deliberate.

## Enforcement

- `tests/test_invariants.py::test_package_has_no_network_imports` — AST
  scan of every module under `love_risk_engine/` against a denylist of
  network roots. Adding a network import fails the build, not the review.
- `pyproject.toml` `dependencies` field stays empty; `pre-commit` and
  dev tools are isolated to the `dev` extra so end users never see them.
- `AGENTS.md` "Engineering Contracts" section restates the contract for
  contributors.
