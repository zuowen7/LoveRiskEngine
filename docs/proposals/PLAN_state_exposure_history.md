# Implementation Plan — State/Exposure Change History

> Status: **implemented 2026-08-31, test-first per §9 — four-gate green,
> 233 tests, coverage 98.8%, `cli.py` / `core/history.py` / `core/timeline.py`
> all at 100%. The contract below is kept verbatim as the record of what was
> built.**
> Scope beyond this document is out — new detectors, backfills or UI belong to
> their own proposals. Test-first throughout: every behaviour below gets a
> failing test before its implementation.

## 1. Scope boundary

| In scope | Out of scope (do NOT build) |
|---|---|
| `state_history` + `exposure_history` tables (schema v3, versioned migration) | Backfilling history for pre-v3 data (impossible — upsert destroyed the past; stated honestly) |
| Snapshot-on-change recording in `upsert_state` / `upsert_exposure` | The "exposure grew while evidence didn't" *detector* — next slice; this slice only makes it possible |
| `lre history <rel>` command (merged state+exposure change log with deltas) | Counterfactual review, TUI, any scoring formula |
| Timeline integration (`[state]` / `[exposure]` events with deltas) | Deleting or pruning history rows |

## 2. Semantics (exact rules)

1. **Snapshot, not delta.** Each history row stores the full new values; deltas
   are computed at read time by comparing consecutive rows of the same series.
2. **Record on change, never on no-op.** `upsert_*` reads the current row,
   applies the upsert, and records history **only when the previous row is
   absent (baseline) or differs** (compared post-clamp). `lre state set` /
   `lre exposure set` with unchanged values write nothing to history.
3. **Baseline rows are recorded.** The first-ever write of each series is a
   baseline snapshot — history is complete from the first change after
   migration, never half-complete.
4. **Atomic.** The upsert and its history row commit together (single implicit
   transaction; `_commit()` is the only commit).
5. **No history for blocked writes.** The cooldown gate refuses `exposure set`
   before `upsert_exposure` runs, so a blocked action leaves no trace.
6. **IDs** follow house style: `SH001…` (state history), `EH001…` (exposure
   history), via `_next_id` with the allow-list extended.

## 3. Schema v3

```sql
CREATE TABLE IF NOT EXISTS state_history (
    id              TEXT PRIMARY KEY,
    relationship_id  TEXT NOT NULL,
    timestamp        TEXT NOT NULL,
    attraction       REAL NOT NULL,
    trust            REAL NOT NULL,
    uncertainty      REAL NOT NULL,
    emotional_state  TEXT NOT NULL,
    FOREIGN KEY (relationship_id) REFERENCES relationships(id)
);

CREATE TABLE IF NOT EXISTS exposure_history (
    id              TEXT PRIMARY KEY,
    relationship_id  TEXT NOT NULL,
    timestamp        TEXT NOT NULL,
    time             REAL NOT NULL,
    emotional        REAL NOT NULL,
    privacy          REAL NOT NULL,
    financial        REAL NOT NULL,
    life_decision    REAL NOT NULL,
    FOREIGN KEY (relationship_id) REFERENCES relationships(id)
);
```

`SCHEMA_VERSION` → 3; `_migrate_v2_to_v3` creates both tables
(`CREATE TABLE IF NOT EXISTS` — no backfill, documented in the migration
docstring); `_migrate` gains `if version < 3`.

## 4. Domain: `core/history.py`

```python
@dataclass(frozen=True)
class StateChange:
    id: str
    relationship_id: str
    timestamp: str
    attraction: float
    trust: float
    uncertainty: float
    emotional_state: str

@dataclass(frozen=True)
class ExposureChange:   # same shape for the five axes
    ...

def describe_state_change(prev: StateChange | None, curr: StateChange) -> str
def describe_exposure_change(prev: ExposureChange | None, curr: ExposureChange) -> str
```

Exact formats (tests pin them; all floats `:.1f`):

- state baseline (`prev is None`):
  `baseline: attraction 7.5, trust 4.0, uncertainty 2.0, emotional ANXIOUS`
- state delta (only changed fields):
  `attraction 7.5 -> 8.5, trust 4.0 -> 5.0` · emotional:
  `emotional CALM -> TENSE`
- exposure baseline:
  `baseline: total 3.0 (time 1.0, emotional 2.0, privacy 0.0, financial 0.0, life_decision 0.0)`
- exposure delta (changed axes only):
  `total 3.0 -> 5.0 (time 1.0 -> 3.0)`

