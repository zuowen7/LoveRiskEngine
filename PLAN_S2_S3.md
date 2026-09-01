# Implementation Plan — S2 & S3 (relationship kinds)

> Status: **implemented 2026-08-31, test-first per §4 — four-gate green,
> 215 tests, coverage 98.3%, `cli.py` 100%.**
> The contract below is kept verbatim as the record of what was built.
> Scope beyond what is written here is out — if a good idea appears mid-slice,
> it goes in a new proposal, not in these diffs.
> Parent document: `PROPOSAL_relationship_kinds.md` (reviewed, §5 decisions
> recorded). Test-first throughout: every behaviour below gets a failing test
> before its implementation.

---

## 1. Scope boundary

| In scope | Out of scope (do NOT build) |
|---|---|
| S2: `promise_expiry` detector, display windowing, `lre promises` command | Reply coaching, any reply generation |
| S3: `exit_cost` HIGH sensitivity for two thresholded rules, boundary-seed *suggestions*, review context line | Numeric power/exit indices; formulas over ordinals |
| Kind-aware hook dispatch (the `enabled_hooks` wiring) | Per-kind surgery on the six v1 hooks — every kind keeps running all six |
| Display-only windowing (never deletes rows) | Data cleanup, "历史垃圾" labels, repeated re-promise counting |
| — | User-editable profiles, config files, new runtime dependencies |

**Decisions resolved here** (proposal §5.5 was deferred to S2):

1. Future-tense matching is a **conservative code lexicon** (regex, word
   boundaries) — same honesty contract as `signals.py`: misses paraphrases, may
   over-match, the warning lists every claim it fired on. No user claim-rules
   integration this slice.
2. `promise_expiry` applies to **BOSS / MENTOR / COLLEAGUE** — the three kinds
   with `promise_window_days = 90` in the approved §5.4 table (proposal §4.3
   named only BOSS/MENTOR; the reviewed table is authoritative and includes
   COLLEAGUE).

## 2. S2 — promise expiry & display windowing

### 2.1 Semantics (exact rules)

A **promise** is a structured claim (`attribute=value`) whose *value* is
future-directed per the lexicon (§2.2). For each normalized attribute, only
the **latest mention** (most recent observation, ties broken by id) is
considered:

1. Latest mention not future-directed (e.g. `funding=delivered`) → the promise
   was resolved or handed to the contradiction tracker's domain → **skipped**.
2. Latest mention future-directed and its age ≤ window → **within window**.
3. Latest mention future-directed and its age > window → **expired**.

So "expired" means exactly: *the attribute has gone untouched for longer than
the window while still pointing at the future*. A re-mention restarts the
window (by construction — the latest mention governs). A malformed timestamp
fails open: the claim is excluded from both lists and never crashes anything.

