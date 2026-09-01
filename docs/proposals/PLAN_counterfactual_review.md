# Implementation Plan — Counterfactual Review (RedTeamMe)

> Status: **implemented 2026-09-01, test-first per §6 — four-gate green,
> 314 tests, coverage 98.9%. The contract below is kept verbatim as the
> record of what was built.**
> Scope beyond this document is out. Test-first throughout. This slice also
> discharges audit issue E1's data-generator half: counterfactual reviews are
> the honest source of user-labeled decision outcomes for future calibration.

## 1. Scope boundary

| In scope | Out of scope |
|---|---|
| `lre counterfactual <rel>` (list) and `--review <id>` (re-run + diff) | Editing/annotating the original review; auto-anything |
| Freeze helpers for state / exposure / observations / hits / inconsistency count | Freezing *rules* — today's thresholds & profiles are applied to past evidence, stated in the output |
| One new storage read: `get_review(review_id)` | Schema changes, new tables |

## 2. Semantics (exact rules)

1. **Frozen evidence** at the review's timestamp `T`: observations with
   `timestamp ≤ T`; boundary hits `≤ T`; exposure from the latest
   `exposure_history` row `≤ T` (default 0); state from the latest
   `state_history` row `≤ T` (default NEUTRAL); unresolved-inconsistency count
   = rows with `created_at ≤ T` that are **currently** unresolved — an
   approximation, because resolutions carry no timestamp; documented in the
   module docstring and in this plan, not hidden.
2. **Recompute** with `run_hooks` + `decide` under the *current* profile and
   thresholds; compare against the review's stored recommendation.
3. **Honesty contract** (printed with every result): "today's thresholds and
   profiles are applied to past evidence; the rules may have changed since the
   original decision. This is an audit tool, not a verdict on your past self."
4. Unknown review id, or a review belonging to a different relationship →
   loud `ValueError` → CLI `sys.exit`.

## 3. Implementation

- `core/counterfactual.py` (pure): `FrozenEvidence` dataclass +
  `freeze_state / freeze_exposure / freeze_observations / freeze_boundary_hits
  / freeze_inconsistency_count`. Fail-open on un-datable timestamps
  (excluded from "before T" only when unparseable rows are ignored, never a
  crash).
- `services/counterfactual.py`: `CounterfactualResult` +
  `run_counterfactual(db, relationship_id, review_id)` — assembles the frozen
  `ReviewContext` and reruns the pipeline.
- `storage/database.py`: `get_review(review_id) -> Review | None`.
- `cli.py`: `counterfactual` command (list mode + `--review` rerun mode).

## 4. Output shape (pinned by tests)

```
Counterfactual review of RV001 (2026-08-20T10:00, original: CONTINUE_OBSERVING)
Evidence frozen at that time: 1 observation(s), 0 boundary hit(s), 0 unresolved inconsistencies
  exposure 0.0 | attraction 0.0 | trust 0.0 | uncertainty 0.0 | emotional NEUTRAL
Recomputed with today's rules: WAIT
  findings at that time: promise_expiry
Original vs recomputed: DIFFERENT
Note: today's thresholds and profiles are applied to past evidence; ...
```

## 5. TDD test list (written first, red, then green)

`tests/test_counterfactual.py` (new; unit — freeze functions):

1. `test_freeze_state_picks_latest_at_or_before`
2. `test_freeze_state_defaults_when_no_history`
3. `test_freeze_exposure_picks_latest_at_or_before`
4. `test_freeze_observations_filters_after_as_of`
5. `test_freeze_boundary_hits_filters_after_as_of`
6. `test_freeze_inconsistency_count_counts_created_before_and_still_open`

`tests/test_counterfactual.py` (service):

7. `test_run_counterfactual_recomputes_with_frozen_evidence` — state changed
   *after* the review must not leak into the frozen context
8. `test_run_counterfactual_unknown_review_raises`
9. `test_run_counterfactual_wrong_relationship_raises`

`tests/test_cli_commands.py`:

10. `test_counterfactual_lists_reviews`
11. `test_counterfactual_reruns_and_reports_difference` — review taken as
    LOVER (promise hooks off), kind switched to MENTOR afterwards → recomputed
    fires `promise_expiry` → DIFFERENT
12. `test_counterfactual_reruns_and_reports_match` — review as MENTOR →
    recomputed identical → MATCHED
13. `test_counterfactual_unknown_review_exits`

## 6. TDD order

1. Write tests 1–13 → red.
2. `core/counterfactual.py` → unit green.
3. `storage.get_review` + `services/counterfactual.py` → service green.
4. CLI wiring → CLI green.
5. Full four-gate + coverage; docs: `overview.md` roadmap #2 checked off,
   `AUDIT_REPORT.md` E1 note, `ARCHITECTURE_AND_PLAN.md` phase table, this plan
   marked implemented. Commit, push, watch CI.
