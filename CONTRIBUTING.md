# Contributing

Read this before your first PR. The rules below exist because each one
corresponds to a defect we actually shipped or nearly shipped.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pip install pre-commit && pre-commit install
```

## The gate

Every push must be green on all four. They run locally in seconds:

```bash
ruff check .          # lint — no findings allowed
ruff format --check . # formatting — no diffs allowed
mypy love_risk_engine # types (disallow_untyped_defs = true — must be clean)
pytest                # all tests pass
```

CI runs the same four on Python 3.11 / 3.12 / 3.13 and fails the build under
95% coverage (mirrored in `pyproject.toml` as `fail_under`). Pre-commit runs
them before you can commit, so a red CI should be a rare event.

## House rules

### 1. Never use `type: ignore` to silence something you have not read

We had 53 of them. One was hiding a genuine bug: `save_review(self, review:
"Review")` referenced a name that was never imported, masked by
`# type: ignore[name-defined]`. The annotation was a **string**, so it was
never evaluated at runtime, so tests passed and the bug shipped.

If you must suppress, name the rule and say why:

```python
value = row["legacy_col"]  # noqa: F821 - column added by migration, see #123
```

A bare `type: ignore` is a debt with no due date.

### 2. Verify linter autofixes, especially around `sqlite3.Row`

`ruff` suggested replacing `key in row.keys()` with `key in row`. That is
correct for a dict and **wrong for `sqlite3.Row`**, where `in` compares row
*values*, not column names:

```
'id' in row          -> False   # 'id' is not a value in this row
'id' in row.keys()   -> True    # 'id' IS a column
```

Applied blindly, that "cleanup" would have silently emptied every timestamp in
the timeline view. The SIM118 exemption used to be disabled for the two files
that touched `sqlite3.Row`; that exemption is now **gone** because every storage
query returns a domain object (see rule #7), so no raw row leaves `storage/`.
If you ever make `storage/` return a `sqlite3.Row` again, restore the per-file
exemption. Auto-fix is a suggestion, not a verdict.

### 3. One time standard: UTC, everywhere

Use `core.timeutil` (`utc_now_iso`, `expires_utc_iso`, `parse_iso`,
`is_future`). Do not call `datetime.now()` directly.

We previously stored observations in naive local time and cooldowns in UTC.
Timelines sort by timestamp *string*, so a UTC evening sorts before a local
morning of the same day. `parse_iso` treats naive values as UTC so legacy rows
still compare correctly.

### 4. Do not commit inside a helper that might be wrapped

Write methods call `self._commit()`, never `self._db.commit()`.

`_commit()` is a no-op while an outer `with db.transaction():` is active.
Without it, a helper that commits internally destroys the atomicity of any
transaction wrapping it — the outer rollback has nothing left to undo. Wrapping
`import_observations` in a transaction looked correct and was not; only the
test caught it.

### 5. SQL identifiers cannot be bound — allow-list them

Values are always bound parameters. Table and column names cannot be, so
`_next_id` checks `(table, column)` against `_ALLOWED_IDENTIFIERS` and raises
otherwise. Add to that set deliberately; never interpolate a caller-supplied
identifier.

### 6. Define it or delete it

`core.boundaries` declared `Boundary` and `BoundaryHit` while the storage layer
returned raw `sqlite3.Row` and never constructed them — an abstraction that
looked authoritative and enforced nothing. Storage now returns the domain
objects. Rule #7 below is what that change cost us.

### 7. Changing a return type means auditing every caller — by hand

Migrating `list_boundary_hits` from `sqlite3.Row` to `BoundaryHit` broke
exactly one caller:

```python
ts = h["timestamp"] if "timestamp" in h.keys() else ""   # AttributeError
```

inside `build_timeline`, reached only by `lre timeline`, which had **0%
coverage** and therefore no test to fail. `mypy` is advisory. CI was green. The
command was dead on arrival and nobody noticed until coverage work touched it.

Before changing what a function returns, grep the callers. If any of them are
untested, write the test first — the migration is not safe to review until you
can see it pass.

### 8. A test fake that cannot fail is worse than no fake

The `timeline` crash survived a green suite because `tests/test_timeline.py`
fed `build_timeline` a hand-rolled `_DictRow`: it quacked like a row, was not a
row, and was not a `BoundaryHit` either. It matched neither production shape,
so it could not detect a mismatch between them.

When a function consumes something the layer above it produces, feed it the
real return value at least once:

```python
events = build_timeline([], db.list_boundary_hits(rid), [], [])   # real objects
```

Fakes are for inputs you genuinely cannot construct, not for ones you cannot
be bothered to.

## Tests

- Test behaviour, not implementation. Assert on what the user sees.
- Use the `db` fixture (see `tests/test_database_integrity.py`) instead of
  constructing and closing a `Database` by hand in every test.
- Prefer `monkeypatch` over hand-rolled save/restore of attributes.
- When you fix a bug, add the test that would have caught it. Every test in
  `test_database_integrity.py` is there for that reason.
- If a test fails, decide which side is wrong before changing either. A failing
  expectation is not automatically a broken implementation.
- CLI tests call `main(argv)` in-process against `LRE_DB_PATH` in `tmp_path`
  (see `tests/test_cli_commands.py`). Subprocess tests lose branch attribution,
  which is usually the reason the test is being written.
- Some branches are unreachable through `main()` because the data cannot occur —
  `run_hooks` always returns at least one finding, so "no warnings" and "no
  hooks fired" never happen in production. Exercise those as direct unit tests
  on the formatting function and *say so in the docstring*, so nobody hunts for
  a CLI invocation that does not exist.

## Pull requests

Keep them reviewable: one concern each, under ~400 lines of diff. The title
states the change; the description states *why*.

Before requesting review, walk this list:

- [ ] `ruff check .` and `ruff format --check .` are clean
- [ ] `pytest` passes and you added tests for new behaviour
- [ ] Coverage did not drop (floor is 95%); read the missing-lines column, not
      the total
- [ ] If you changed a return type, every caller was checked by hand (rule #7)
- [ ] No new `# type: ignore` or `# noqa` without a reason
- [ ] No bare `datetime.now()`; use `core.timeutil`
- [ ] New writes go through `self._commit()`, not `self._db.commit()`
- [ ] No credentials, tokens, or personal data in the diff
- [ ] User-facing text stays honest: no invented certainty, no scores presented
      as fact

## Reviewing

Review the diff, not the author. Ask for a test rather than an explanation —
a test is an explanation that cannot rot. If you approve something you do not
understand, say so explicitly; that is useful information too.
