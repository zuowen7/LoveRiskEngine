# Repository Guidelines

## Project Structure & Architecture

`love_risk_engine/` contains `core/` domain logic, `storage/` SQLite persistence, `services/` orchestration, and `cli.py` presentation. `core/` imports no storage, service, CLI, or network modules. Tests are in `tests/`, plans in `docs/`, and sample rules in `examples/`.

`docs/ARCHITECTURE_AND_PLAN.md` is canonical. Begin each slice with a `docs/proposals/` plan; before coding, also amend the canonical document for invariant, boundary, or dependency changes.

## Setup & Quality Gate

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate; POSIX: source .venv/bin/activate
python -m pip install -e ".[dev]"
pre-commit install
pre-commit install --hook-type pre-push   # House Rule #9 safety net
lre --help
ruff check .
ruff format --check .
mypy love_risk_engine
python -m pytest --cov=love_risk_engine --cov-report=term-missing
```

Editable installation is the development build; CI runs the gate on Python 3.11–3.13.

## Coding Style & Naming Conventions

Use UTF-8/LF, four spaces for Python, two for YAML/JSON/TOML, double quotes, and 88-character lines. Ruff formats and lints; type-annotate shipped functions. Use `snake_case` for modules/functions, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants.

## Engineering Contracts

Keep required runtime dependencies at zero. Soft-import optional presentation dependencies and retain the base CLI's plain-text fallback. Route new static CLI chrome, help, and errors through `t()`. Keep evidence canonical; localize findings at display time through `msg_key`/`msg_params`.

Profile context uses `HIGH/MED/LOW`. Scores stay within 0–10 and are evidence indicators, not probabilities. Do not add percentage-like or opaque composite risk scores; mark heuristic thresholds `uncalibrated`.

Use `resolve_db_path()` and retain its legacy-CWD fallback. Create UTC timestamps through `core.timeutil`. Keep `sqlite3.Row` inside storage; persistence helpers use `self._commit()`. Bind SQL values and allow-list identifiers.

Every new detector must register a `RuleSpec` in `core/rulespec.py` (theory anchor, evidence level, `uncalibrated` threshold status) — `tests/test_rulespec.py` fails the build otherwise. Load-bearing, hard-to-reverse decisions get an immutable ADR in `docs/adr/` (supersede by writing a new ADR that points back; never rewrite). Never use `--no-verify` (House Rule #9): the pre-push hook re-runs the four gates and cannot be skipped.

## Testing Guidelines

See `docs/TESTING.md` for the philosophy (coverage as a map, not a score; fakes must be able to fail; mutation guards; property tests; the meta-guard pattern). Name tests `tests/test_<subject>.py` and `test_<behavior>()`. Test behavior and add a regression for every bug. Prefer real domain objects, `tmp_path`, and `monkeypatch`; call CLI `main(argv)` in-process with temporary `LRE_DB_PATH`. Keep branch coverage at least 95%. When you add an invariant/doc test, add the meta-guard that proves it fires.

Every schema change must update canonical DDL, bump `SCHEMA_VERSION`, add one versioned migration, and test previous-version upgrade with data preservation. Export or schema changes also require a same-version lossless export→restore test.

## Commits, Pull Requests & Safety

Use Conventional Commit-style subjects such as `feat:`, `fix(ci):`, or `docs:`. Keep a PR to one concern and roughly under 400 changed lines. Explain what and why, link the issue, identify migrations or follow-ups, and confirm all gates pass.

Never commit databases, credentials, tokens, chat exports, or personal data. Committed code remains local-only: no outbound network calls, surveillance, or new PII fields.
