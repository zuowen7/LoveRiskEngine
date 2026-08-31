<!--
LoveRiskEngine engineering gate (see CODE_QUALITY_REPORT.md). All of the
following are enforced in CI — this checklist is for the author's own sanity,
not a substitute for the green checkmark.
-->

## What & why

<!-- One paragraph: what changed and the problem it solves. Link the issue. -->

## Engineering gate (must pass in CI)

- [ ] `ruff check .` is clean (full rule set: E/W/F/I/B/C4/UP/SIM/RET/ARG/PTH/S)
- [ ] `ruff format --check .` passes
- [ ] `mypy love_risk_engine` passes (disallow_untyped_defs = true)
- [ ] `pytest` passes
- [ ] Coverage stays at or above **95%** (`coverage report --fail-under=95`)

## Domain guardrails (this is a decision-support tool, not a rating tool)

- [ ] No new PII fields added (alias + free-text only; no phone / ID / address)
- [ ] No automated conviction: a vague observation never forces a verdict
- [ ] Every score is 0–10 and clearly an *evidence indicator*, not a probability
- [ ] No surveillance of a third party; the subject is the user's own reasoning
- [ ] Local-only: no outbound network calls in the committed code path

## Notes for reviewers

<!-- Anything subtle: the reason for an exclusion, a deliberately unverified
threshold, a migration step, etc. Call out anything that looks like a shortcut. -->

## Follow-ups

<!-- Debt you knowingly left behind, with a ticket/issue if one exists. -->
