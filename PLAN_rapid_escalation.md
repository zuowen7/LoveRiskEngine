# Implementation Plan — Rapid Exposure Escalation Detector

> Status: **implemented 2026-08-31, test-first per §6 — four-gate green,
> 248 tests, coverage 98.8%, `cli.py` / `core/escalation.py` both 100%.
> The contract below is kept verbatim as the record of what was built.**
> Scope beyond this document is out. Test-first: every behaviour below gets a
> failing test before its implementation.

## 1. Scope boundary

| In scope | Out of scope (do NOT build) |
|---|---|
| One detector: `rapid_exposure_escalation`, universal across all kinds | Any other new detector (counterfactual review, mutual verification) |
| Consumes the existing `exposure_history` log + observation timestamps | Schema changes, new tables, config files, scoring |
| `ReviewContext` gains `exposure_history` (single construction site) | TUI, reply coaching, numeric indices |

## 2. Semantics (exact rules)

The roadmap's wording is the spec: **"exposure grew 3 points in 2 days while
evidence grew 0"**.

1. **Window**: `RAPID_EXPOSURE_WINDOW_DAYS = 2` (uncalibrated placeholder,
   documented as such).
2. **Growth**: total exposure increased by ≥ `RAPID_EXPOSURE_INCREASE = 3.0`
   within the window.
3. **Baseline carry-forward**: the baseline is the *latest* exposure snapshot
   with `timestamp ≤ now − window`. If none exists (the series started inside
   the window), the earliest snapshot overall is the baseline. Empty history →
   no fire. A single-row history → delta 0 → no fire.
4. **Recency**: the latest snapshot must be inside the window — growth that
   happened entirely before the window is history, not escalation.
5. **Evidence**: *any* observation with `timestamp > now − window` means
   evidence grew → no fire. Zero new observations in the window is the other
   half of the pairing.
6. **Fail open**: unparseable timestamps are skipped (never crash, never flag
   on un-datable rows); unparseable `now` → no fire.
7. **Output**: `BiasFinding("rapid_exposure_escalation", …)` severity 3,
   proposing **PAUSE** (the speed impairs judgement — pause before more
   exposure, same rationale as love-bombing). Never a conviction.

Exact message (tests pin it):

```
Exposure grew 5.0 points in the last 2 days (3.0 -> 8.0) with no new
observations recorded in that window.
```

## 3. New module `core/escalation.py`

```python
RAPID_EXPOSURE_WINDOW_DAYS = 2   # uncalibrated placeholder
RAPID_EXPOSURE_INCREASE = 3.0    # uncalibrated placeholder

def detect_rapid_exposure_escalation(
    exposure_history: list[ExposureChange],
    observations: list[Observation],
    now: str | None = None,
) -> BiasFinding | None
```

Time handling via `core.timeutil` only (`utc_now_iso`, `parse_iso`); window
arithmetic with `datetime.timedelta` locally — no direct `datetime.now()`.

## 4. Wiring

- `core/hooks.py`: `ReviewContext` gains a required
  `exposure_history: list[ExposureChange]` field; `run_hooks` runs the detector
  when `"rapid_exposure_escalation" in hooks` (after the v1 six, before
  `promise_expiry`).
- `services/review.py::build_context`: loads
  `db.list_exposure_history(relationship_id)` (the only `ReviewContext`
  construction site).
- `core/profiles.py`: new `_HOOKS_COMMON = _HOOKS_V1 +
  ("rapid_exposure_escalation",)`; **all seven kinds** use it (this rule is
  orthogonal to relationship kind). Windowed kinds keep their
  `+ ("promise_expiry",)`.
- No CLI surface change: the warning flows through `status` / `review`
  automatically, like every other hook.

## 5. TDD test list (written first, red, then green)

`tests/test_escalation.py` (new; fixed `now`, hand-built rows):

1. `test_fires_when_exposure_grew_in_window_without_observations`
   (rows at −3d total 2.0 / −1d total 5.5; no obs → fires, PAUSE)
2. `test_silent_when_an_observation_exists_in_window` (evidence grew)
3. `test_silent_when_growth_below_threshold` (+2.0)
4. `test_silent_when_growth_predates_window` (latest row older than 2d)
5. `test_silent_without_exposure_history` (empty list)
6. `test_series_started_inside_window_uses_earliest_row_as_baseline`
   (rows at −1d 0.0 / −0.5d 5.0 → fires)
7. `test_baseline_is_latest_snapshot_at_or_before_cutoff`
   (rows at −3d 0.0 / −2.5d 0.5 / −1d 5.0 → delta 4.5 → fires)
8. `test_fails_open_on_malformed_timestamps` (garbage row ignored, no crash)
9. `test_message_states_window_delta_and_evidence` (exact string, `:.1f`)

`tests/test_profiles.py`:

10. `test_all_kinds_run_rapid_escalation`
11. update `test_lover_profile_pins_todays_behavior` (six v1 hooks remain a
    subset; `rapid_exposure_escalation` present; window still None)

`tests/test_cli_commands.py`:

12. `test_status_warns_on_rapid_exposure_without_evidence` (two real
    `exposure set` writes → warning line in `status`)
13. `test_review_fires_rapid_exposure_escalation` (in triggered hooks)

## 6. TDD order (mechanical)

1. Write tests 1–13 → `pytest` → **red**.
2. `core/escalation.py` → unit tests green.
3. Profiles + hooks + build_context wiring → CLI tests green.
4. Full four-gate + coverage (floor 95%, `cli.py` 100%).
5. Docs: `overview.md` (built-list + roadmap note), `README.md` detector
   table row, this plan marked implemented.

## 7. Non-goals (restated so the diff cannot drift)

- No threshold tuning UI; constants stay code-frozen placeholders.
- No other detectors; no schema change; no new command.
- No scoring, no reply coaching, no auto-conviction (PAUSE only).

## 8. Gate checklist

- [ ] `ruff check .` / `ruff format --check .` / `mypy love_risk_engine` clean
- [ ] `pytest` green; coverage ≥ 95%; `cli.py` 100%
- [ ] Time via `core.timeutil`; warning text carries window + delta + baseline
