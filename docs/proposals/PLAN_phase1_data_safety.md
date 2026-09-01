# Implementation Plan — Phase 1: Data Safety

> Status: **implemented 2026-09-01, test-first per §7 — four-gate green,
> 275 tests, coverage 98.9%, `cli.py` / `services/export.py` /
> `storage/paths.py` all at 100%. The contract below is kept verbatim as the
> record of what was built.**
> Scope beyond this document is out. Test-first: every behaviour below gets a
> failing test before its implementation. Discharges audit issues D1, D2, D3
> and invariant #1's guard.

## 1. Scope boundary

| In scope | Out of scope |
|---|---|
| Data-home default path + legacy CWD fallback (D2) | Encryption of exports (user's disk encryption; documented) |
| Lossless `lre export` / `lre restore` bundle with SHA-256 (D1) | Cross-schema-version restore (refused loudly) |
| `lre db check` — `integrity_check` + `foreign_key_check` (D3) | Automated backups / cron (export IS the backup, one mechanism) |
| Network-import guard test (invariant #1) | Compaction, pruning, cloud anything |
| README data-location & backup guidance | TUI/Web, config files |

## 2. Data-home default (D2)

`storage/paths.py` (new):

```python
def default_db_path() -> str
    # win32:  %LOCALAPPDATA%\LoveRiskEngine\love_risk.db  (fallback: ~)
    # darwin: ~/Library/Application Support/LoveRiskEngine/love_risk.db
    # else:   $XDG_DATA_HOME (fallback ~/.local/share)/LoveRiskEngine/love_risk.db

def resolve_db_path(explicit: str | None = None) -> str
    # explicit wins; else ./love_risk.db if it exists (legacy data, never
    # orphaned); else default_db_path()
```

- `cli.get_db()` passes `LRE_DB_PATH` (or None) to `resolve_db_path`.
- `Database.connect()` creates parent directories (`os.makedirs`, guarded for
  bare filenames) so the data dir exists before sqlite opens it.
- `lre init` already prints the resolved path — discoverability for free.

## 3. Lossless export/restore (D1)

**Storage primitives** (`storage/database.py`, identifiers are package-owned
constants from `schema.py`, never caller input):

```python
TABLE_ORDER  # in schema.py: FK parents before children
export_all_tables() -> dict[str, list[dict]]      # SELECT * per table, dict rows
restore_all_tables(tables) -> int                 # one transaction: DELETE all
                                                  # in reverse order, INSERT all;
                                                  # returns row count
integrity_check() -> tuple[bool, str, list[dict]] # PRAGMA integrity_check +
                                                  # PRAGMA foreign_key_check
```

**Bundle format** (`services/export.py`, new):

```json
{
  "format": "loverisk-bundle", "version": 1,
  "schema_version": 3, "tables": { ...all tables, dict rows... },
  "sha256": "<hex over the canonical form of the four fields above>",
  "exported_at": "<UTC ISO>"
}
```

- Canonical form: `json.dumps(payload, sort_keys=True, separators=(",", ":"))`
  over `{format, version, schema_version, tables}` — `sha256`/`exported_at`
  excluded, so the checksum is stable and verifiable.
- `restore` **refuses loudly** on: unknown format/version, checksum mismatch
  (corruption/tamper), schema_version ≠ current (restore is same-version
  backup; cross-version is out of scope by decision).
- `lre export <file>` refuses to overwrite an existing file. `lre restore
  <file>` replaces the entire current database inside one transaction
  (all-or-nothing).

## 4. `lre db check` (D3)

`lre db check` → prints `Database OK (<path>)` or lists `integrity_check`
detail + every `foreign_key_check` violation and exits non-zero. Grouped under
a `db` subcommand (`lre db check`) so future db-level commands have a home.

## 5. Network-import guard (invariant #1)

`tests/test_invariants.py`: AST-scan every `love_risk_engine/**/*.py` for
imports of `{requests, urllib, urllib3, http, httpx, aiohttp, socket, ftplib,
smtplib, telnetlib}`; any hit fails the test with the offender list. Adding a
network import now requires amending this test *and* `ARCHITECTURE_AND_PLAN.md`
invariant #1 — the drift can't be accidental.

## 6. TDD test list (written first, red, then green)

`tests/test_paths.py` (new):

1. `test_default_db_path_windows_uses_localappdata`
2. `test_default_db_path_windows_falls_back_to_home`
3. `test_default_db_path_macos`
4. `test_default_db_path_linux_uses_xdg`
5. `test_default_db_path_linux_falls_back_to_dot_local_share`
6. `test_resolve_db_path_explicit_wins`
7. `test_resolve_db_path_uses_legacy_cwd_db_when_present` (chdir to tmp)
8. `test_resolve_db_path_goes_to_data_dir_without_legacy` (chdir, platform+env)

`tests/test_export.py` (new):

9. `test_export_restore_roundtrip_is_lossless` — DB with rows across **every**
   table (relationships w/ kinds, observations w/ claims, boundaries + hits,
   inconsistencies, reviews, cooldowns, override_log, state_history,
   exposure_history) → export → restore into a fresh DB → `export_all_tables()`
   equal.
10. `test_restore_rejects_tampered_bundle` (checksum mismatch)
11. `test_restore_rejects_wrong_schema_version`
12. `test_restore_rejects_unknown_format`
13. `test_restore_replaces_existing_contents` (not additive)

`tests/test_storage.py` additions:

14. `test_export_all_tables_covers_every_table`
15. `test_integrity_check_ok_on_fresh_db`
16. `test_integrity_check_reports_foreign_key_violation` (raw sqlite connection
    with `foreign_keys=OFF` plants a bad `observation_claims` row)

`tests/test_invariants.py` (new):

17. `test_package_has_no_network_imports`

`tests/test_cli_commands.py` additions:

18. `test_export_and_restore_cli_roundtrip` (seed via CLI → export → mutate →
    restore → original state back)
19. `test_export_refuses_existing_file`
20. `test_restore_rejects_corrupt_file`
21. `test_db_check_reports_ok`

## 7. TDD order (mechanical)

1. Write tests 1–21 → `pytest` → **red**.
2. `storage/paths.py` + `Database.connect()` dir creation → paths green.
3. `schema.py` `TABLE_ORDER` + storage export/restore/integrity primitives →
   storage/export tests green.
4. `services/export.py` bundle format + verification → export tests green.
5. `cli.py` (`get_db` resolution, `export`, `restore`, `db check`) → CLI tests
   green.
6. Guard test → green (it scans the current tree; must already pass).
7. Full four-gate + coverage (95% floor, `cli.py` 100%).
8. Docs: README data-location & backup section; `AUDIT_REPORT.md` register
   marks D1–D3 done; `ARCHITECTURE_AND_PLAN.md` phase table updated; this plan
   marked implemented. Commit, push, watch CI.

## 8. Non-goals (restated so the diff cannot drift)

- No encryption, no compression, no incremental/delta export.
- No cross-schema-version restore; no automatic backups.
- No new runtime dependency (json/hashlib/os are stdlib).
- No changes to the engine or detectors.
