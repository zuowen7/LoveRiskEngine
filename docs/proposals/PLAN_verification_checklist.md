# Implementation Plan — Mutual Verification Checklist

> Status: **implemented 2026-09-01, test-first per §5 — four-gate green,
> 314 tests, coverage 98.9%. The contract below is kept verbatim as the
> record of what was built.**
> Scope beyond this document is out. Test-first throughout.

## 1. Scope boundary

| In scope | Out of scope |
|---|---|
| Schema v4: `verification_items` table + tested migration | Feeding verified items into evidence-support weighting (separate slice) |
| `lre verify add/list/check/fail` command group | Editing/deleting items; reminders; sharing |
| `status` shows `Verified facts: N of M` | Detector integration — the checklist is a record + display, not a hook |

## 2. Semantics (exact rules)

1. An item is a user-curated verifiable fact ("introduced me to their
   friends"). Status is three-state: `unverified` (default) → `verified` or
   `failed` (the fact turned out untrue). Confirming is always the user's
   action — the engine never auto-verifies.
2. `verified_at` is set when the status leaves `unverified`; `note` is
   user-supplied on `fail` (optional on `check`). Items are append-only:
   status transitions are allowed, deletion is not.
3. `status` prints `Verified facts: N of M` only when at least one item
   exists — this sharpens the cheap-talk/costly-signal boundary by making the
   *confirmed* costly signals visible next to the warnings.

## 3. Implementation

- `storage/schema.py`: `SCHEMA_VERSION = 4`, table DDL, `verification_items`
  appended to `TABLE_ORDER`.
- `storage/database.py`: `_migrate_v3_to_v4` (CREATE TABLE IF NOT EXISTS),
  `add_verification_item`, `set_verification_status` (allow-listed status),
  `list_verification_items`; `_ALLOWED_IDENTIFIERS` += verification_items.
- `core/verification.py` (new): `VerificationStatus` StrEnum +
  `VerificationItem` frozen dataclass.
- `cli.py`: `verify` group (add/list/check/fail) + status integration
  (`format_status` gains an optional `verification: tuple[int, int] | None`).

## 4. TDD test list (written first, red, then green)

`tests/test_verification.py` (new):

1. `test_add_item_defaults_unverified`
2. `test_check_marks_verified_with_timestamp`
3. `test_fail_marks_failed_with_note`
4. `test_set_status_unknown_item_returns_false`
5. `test_set_status_rejects_invalid_status`
6. `test_list_returns_ordered_domain_objects`

`tests/test_migration.py`:

7. `test_v3_database_gains_verification_items`

`tests/test_cli_commands.py`:

8. `test_verify_roundtrip_add_list_check_fail`
9. `test_verify_check_unknown_id_exits`
10. `test_status_shows_verified_facts_when_present`
11. `test_status_omits_verified_facts_when_absent`

(`test_export_all_tables_covers_every_table` pins the new table automatically
via `TABLE_ORDER`.)

## 5. TDD order

1. Write tests 1–11 → red.
2. Schema v4 + migration + storage → unit/migration green.
3. `core/verification.py` + CLI wiring + status line → CLI green.
4. Full four-gate + coverage; docs (`overview.md` roadmap #3 checked off,
   architecture phase table, this plan marked implemented). Commit, push,
   watch CI.
