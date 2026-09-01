# Implementation Plan — Self-Consistency Audit

> Status: **implemented 2026-09-01, test-first per §7; full four-gate green.**
> This plan delivers both stages of the self-deception-risk proposal without
> claiming that software can infer a user's hidden beliefs. The feature name
> and every message use *consistency audit*, never *self-deception diagnosis*.

## 1. Product claim and safety boundary

The engine may identify inconsistencies between recorded evidence and recorded
judgments. It cannot determine whether the user is dishonest, unconscious of a
bias, or merely reconsidering older evidence.

Consequently:

1. `lre consistency <relationship> --days N` is an informational audit, not a
   review hook.
2. Audit findings never propose `WAIT`, `PAUSE`, `DECREASE_EXPOSURE`, or `EXIT`.
3. No percentage, probability, composite "self-deception score", semantic AI
   classifier, or network call is introduced.
4. Findings state the observable mismatch and a non-pathologizing alternative.
5. The default window is 30 days; `--days` must be a positive integer.

## 2. Stage 1 — audit existing evidence traces

The command produces a deterministic report for one relationship. Rules run in
the following fixed order:

| Rule id | Exact observable condition | Scope |
|---|---|---|
| `trust_change_without_new_evidence` | A consecutive state-history transition changes `trust`, while no observation timestamp or currently stored verification timestamp (`verified_at`) falls in `(previous.timestamp, current.timestamp]` | Transitions whose current snapshot is inside the requested window |
| `interpretation_without_alternative` | `interpretation.strip()` is non-empty and `alternative_explanation.strip()` is empty | Observations inside the window |
| `self_reported_rationalization_run` | At least 3 consecutive, time-ordered observations inside the window carry the user-supplied `rationalization=True` flag | Observations inside the window; threshold is uncalibrated |
| `unresolved_structured_conflicts` | One or more currently unresolved persisted inconsistencies have `kind="detected"` | Current snapshot; free-text semantic conflicts are explicitly out of scope |

An empty report is positive only in the narrow sense that no *recorded*
inconsistency matched these rules; it is never proof that the user's reasoning
is unbiased.

### Alternative-explanation input contract

The current scientific document says alternative explanations are required,
but `lre observe` accepts an empty `--alternative`. The honest invariant is:

> When an interpretation is supplied, a non-empty alternative explanation is
> required. A facts-only observation with no interpretation may omit it.

The CLI enforces this for new interactive observations. Existing rows remain
append-only and are audited by `interpretation_without_alternative`; imports
remain lossless and may expose missing alternatives rather than rewriting them.

## 3. Stage 2 — explicit criterion-direction comparison

Free text is insufficient to determine that two events were judged under the
same standard. Stage 2 therefore adds two optional fields to `Observation`:

- `criterion_key`: a user-authored stable comparison key, stored verbatim
  after trimming and normalized only during comparison;
- `judgment_direction`: `UNSPECIFIED`, `SUPPORTS_TRUST`, `WEAKENS_TRUST`, or
  `NEUTRAL`.

CLI flags are `--criterion-key KEY` and `--judgment-direction DIRECTION`.
They are both-or-neither; `UNSPECIFIED` is the legacy/storage default and is
not offered as an explicit CLI choice.

`criterion_direction_conflict` compares observations inside the requested
window. It emits candidates only when:

1. normalized non-empty `criterion_key` values match;
2. one direction is `SUPPORTS_TRUST` and the other is `WEAKENS_TRUST`;
3. at least one observation belongs to the relationship being audited.

`NEUTRAL` and `UNSPECIFIED` never form a conflict. Same-relationship and
cross-relationship pairs are both reviewable. The result says "opposite
recorded directions", not "double standard" or "self-deception"; context may
justify the difference.

## 4. Architecture and data changes

- `core/observation.py`: `JudgmentDirection` and the two optional fields.
- `core/consistency.py`: pure windowing, normalization, candidate generation,
  and stage-1/stage-2 audit rules.
- `services/consistency.py`: load domain objects, establish the UTC window,
  and assemble `ConsistencyAudit`; no logic in `cli.py`.
