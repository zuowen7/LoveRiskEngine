# Code Quality Audit — LoveRiskEngine v0.2

Audit date: 2026-08-31 (updated after the `cli.py` coverage push)
Scope: `love_risk_engine/` (1,198 statements) + `tests/` (~2,400 LOC)

## 1. Summary

The codebase is well-structured for its age: clean layering (`core` /
`storage` / `services` / `cli`), dataclass domain models, stdlib only, and a
test suite that genuinely exercises behaviour rather than mocks.

The problem is not structure, it is **the absence of any automated gate**.
Nothing ran on commit, so defects that a linter or type checker catches in
milliseconds were reaching review — and one reached `main`.

| Metric | Before audit | After audit | After `cli.py` push |
|---|---|---|---|
| Tests passing | 81 | 106 | **159** |
| Coverage (branch) | 84% | 84% | **97%** |
| Coverage floor enforced | none | 80% | **90%** |
| `cli.py` coverage | **66%** | 66% | **100%** |
| `core/boundaries.py` coverage | **0%** | 100% | **100%** |
| `storage/database.py` coverage | 91% | 94% | **96%** |
| `type: ignore` suppressions | **53** | 0 | **0** |
| Ruff findings (all selected rules) | **188** | 0 | **0** |
| Files consistently formatted | 0 | 39 | **40** |
| CI / pre-commit | none | both | **both** |

The headline is not the 97%. It is that **closing `cli.py` found a live crash**
(see §2, "P1 — `lre timeline` crashed on every invocation"). Coverage work on
a 0%-covered command turned into a user-visible bug fix within an hour. That
is the argument for the practice, not the number.

---

## 2. Defects found and fixed

### P0 — `Review` referenced but never imported (shipped bug)

`storage/database.py:482` annotated `save_review(self, review: "Review")`.
The annotation was a **string**, so Python never evaluated it. `Review` was
never imported. The wrongness was masked by `# type: ignore[name-defined]`,
so neither tests nor review caught it.

Fixed with a `TYPE_CHECKING` import — the correct tool here, because
`services.review` imports `storage.database` and a runtime import would be a
cycle.

**Lesson:** a string annotation plus a suppression comment is a bug with the
smoke detector disconnected. This is now House Rule #1 in `CONTRIBUTING.md`.

### P0 — Bulk import was not atomic

`import_observations` looped calling `add_observation`, which commits per row.
A chat import failing at row 400 of 900 left 399 rows persisted as if the
import had succeeded — and paid one fsync per row.

Fixed with a `transaction()` context manager. The subtle part: wrapping the
loop is **not enough** when the helper commits internally. The outer rollback
would have had nothing to undo. Write methods now call `self._commit()`, which
no-ops while a transaction is open. A test asserts the first row is gone after
row 2 raises — it fails against the naive fix and passes against this one.

### P1 — Two time standards in one database

Observations, inconsistencies and boundary hits were stamped with naive local
time; cooldowns with UTC. The timeline sorts events by timestamp *string*, so
ordering is silently wrong whenever local time and UTC disagree — every day,
for any user not on UTC.

Consolidated into `core/timeutil.py`. Every stored timestamp is now UTC with an
explicit offset, and `parse_iso` reads legacy naive values as UTC so old rows
still compare correctly.

### P1 — Cooldown expiry compared as strings

`is_active` used `cooldown.expires_at > now`. That holds only while every
producer formats identically; one naive value from an old migration and the
comparison silently inverts. Now compares parsed datetimes, and an unparseable
expiry fails *open* (treated as expired) so a corrupt row can never lock the
user out — consistent with the project's "override is always possible"
principle.

### P1 — SQL identifiers interpolated into query text

`_next_id` built `SELECT {column} FROM {table} ...` from caller arguments.
Identifiers cannot be bound as parameters, so they are now checked against an
explicit `_ALLOWED_IDENTIFIERS` allow-list that raises on anything unknown.
All *values* remain bound parameters.

