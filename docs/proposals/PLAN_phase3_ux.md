# Implementation Plan — Phase 3 Remainder (UX, no UI)

> Status: **implemented 2026-09-01, test-first per §5 — four-gate green,
> 328 tests, coverage 98.9%, `cli.py` 100%. UI decision deferred by the user,
> config file skipped — both recorded in `ARCHITECTURE_AND_PLAN.md` §8.
> The contract below is kept verbatim as the record of what was built.**

## 1. Scope boundary

| In scope | Out of scope |
|---|---|
| `lre completion <shell>` — static glue templates (bash/zsh/fish/powershell) | DB-backed value completion (relationship aliases/ids) — documented v1 limitation |
| `lre _complete <tokens…>` — runtime completion engine introspecting the argparse tree (zero drift: the script asks the running `lre`) | TUI / Web UI (deferred by user) |
| E2: `add_observation` gains an optional `timestamp`; `import_observations` preserves source timestamps (missing → `_now()`, current fallback) | Config file (skipped by decision); rewriting stored chat rows |

## 2. Shell completion semantics

1. `lre completion bash|zsh|fish|powershell` prints a template that registers a
   completion function calling `lre _complete <tokens…>` — candidates always
   come from the *installed* parser, so command drift is impossible.
2. `lre _complete` (hidden; excluded from its own candidates) takes the token
   list with the **last token as the partial prefix**; it walks the argparse
   tree (subcommands descend, options skip their value token) and prints
   matching candidates, one per line: subcommand names, option strings, and
   positional `choices` (kinds, severities, signal types, states, shell
   names). No network, no DB lookups, stdlib only.
3. Best-effort contract: completion is a convenience, never authoritative —
   the parser still validates everything.

## 3. E2 — chat import ordering

- `Database.add_observation(..., timestamp: str | None = None)` stores
  `timestamp or _now()`.
- `Database.import_observations` passes `timestamp=o.timestamp or None`, so
  imported rows keep their source timestamps (NDJSON/delimited) instead of
  collapsing to insertion time; missing timestamps fall back to `_now()` as
  before.
- Ordering stays deterministic where timestamps collide: timeline and
  detectors sort by `(timestamp, id)`, and ids are sequential.

## 4. TDD test list (written first, red, then green)

`tests/test_completion.py` (new — engine):

1. `test_root_candidates_list_subcommands` (no `_complete`, no leading-underscore)
2. `test_descends_into_subcommands` (`relationship` → `add`, `set`)
3. `test_positional_choices_surface` (`relationship add X --kind` context →
   the seven kinds)
4. `test_partial_prefix_filters` (`--ki` → `--kind`)
5. `test_option_values_are_skipped` (`observe A --claim k=v --si` → `--signal-type`)
6. `test_unknown_tokens_do_not_crash` (garbage tokens → safe fallback)

`tests/test_cli_commands.py`:

7. `test_completion_prints_bash_template` (contains `complete -F` +
   `lre _complete` marker)
8. `test_internal_complete_prints_candidates` (`lre _complete rel` → `relationship`)

`tests/test_storage.py` / `tests/test_chat_import.py`:

9. `test_add_observation_preserves_explicit_timestamp`
10. `test_import_observations_preserves_source_timestamps`
11. `test_import_observations_falls_back_to_now_for_missing_timestamp`

## 5. TDD order

1. Write tests 1–11 → red.
2. Completion engine + templates + hidden command → completion tests green.
3. `add_observation` timestamp param + import wiring → storage/import green.
4. Full four-gate + coverage; docs (README completion section; `AUDIT_REPORT.md`
   E2/E3 done; architecture phase table closes phase 3 with the UI-deferral
   note; this plan marked implemented). Commit, push, watch CI.