- `storage/schema.py`: schema v6 adds the two observation columns.
- `storage/database.py`: one v5→v6 migration, allow-listed enum validation,
  domain-object round trip, and all-observation read for cross-relationship
  comparison.
- `cli.py` / `core/i18n.py`: input validation and bilingual audit rendering.
- `core/rulespec.py` / `docs/SCIENTIFIC_FOUNDATIONS.md`: every audit rule is
  registered; all are `engineering_heuristic` and `uncalibrated`.

No new runtime dependency, network surface, PII field, or decision-engine hook
is added. Because the schema changes, canonical DDL, `SCHEMA_VERSION`, the
versioned migration, previous-version preservation test, and same-version
lossless export→restore test must change together.

## 5. Output contract

The command prints:

1. relationship id and exact UTC window;
2. findings in the fixed order from §§2–3, localized at display time;
3. if no finding fires, an explicit "no recorded consistency signal" line;
4. on every run, an honesty note: the report identifies record-level
   inconsistencies, not self-deception, intent, or truth.

Canonical English finding text remains auditable; localized text is never
persisted. The audit itself performs no write.

## 6. Failure and compatibility behavior

- Unknown relationship uses the existing loud relationship-not-found path.
- Non-positive `--days` is rejected before analysis.
- One criterion flag without the other is rejected before insertion.
- Direct storage writes reject unknown judgment directions.
- Legacy v5 rows back-fill `criterion_key=''` and
  `judgment_direction='UNSPECIFIED'`; they do not create false conflicts.
- Malformed timestamps are excluded from windowed comparisons, never treated
  as evidence inside a transition.
- Verification items expose only their latest `verified_at` transition. If an
  item changes status repeatedly, an older transition cannot be reconstructed;
  the audit therefore says "currently recorded timestamp", not "no transition
  occurred".
- Import/export preserves both new fields exactly.

## 7. TDD order and required tests

Tests were written and observed failing before business code.

### Core tests (`tests/test_consistency.py`)

1. Trust change with no evidence timestamp fires; evidence in the open/closed
   interval suppresses it; unchanged trust and out-of-window transitions do
   not fire.
2. Interpretation without alternative fires only inside the window.
3. The rationalization rule uses consecutive time order, resets on an unmarked
   observation, and states that the flags are self-reported.
4. Only unresolved structured inconsistencies are counted.
5. Criterion normalization is deterministic; opposite directions with the
   same key form a candidate; neutral/unspecified, different keys, and pairs
   unrelated to the target do not.
6. Audit ordering and the no-decision-impact invariant are pinned.

### Storage/migration/export tests

7. Both structured judgment fields round-trip through SQLite.
8. Unknown judgment directions are rejected.
9. A v5 database migrates once to v6 with observation data preserved and
   defaults back-filled.
10. Export→restore includes non-default structured judgment data losslessly.

### Service/CLI tests

11. The service assembles stage-1 and cross-relationship stage-2 findings.
12. `observe` rejects interpretation without alternative.
13. `observe` accepts facts-only input without alternative.
14. Criterion flags enforce both-or-neither and accept valid pairs.
15. `consistency` rejects non-positive days, renders findings, renders the
    empty state, and always prints the honesty note.
16. Chinese display localizes new static text and findings while domain text
    stays canonical English.

### Contract/meta-guard tests

17. Every new rule has a `RuleSpec` and a scientific-foundations table row.
18. A meta-guard proves that removing either observation column from canonical
    DDL or the v5→v6 migration fails the schema contract.
19. Full gate: `ruff check .`, `ruff format --check .`,
    `mypy love_risk_engine`, and
    `python -m pytest --cov=love_risk_engine --cov-report=term-missing` with
    branch coverage at least 95%.

## 8. Delivery sequence

1. Add this plan and amend canonical architecture/scientific contracts.
2. Add tests in §7 and run the focused set to record the expected red state.
3. Implement domain and storage behavior; make core/storage tests green.
4. Implement service and CLI behavior; make focused tests green.
5. Update bilingual user documentation and proposal status.
6. Run all four gates and perform a requirement-by-requirement completion
   audit against this document.