### P1 — `lre timeline` crashed on every invocation (regression, found by coverage)

Discovered while writing the first-ever test for `cmd_timeline`. It had zero
coverage, so nothing was watching it, and it had been broken by an earlier
change in this very audit.

`build_timeline` read boundary hits as rows:

```python
ts = h["timestamp"] if "timestamp" in h.keys() else ""
```

but `list_boundary_hits` had been migrated (see `core.boundaries` below) to
return `BoundaryHit` dataclasses. Result: `AttributeError: 'BoundaryHit' object
has no attribute 'keys'` — the `timeline` command was dead on arrival.

Fixed with a single `_field(obj, name, default)` accessor that reads from
either shape, because `build_timeline` legitimately consumes both:
`observations` / `boundary_hits` are domain objects, `inconsistencies` /
`reviews` are still raw rows. One accessor means the next table to migrate
needs no change here.

**Why the existing tests missed it:** `tests/test_timeline.py` fed
`build_timeline` a hand-rolled `_DictRow` fake that matched *neither*
production shape. It was a plausible-looking object that could not fail. Two
guards were added: one passing the real `BoundaryHit`, and one feeding the
function the actual return value of `Database.list_boundary_hits`. See §6.

### P1 — Boundaries could never be retired

`add_boundary` hardcoded `active=1` and no method could ever set it back to 0.
A soft boundary that stops being relevant accumulated forever, and — because
hard-boundary hits drive the EXIT recommendation — a stale boundary kept
vetoing decisions with no way to withdraw it.

Added `Database.deactivate_boundary(id) -> bool`. Retired, never deleted, so
earlier `boundary_hits` stay interpretable and the audit trail is intact.

### P2 — 53 `# type: ignore[union-attr]` comments

`Database.conn` is `Optional[Connection]`, so every use needed suppressing.
That is a symptom, not a fix: the `Optional` should be resolved once, not 53
times. Replaced with a `_db` property that raises a clear `RuntimeError` when
disconnected. Zero suppressions remain, and misusing a closed database now
fails loudly instead of as an `AttributeError` on `None`.

---

## 3. Near miss worth reading

Ruff flagged `key in row.keys()` as SIM118 and offered `key in row`. Correct
for a dict. **Wrong for `sqlite3.Row`**, where `in` compares row *values*:

```
'id' in row          -> False
'id' in row.keys()   -> True
```

Accepting that autofix across the codebase would have turned every
column-existence check in the timeline into a value lookup, emptying every
timestamp and scrambling the ordering — with all tests still green.

The rule was disabled for `cli.py` and `core/timeline.py` because both touched
`sqlite3.Row`. **Verify autofixes before committing them.** This is House
Rule #2.

That exemption is now **gone**. Every storage query returns a domain object
(see §4), so there is no `sqlite3.Row` left outside `storage/database.py`'s
private `_row_to_*` mappers — and those use positional column access, never
`.keys()`. The SIM118 exemption was removed from `pyproject.toml` on
2026-08-30; if a raw row ever escapes the storage layer again, restore it.

---

## 4. Known debt (deliberately not fixed here)

All items from the original audit are now **closed**. The table records the
resolution path for each, so a future reader can see what "done" meant.

