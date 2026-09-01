# Implementation Plan — Promise Re-promise Counting

> Status: **implemented 2026-09-01, test-first per §5 — four-gate green,
> 314 tests, coverage 98.9%. The contract below is kept verbatim as the
> record of what was built.**
> Scope beyond this document is out. Test-first throughout.

## 1. Scope boundary

| In scope | Out of scope |
|---|---|
| New detector `repeated_repromises` in `core/promises.py` | Changing `promise_expiry` semantics |
| Enabled for the three windowed kinds (BOSS / MENTOR / COLLEAGUE) | Any new CLI command — it flows through `status` / `review` like every hook |
| Aggregated finding (all re-promised attributes in one warning) | Per-attribute findings |
| Lookback = the kind's promise window (uncalibrated placeholder) | A separate lookback parameter |

## 2. Semantics (exact rules)

1. For each normalized attribute, count **distinct observations** whose claim
   value is future-directed (`is_future_directed`) **and** whose timestamp is
   inside the lookback window (`now − promise_window_days`).
2. Fire when `count >= REPROMISE_THRESHOLD = 3` (uncalibrated placeholder,
   documented as such).
3. One aggregated `BiasFinding` (`repeated_repromises`, severity 2, WAIT) when
   any attribute fires; details capped at 3 attributes, the rest collapsed
   into a count. Message states the window, each attribute's count, latest
   value and observation id — fully auditable.
4. `window_days is None` → no finding (defensive; only windowed kinds enable
   the hook). Un-datable rows fail open (skipped).

Message shape (pinned by tests):

```
3 promise re-mention(s) within 90 days: funding x3 (latest: 'will fund', obs O003)
```

## 3. Implementation

- `core/promises.py`: `REPROMISE_THRESHOLD = 3`, `Repromise` frozen dataclass,
  `collect_repromises(observations, window_days, now=None) -> list[Repromise]`,
  `detect_repeated_repromises(...) -> BiasFinding | None`.
- `core/profiles.py`: windowed kinds gain `"repeated_repromises"` in
  `enabled_hooks`; non-windowed kinds unchanged.
- `core/hooks.py`: dispatch after `promise_expiry`.
- No CLI/storage/schema changes.

## 4. TDD test list (written first, red, then green)

`tests/test_promises.py` additions:

1. `test_collect_repromises_counts_repeated_future_mentions` (3 mentions → 3)
2. `test_collect_repromises_ignores_non_future_mentions`
3. `test_collect_repromises_ignores_mentions_outside_window`
4. `test_collect_repromises_empty_without_window`
5. `test_detect_repeated_repromises_fires_wait_with_details` (count/window/
   value/obs id in message)
6. `test_detect_repeated_repromises_silent_below_threshold` (2 mentions)
7. `test_detect_repeated_repromises_none_without_window`

`tests/test_profiles.py`:

8. windowed kinds include `repeated_repromises`; others do not

`tests/test_cli_commands.py`:

9. `test_review_fires_repeated_repromises_for_mentor` (three recent future
   claims via `_patch_clock`; rule id in review output)
10. `test_review_does_not_fire_repeated_repromises_for_lover`

## 5. TDD order

1. Write tests 1–10 → red.
2. `core/promises.py` additions → unit green.
3. Profiles + hooks wiring → CLI green.
4. Full four-gate + coverage; mark this plan implemented; register note in
   `AUDIT_REPORT.md` (S2 limitation resolved).