The detector output is a `BiasFinding` proposing **WAIT** (severity 2), never a
conviction, listing up to 3 expired claims with observation id, date and age
days — the basis stays auditable (DESIGN.md Do's #3).

### 2.2 New module `core/promises.py`

```python
_FUTURE_PATTERN  # compiled regex, word boundaries, IGNORECASE:
                 # will | going to | gonna | promise(s|d) | next week/month/
                 # year/quarter/semester | by the end of | plan(s) to |
                 # intend(s) to | upcoming | by next

@dataclass(frozen=True)
class PromiseClaim:
    attribute: str          # normalized (contradiction.normalize_attribute)
    value: str
    observation_id: str
    timestamp: str
    age_days: int

@dataclass(frozen=True)
class PromiseReport:
    window_days: int | None
    within: list[PromiseClaim]
    expired: list[PromiseClaim]

def is_future_directed(value: str) -> bool
def collect_promises(
    observations, window_days: int | None, now: str | None = None
) -> PromiseReport      # window_days None -> empty report; lists sorted by timestamp
def detect_expired_promises(
    observations, window_days: int | None, now: str | None = None
) -> BiasFinding | None  # None when window is None or nothing expired
```

Time handling goes through `core.timeutil` only (`utc_now_iso`, `parse_iso`);
no direct `datetime.now()` (CONTRIBUTING.md rule #3).

### 2.3 Wiring

- `core/profiles.py`: `_HOOKS_V1` stays six; BOSS / MENTOR / COLLEAGUE get
  `enabled_hooks = _HOOKS_V1 + ("promise_expiry",)`.
- `core/hooks.py`: `ReviewContext` gains a required `profile: RelationshipProfile`
  field (single construction site: `services/review.py::build_context`).
  `run_hooks` dispatches on `set(ctx.profile.enabled_hooks)`; every v1 hook
  keeps its current call order; `promise_expiry` runs last when enabled.
- `services/review.py::build_context`: resolves `rel.kind` →
  `get_profile(rel.kind)` (missing relationship falls back to `LOVER`).

### 2.4 CLI surface

- `lre status <rel>`: when `profile.promise_window_days` is not None *and*
  there are promises, print after the contradictions block:

  ```
  Promises (window: 90d)
    funding='will fund' (O001, 2026-05-01, 122d)
  Older promises (1): run `lre promises <rel>` for details.
  ```

  `format_status` gains an optional `promises: PromiseReport | None = None`
  parameter (direct unit tests keep passing without it).

- **New command `lre promises <rel>`** (the "one command away" from the
  proposal): full list, split within/expired, with ages. For a kind without a
  window: `Kind LOVER does not track a promise window.` Empty: `No promise
  claims recorded.`
- `lre review <rel>`: needs no new code for the hook to fire — `promise_expiry`
  flows through `run_hooks` into `triggered_hooks` / `notes` automatically.

### 2.5 S2 tests (written first, red, then green)

`tests/test_promises.py` (new — unit level, fixed `now`):

1. `test_is_future_directed_matches_lexicon` — "will fund", "promised to pay",
   "by the end of 2026" → True.
2. `test_is_future_directed_rejects_past_and_bare_words` — "funded",
   "willpower", "", "recommended me" → False.
3. `test_collect_promises_ignores_non_future_claims`.
4. `test_collect_promises_splits_within_and_expired` — fixed `now`, one 10d-old
   + one 122d-old → exactly one each.
5. `test_collect_promises_latest_mention_governs` — re-mention restarts window;
   later non-future value (delivered) → skipped.
6. `test_collect_promises_empty_without_window` — `window_days=None`.
7. `test_collect_promises_fails_open_on_malformed_timestamp` — garbage ts
   excluded, no raise.
8. `test_detect_expired_promises_fires_wait_with_audit_details` — rule_id,
   `WAIT`, window + claim + obs id + age in message.
9. `test_detect_expired_promises_caps_at_three_with_count`.
10. `test_detect_expired_promises_none_when_fresh_or_no_window`.

`tests/test_cli_commands.py` (integration — monkeypatch
`love_risk_engine.storage.database._now` for old timestamps):

11. `test_status_shows_promise_section_for_windowed_kind`.
12. `test_status_omits_promise_section_for_lover_kind`.
13. `test_promises_command_lists_within_and_expired`.
14. `test_promises_command_reports_no_window_kind`.
15. `test_review_fires_promise_expiry_for_mentor` — `promise_expiry` in
    triggered hooks + `WAIT`-carrying review.
16. `test_review_does_not_fire_promise_expiry_for_lover`.

`tests/test_profiles.py`: extend pin — windowed kinds include `promise_expiry`,
non-windowed do not.

## 3. S3 — sensitivity direction, boundary seeds, voice polish

### 3.1 Sensitivity (exit_cost HIGH ⇒ earlier warnings)

`core/bias_detector.py` gains:

```python
class Sensitivity(StrEnum):
    NORMAL = "NORMAL"
    HIGH_EXIT_COST = "HIGH_EXIT_COST"

ATTRACTION_TRUST_GAP                = 3.0   # unchanged default
ATTRACTION_TRUST_GAP_HIGH_EXIT_COST = 2.0
RATIONALIZATION_RUN                 = 3     # unchanged default
RATIONALIZATION_RUN_HIGH_EXIT_COST  = 2
```

Only two rules shift — the two with clean scalar thresholds
(`attraction_exceeds_trust`, `repeated_rationalization`). The others are
untouched, deliberately: `exposure_outpaces_evidence` has no clean scalar;
`high_emotion_major_decision` is boolean; `unresolved_inconsistencies` fires on
count > 0 already (nothing "earlier" exists); `love_bombing_pattern` is an
early-window rule orthogonal to exit cost.

Both detectors gain an optional
`sensitivity: Sensitivity = Sensitivity.NORMAL` keyword. **NORMAL keeps the
exact current messages** (zero churn for existing tests/users). The shifted
path appends its basis to the message:

- `… significantly exceeds supported trust (4.0) (exit-cost sensitive: gap threshold 2.0).`
- `2 consecutive rationalizations detected (exit-cost sensitive: run threshold 2).`

`run_hooks` maps `ctx.profile.exit_cost is Ordinal.HIGH` →
`Sensitivity.HIGH_EXIT_COST` and passes it to the two rules. Affected kinds by
the approved table: PARENT / BOSS / MENTOR.

### 3.2 Boundary seeds as *suggestions* (never auto-created)

`lre relationship add --kind X` prints the profile's `boundary_seeds` as
suggestions after the confirmation line. The engine never creates boundaries
on its own — "the user always decides" (house precedent: `signals.py`).

### 3.3 Review context line (voice polish)

Extract `_profile_context(profile) -> str | None` in `cli.py` (None for
`LOVER`), used by both `format_status` (identical output to S1) and `cmd_review`
— `lre review` now prints the same `power asymmetry / exit cost / voice` line
where decisions actually happen.

### 3.4 S3 tests (written first, red, then green)

`tests/test_bias.py` additions:

1. `test_attraction_high_exit_cost_fires_earlier` — gap 2.5 fires under
   HIGH_EXIT_COST, silent under NORMAL.
2. `test_attraction_message_states_shifted_threshold`.
3. `test_attraction_normal_message_unchanged`.
4. `test_rationalization_high_exit_cost_fires_earlier` — run of 2.
5. `test_rationalization_message_states_shifted_threshold`.

`tests/test_cli_commands.py` additions:

6. `test_boss_status_fires_earlier_attraction_warning` — attraction 8.5,
   trust 6, <3 obs: BOSS warns (gap 2.5 ≥ 2.0), LOVER does not (gap 2.5 < 3.0).
7. `test_review_prints_context_line_for_non_default_kind` — BOSS review shows
   the context line; LOVER review does not.
8. `test_relationship_add_suggests_seed_boundaries` — PARENT prints both
   seeds; LOVER prints none.

## 4. TDD order (mechanical, followed exactly)

1. Write S2 test file + CLI tests + profile-pin extension → run pytest → **red**.
2. Implement `core/promises.py` → run its tests → **green**.
3. Wire profiles / hooks / build_context → CLI tests → **green**.
4. Write S3 tests → run → **red**.
5. Implement bias_detector sensitivity + hooks mapping → **green**.
6. Implement seeds + review context line → CLI tests → **green**.
7. Full four-gate + coverage run (floor 95%, `cli.py` 100%).
8. Update `PROPOSAL_relationship_kinds.md` §4 status + `README.md` (promises
   command, sensitivity note) + `overview.md` built-list.

## 5. Non-goals (from the parent proposal, restated so the diff cannot drift)

- No reply coaching, no suggested replies, no "buffer reply" logic.
- No numeric indices; ordinals stay ordinals and stay out of formulas.
- No deletion or auto-cleanup; windowing is display-only.
- No new runtime dependency; no config files; no user-editable profiles.
- No `lre mode` alias (decided: command surface minimal).

## 6. Gate checklist

- [ ] `ruff check .` clean, `ruff format --check .` clean
- [ ] `mypy love_risk_engine` clean (strict-ish config)
- [ ] `pytest` all green; coverage ≥ 95% via the CI command
- [ ] `cli.py` at 100% statement + branch
- [ ] No `type: ignore` without a named, read reason
- [ ] Time via `core.timeutil` only; writes via `_commit()` (no new writes here)
- [ ] Warning text carries its basis (window / threshold / claim / obs id)