| Item (original) | Size | Resolution |
|---|---|---|
| `UP` / `PTH` modernisation (124 findings) | done | Migrated, both rules moved `ignore → select`. |
| `core.boundaries` unused | done | Storage returns `Boundary` / `BoundaryHit`; this also fixed the `timeline` crash. |
| `cli.py` coverage 66% | done | 100% statement + branch. |
| Coverage floor 80% → 90% | done | Raised to **95%** (2026-08-30), mirrored in `pyproject.toml` + CI. |
| `mypy` not strict | done | `disallow_untyped_defs = true` since 2026-08-30; `continue-on-error` dropped from CI. Source is clean, tests exempted. |
| `_migrate()` runs on every `init()` | done | Replaced by `PRAGMA user_version` gating: an up-to-date DB returns after one integer read; legacy DBs run `_migrate_v0_to_v1` exactly once, then are stamped. |
| `_next_id` read-then-write | done | Kept `max()+1` (correct for the single-user CLI model) **and** added a real collision fallback: after building the token it re-checks the table and loops to the next free `NNN` until `UNIQUE`-safe. |
| Row mapping split (`sqlite3.Row`) | done | All seven `list_*` / get queries return domain objects; `timeline._field()` deleted; SIM118 exemption removed. |
| Boundary / cooldown lifecycle CLI-less | done | `lre boundary retire <id>` exposes `deactivate_boundary`; `log_override` was already reachable via `exposure set --override`, and its audit trail is shown by `lre cooldown <rel>`. |
| Review checklist not in PR template | done | `.github/PULL_REQUEST_TEMPLATE.md` added (engineering gate + domain guardrails). |

**What remains is research, not debt** — it is explicitly *not* a defect and
was never in the "fix this" list:

- Property-based tests (`hypothesis`) for `detect_contradictions` / `timeutil`.
- Mutation testing (`mutmut`) on `core/decision.py` / `core/cooldown.py`.

Both are valuable next steps but would pull in new dev dependencies; they are
tracked here as future investment, not as open bugs.

---

## 5. Route to the next level

### Immediate (this week)
1. `pip install -e ".[dev]" && pre-commit install` — everyone.
2. **Done:** row-mapping migration finished, `timeline._field()` deleted,
   SIM118 exemption removed. Every migration found a bug; this one too
   (`lre timeline` was silently broken on domain objects).
3. **Done:** `lre boundary retire <id>` exposes `deactivate_boundary`.

### Next 30 days
4. **Done:** `disallow_untyped_defs = true` globally; `mypy` `continue-on-error`
   removed from CI.
5. **Done:** `PRAGMA user_version` versioned migrations replace `_migrate()`.
6. **Done:** coverage floor 90% → 95%. It only ever goes up.

### Next 90 days (research, optional)
7. Property-based tests (`hypothesis`) for `contradiction.detect_contradictions`
   and `timeutil` — both are pure functions with tricky edge cases.
8. Mutation testing (`mutmut`) on `core/decision.py` and `core/cooldown.py`.
   These encode safety-critical rules; passing tests prove little if no test
   fails when the logic is inverted. Start here: the cooldown gate is the one
   place the tool refuses a user's request, and its tests are still
   example-based.
9. **Done:** review checklist enforced in the PR template.

---

## 6. Habits that produce this codebase

Three practices matter more than any tool configured above:

**Treat a suppression as a decision, not a keystroke.** Every `noqa` and
`type: ignore` should name its rule and its reason. The shipped `Review` bug
was a suppression that outlived the memory of why it was added.

**A failing test is a question, not an instruction.** During this audit a new
test failed because the *expectation* was wrong — unparseable expiry should
fail open, not hang. Deciding which side is wrong is the job.

**Coverage is a map, not a score.** 84% tells you nothing. What mattered was
that `boundaries.py` — the module behind the EXIT recommendation — sat at 0%,
and that `cmd_timeline` sat at 0% while being completely broken. Read the
missing-lines column; do not read the total.

**A test fake that cannot fail is worse than no fake.** The `timeline` crash
slipped through a green suite because `test_timeline.py` passed a hand-rolled
`_DictRow` that quacked like a row but was not one — and was not a
`BoundaryHit` either. It matched neither production shape, so it could not
detect a mismatch between them. When a function consumes something a layer
above it produces, feed it the real return value at least once. Fakes are for
the cases you cannot construct, not the ones you cannot be bothered to.

**Migrating a return type is a breaking change with no compiler to catch it.**
Changing `list_boundary_hits` from rows to dataclasses broke exactly one
caller, in a command with no tests. With `mypy` in advisory mode and one
uncovered command, nothing complained. Before a change like that, grep the
callers — and treat "no callers are tested" as a reason to add tests first,
not as a reason to ship.