## 5. Storage (`storage/database.py`)

- `_ALLOWED_IDENTIFIERS` += `("state_history", "id")`, `("exposure_history", "id")`.
- `upsert_state` / `upsert_exposure`: read previous → upsert → record history
  per §2 (previous fetched *before* the write; comparison post-clamp).
- `list_state_history(relationship_id) -> list[StateChange]` and
  `list_exposure_history(relationship_id) -> list[ExposureChange]`, ordered by
  `timestamp, id`, returning domain objects (house rule: no raw rows leave
  `storage/`).

## 6. Timeline integration (`core/timeline.py`)

- `build_timeline` gains two keyword params with `None` defaults (normalized to
  `[]` inside — the eight existing positional call sites stay untouched):
  `state_changes: list[StateChange] | None = None`,
  `exposure_changes: list[ExposureChange] | None = None`.
- Events: kind `"state"` / `"exposure"`, label
  `f"{id} STATE {describe_state_change(prev, curr)}"` (baseline rows show the
  `baseline:` form). Consecutive pairing within each series, sorted by
  `(timestamp, id)`.
- Module docstring honesty note updated: history exists from schema v3 onward;
  the pre-v3 past left no trace.

## 7. CLI

- **New command `lre history <rel>`** — merge both series, sort by
  `(timestamp, id)`, one line per row:

  ```
  History for R001:
  2026-08-30T12:00  [STATE]    SH001 attraction 7.5 -> 8.5, trust 4.0 -> 5.0
  2026-08-31T09:00  [EXPOSURE] EH001 total 3.0 -> 5.0 (time 1.0 -> 3.0)
  ```

  Empty: `No state or exposure changes recorded yet.`
- `lre timeline <rel>` passes the two new lists to `build_timeline` (only
  caller change).

## 8. TDD test list (written first, red, then green)

`tests/test_history.py` (new):

1. `test_upsert_state_records_baseline_on_first_write`
2. `test_upsert_state_records_changed_values` (second write → 2 rows)
3. `test_upsert_state_skips_unchanged_write` (identical write → still 2 rows)
4. `test_upsert_state_history_holds_clamped_values` (attraction=99 → 10.0)
5. `test_upsert_exposure_records_baseline_and_change`
6. `test_upsert_exposure_skips_unchanged_write`
7. `test_list_state_history_returns_ordered_domain_objects`
8. `test_list_exposure_history_returns_ordered_domain_objects`
9. `test_history_ids_are_sequential` (SH001, SH002; EH001…)
10. `test_describe_state_change_baseline_and_delta` (exact strings)
11. `test_describe_exposure_change_baseline_and_delta` (exact strings)

`tests/test_migration.py`:

12. `test_v2_database_gains_history_tables` (user_version=2 → 3; both tables
    exist; fresh DBs still stamp `SCHEMA_VERSION`)

`tests/test_timeline.py`:

13. `test_state_and_exposure_events_appear_with_deltas` (constructed rows →
    `[state]` / `[exposure]` labels with `->` text)
14. `test_timeline_baseline_rows_marked` (first row of each series shows
    `baseline:`)

`tests/test_cli_commands.py`:

15. `test_history_command_lists_changes_with_deltas`
16. `test_history_command_reports_empty`
17. `test_timeline_includes_state_and_exposure_events` (real CLI flow)

## 9. TDD order (mechanical)

1. Write tests 1–17 → `pytest` → **red**.
2. `core/history.py` → unit tests green.
3. `storage/schema.py` + `_migrate_v2_to_v3` + upsert/list changes → storage +
   migration tests green.
4. `core/timeline.py` + `cli.py` (`lre history`, timeline caller) → remaining
   tests green.
5. Full four-gate + coverage (floor 95%, `cli.py` 100%).
6. Docs: `overview.md` (built-list + roadmap item 1 checked off), `README.md`
   (`lre history` usage), this plan marked implemented.

## 10. Non-goals (restated so the diff cannot drift)

- No rapid-escalation detector (it gets its own slice on top of this log).
- No backfill, no data rewrite, no history pruning/deletion.
- No new runtime dependency; no scoring; no TUI.

## 11. Gate checklist

- [ ] `ruff check .` clean, `ruff format --check .` clean
- [ ] `mypy love_risk_engine` clean
- [ ] `pytest` green; coverage ≥ 95% via the CI command; `cli.py` 100%
- [ ] Time via `core.timeutil` only; writes committed via `_commit()`
- [ ] History rows never deleted; blocked writes leave no trace
