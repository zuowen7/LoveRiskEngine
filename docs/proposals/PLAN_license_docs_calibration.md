# Implementation Plan — License, Docs Anti-Drift, Calibration/Eval, Badges

> Status: **implemented 2026-09-01, test-first per §7 — four-gate green,
> 358 tests, coverage 98.8%, `cli.py` / `core/calibration.py` at 100%.
> Architecture invariant #11 (docs anti-drift) recorded in
> `ARCHITECTURE_AND_PLAN.md`. The contract below is kept verbatim as the
> record of what was built.**
> Test-first throughout. Architecture decisions recorded here amend
> `ARCHITECTURE_AND_PLAN.md` at the end of the phase.

## 1. Scope boundary

| In scope | Out of scope (recorded, deliberate) |
|---|---|
| Apache-2.0 `LICENSE` file + `pyproject` license field (no per-file headers — documented decision) | Coverage badge: needs an external coverage service (Codecov et al.) — deferred until the user chooses one |
| Docs anti-drift: purge drift-prone hard numbers + **executable doc-guard tests** | Generated docs tooling (sphinx et al.) |
| Calibration/evaluation **v1 = measurement**: schema v5 `review_outcomes` (user labels on past reviews), `lre evaluate`, `lre calibration` honest report | Personal threshold overrides wired into detectors — **deferred** until labeled data actually exists (architecture §4: measure first, tune only on the user's own data) |
| Badges: CI workflow + license + Python (shields.io) | — |

## 2. License

- Full Apache-2.0 text in `LICENSE`; `pyproject.toml` gains
  `license = {text = "Apache-2.0"}` (classic form — compatible with the
  pinned `setuptools>=61`).
- No per-file SPDX headers: Apache-2.0 does not require them and 36+ churned
  files would add noise. Recorded in `ARCHITECTURE_AND_PLAN.md` release policy.

## 3. Docs anti-drift (executable, not a habit)

1. **Purge** drift-prone hard numbers from docs: `docs/overview.md` test-count
   claims become version-free ("300+ tests"), README detector counts become
   the guard-checked number.
2. **`tests/test_docs.py`** (new — the guards fail the build on drift):
   - `test_readme_detector_count_matches_code` — regex `ships (\d+) detectors`
     in README.md equals `len(union of enabled_hooks over PROFILES)` (9).
   - `test_readme_zh_detector_count_matches_code` — regex `内置 (\d+) 个检测器`.
   - `test_overview_mentions_current_schema_version` — `docs/overview.md`
     contains `schema v{SCHEMA_VERSION}`.
   - `test_license_file_is_apache_2` — LICENSE exists, contains
     "Apache License" and "Version 2.0"; `pyproject.toml` license text says
     Apache-2.0.
   - `test_bilingual_docs_exist` — README_zh.md, docs/getting-started.{en,zh}.md
     exist and README.md links them.
   - `test_cli_usage_mentions_export_restore` — the two most safety-critical
     commands stay discoverable in README.md.
3. **Architecture invariant #11 (new)**: "Docs carry no driftable hard
   numbers; whatever claims remain are pinned by executable doc-guard tests."
   `AUDIT_REPORT.md` gains a docs-drift register entry, closed by this phase.

## 4. Calibration / evaluation — v1 measurement

### Semantics

1. `review_outcomes(review_id PK→reviews.id, outcome, note, labeled_at)` —
   the user's **retrospective label** on a past review (`good / bad / neutral`).
   Re-labeling is allowed and overwrites (labels are judgments, not evidence —
   stated in the docstring; underlying reviews are never touched).
2. `lre evaluate <review_id> --outcome good|bad|neutral [--note …]` — labels;
   unknown review → loud error; outcome allow-listed in parser AND storage.
3. `lre calibration <rel>` — per-rule stats over that relationship's reviews:
   fired / labeled / labeled-bad counts, plus totals. Framing printed with
   every report: *"these are counts from your own labeled history, not
   calibrated probabilities"*.
4. **Guardrail (invariant #5):** labels NEVER feed the engine automatically.
   No threshold changes, no re-ranking. Measurement only.

### Implementation

- `storage/schema.py`: `SCHEMA_VERSION = 5`, `review_outcomes` DDL appended
  to `TABLE_ORDER`; `_migrate_v4_to_v5`.
- `storage/database.py`: `label_review_outcome(review_id, outcome, note)`
  (upsert; allow-listed outcome), `list_review_outcomes(relationship_id)`
  (join through reviews), `get_review_outcome(review_id)`.
- `core/calibration.py` (pure): `ReviewOutcome`, `RuleStat`, `CalibrationReport`,
  `compute_calibration(reviews, outcomes)`, `VALID_OUTCOMES`.
- `cli.py`: `evaluate` + `calibration` commands; i18n keys for all new text.

## 5. Badges

README.md top (below the bilingual links):

```markdown
[![CI](https://github.com/zuowen7/LoveRiskEngine/actions/workflows/ci.yml/badge.svg)](https://github.com/zuowen7/LoveRiskEngine/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
```

## 6. TDD test list (written first, red, then green)

`tests/test_docs.py` (new): 6 guards from §3.

`tests/test_calibration.py` (new):

1. `test_label_creates_outcome_row`
2. `test_relabel_overwrites`
3. `test_invalid_outcome_rejected`
4. `test_compute_calibration_per_rule_stats`
5. `test_compute_calibration_empty`

`tests/test_migration.py`:

6. `test_v4_database_gains_review_outcomes`

`tests/test_cli_commands.py`:

7. `test_evaluate_then_calibration_roundtrip`
8. `test_evaluate_unknown_review_exits`
9. `test_calibration_reports_empty_gracefully`

## 7. TDD order

1. Write tests 1–9 → red.
2. LICENSE + pyproject + doc purges + guards → docs green (guards are
   property tests; the count fix is part of making them pass).
3. Schema v5 + storage + `core/calibration.py` → unit green.
4. CLI + i18n keys → CLI green.
5. Badges + README_zh sync; `ARCHITECTURE_AND_PLAN.md` (invariant #11,
   release policy, calibration measurement phase) + `AUDIT_REPORT.md` updates;
   this plan marked implemented. Four-gate, commit, push, watch CI.
