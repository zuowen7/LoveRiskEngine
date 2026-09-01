# LoveRiskEngine — Audit Report

> Date: 2026-09-01 · Scope: repo hygiene, engineering quality, domain design,
> data safety, functional coverage, community positioning.
> Method: code inspection, gates re-run, git-history review, network-import
> scan, competitor research (see `RESEARCH_COMMUNITY.md`).
> Companion document: `ARCHITECTURE_AND_PLAN.md` (target architecture +
> phased plan that discharges the issues registered here).

## 1. Executive summary

**Verdict: the engineering core is in unusually good shape; the real risks are
operational (data safety UX) and strategic (roadmap reconciliation) — not code
quality.**

| Dimension | Grade | One-line summary |
|---|---|---|
| Engineering quality | **A** | 248 tests, 98.8% coverage (floor 95), `cli.py` 100%, ruff/mypy clean, CI ×3 Python versions |
| Migration discipline | **A** | Schema v0→v3, every step versioned and tested; domain objects only leave `storage/` |
| Principle adherence | **A** | No pseudo-precision, no judging tone, user-decides, never-delete — verified in code, not just docs |
| Repo hygiene | **B+** | Fixed this session (docs structure, stale README, pre-commit); one versioning wart remains |
| Data safety | **B−** | Local-only and privacy-clean, but no export/backup story and a CWD-dependent default DB path |
| Roadmap coherence | **C+** | Old README roadmap listed items that now conflict with the project's own principles; reconciliation in progress |
| Community positioning | *(see §7)* | Research scan in `RESEARCH_COMMUNITY.md` |

## 2. Repo hygiene audit

**Fixed in this session:**

- Documentation reorganized: `DESIGN.md`, `overview.md`, `CODE_QUALITY_REPORT.md`
  → `docs/`; the four shipped-slice contracts (`PROPOSAL_relationship_kinds.md`,
  `PLAN_S2_S3.md`, `PLAN_state_exposure_history.md`, `PLAN_rapid_escalation.md`)
  → `docs/proposals/` (history preserved via `git mv`).
- README de-staled: version-agnostic title, "5 detectors" → 8, project-layout
  updated with the new modules, the roadmap section now points at the canonical
  roadmap instead of carrying its own stale list.
- `pre-commit` installed and verified (`pre-commit run --all-files` green:
  ruff lint/format, whitespace/EOF/YAML/TOML checks, pytest).

**Verified clean:** no build artifacts tracked (`*.egg-info/`, caches all
ignored); `.gitignore` covers Python, venvs, local DBs, tooling caches, and
`.workbuddy/`.

**Remaining wart:** `pyproject.toml` still says `version = "0.1.0"` while the
feature set is well past that. This is a *release* decision (semver moment),
not a typo — registered as issue R1 and resolved by the versioning policy in
`ARCHITECTURE_AND_PLAN.md`.

## 3. Engineering quality audit

- **Gates**: 248 tests (branch coverage on), total coverage 98.8% against a 95%
  floor; `cli.py` 100% statement+branch; `ruff check` / `ruff format --check`
  / `mypy love_risk_engine` clean; CI matrix 3.11/3.12/3.13.
- **Process**: every shipped slice since the kinds proposal followed
  plan-document-first → TDD (red→green demonstrated) → four-gate. The contracts
  are preserved in `docs/proposals/`, so the *why* of every threshold and
  semantic survives the code.
- **Storage discipline**: versioned migrations (`PRAGMA user_version`),
  sequential readable IDs with a collision fallback, allow-listed SQL
  identifiers, `_commit()` transaction nesting, fail-open parsing (a corrupt
  row can never lock the user out), all queries return domain objects.
- **Known accepted exclusions**: `core/hooks.py` + `core/evidence.py` are
  coverage-omitted (defensive branches structurally unreachable through the
  CLI) — documented in `pyproject.toml`, consistent with house precedent.
- **Gap**: the pre-commit config runs pytest but not mypy (CI still catches
  it). Registered as issue R2 — one line to add if we want commits to never
  outrun the type checker.

## 4. Domain & principles adherence audit

Checked against the written principles (README + `docs/DESIGN.md`):

- **No pseudo-precise scores** ✅ — ordinals (HIGH/MED/LOW) only; every numeric
  threshold is labeled an uncalibrated placeholder; no weighted formulas over
  them exist.
- **No judging tone** ✅ — warning strings were spot-checked: every one states
  its basis (threshold, claim, observation id, window) and proposes
  CONTINUE_OBSERVING/WAIT/PAUSE, never a conviction. EXIT remains reserved for
  recorded hard-boundary hits.
- **User always decides** ✅ — signal classification hints but never auto-sets;
  boundary seeds print as suggestions; cooldown override is possible and
  audited; contradiction resolution is three-state and human-arbitrated.
- **Never delete** ✅ — boundaries retire, observations append, history rows are
  append-only; windowing (promise display) is presentation-only.
- **Privacy / local-only** ✅ — package-wide scan found **zero network imports**
  (no requests/urllib/socket/http anywhere in `love_risk_engine/`); the only
  IO is the local SQLite file and local chat-export files the user chooses.
- **No drift from the rejected pitch** ✅ — no reply coaching, no numeric
  power/exit indices, no rebrand, no factory/plugin over-architecture.

## 5. Data safety audit

**Strong:** local SQLite only; `PRAGMA foreign_keys = ON`; minimal PII by
schema design (alias + free text the user chooses; no phone/ID/address fields);
append-only history with audit trails (override log, resolution notes,
boundary retirement).

**Gaps — the weakest dimension:**

1. **No export/backup command** (issue D1, P1). The database is the user's only
   copy of potentially sensitive, long-horizon records. A lost file is a total
   loss; there is currently no `lre export`, no backup guidance in README.
2. **Default DB path is the working directory** (issue D2, P1).
   `Database("love_risk.db")` resolves against wherever `lre` was invoked — the
   same alias can silently span multiple databases. A user-data-directory
   default (with `LRE_DB_PATH` still overriding) would make "my data" a single,
   discoverable place.
3. **No integrity-check command** (issue D3, P2). `PRAGMA integrity_check` is
   one command away but not exposed; cheap insurance to pair with export.
4. **No config file** (issue D4, P2 — deliberate). Env vars only
   (`LRE_DB_PATH`, `LRE_COOLDOWN_HOURS`). Keeping it env-only is a defensible
   choice for a stdlib CLI; the architecture doc fixes the decision so it
   doesn't drift by accident.

## 6. Functional coverage vs roadmap

**Implemented** (all test-first, contracts in `docs/proposals/`): contradiction
tracker + three-state resolution, quality-calibrated evidence support,
cheap/costly signals, love-bombing, cooldown/precommitment, timeline, chat
import, relationship kinds & profiles (S1–S3), promise expiry, exit-cost
sensitivity, state/exposure change history, rapid exposure escalation.

**Reconciled this session** — the old README roadmap contained items that
conflict with the project's own principles. They are re-decided explicitly in
`ARCHITECTURE_AND_PLAN.md` §"Roadmap reconciliation": LLM Devil's Advocate
(depends on an LLM — rejected), Bayesian updater / real-option / optimal
stopping (pseudo-precision risk — deferred behind a calibration strategy that
is honest about lacking data), relationship backtesting (needs labeled data —
deferred), public-information consistency check (privacy conflict — rejected).

**Still canonical:** counterfactual review / RedTeamMe, mutual verification
checklist, calibration report, presentation layer (CLI-first; adapter
boundary defined, UI form factor gated).

## 7. Community benchmark

The full scan — 10 verified projects across four camps, plus the **pi agent**
architecture study — lives in `RESEARCH_COMMUNITY.md`. Headline finding: the
intersection of *relationship risk detection + local CLI + non-judging tone*
is unoccupied; every camp does only one of the three.

Key takeaways, folded into the architecture:

1. **Freshness self-check** (Bonds' `needs-verification` flag) → the mutual
   verification checklist (roadmap #3).
2. **Append-only + `Supersedes:` + decide/assume/escalate** (log-decisions,
   adr-tools) → formalizes our retire-not-delete semantics and the
   "signal → transparent presentation → user adjudication" UX.
3. **Public non-diagnostic instruments + boundary statements** (MindWell) →
   how each detector documents itself as explainable and non-diagnostic.
4. **File-as-truth + permission layering** (pi) → data-home default, lossless
   export, and the read-only-by-default agent-integration gate.

The anti-model is Texts with My Ex: detection value is real, but cloud upload
of private chats, opaque thresholds and alarm framing are the three things we
refuse — that contrast *is* the positioning.

## 8. Issue register

| # | Sev | Issue | Disposition |
|---|---|---|---|
| D1 | P1 | No export/backup command; DB is a single point of loss | **Implemented** — `lre export`/`restore` (SHA-256 bundle, lossless round-trip tested) |
| D2 | P1 | Default DB path = CWD; data not discoverable | **Implemented** — platform data dir + legacy CWD fallback + `LRE_DB_PATH` |
| R1 | P2 | `pyproject.toml` version 0.1.0 stale | **Implemented** — 0.3.0 (phase 2) |
| R2 | P2 | pre-commit lacks the mypy hook | **Implemented** — mypy hook added (phase 2) |
| D3 | P2 | No `PRAGMA integrity_check` surface | **Implemented** — `lre db check` (integrity + foreign-key) |
| D4 | P2 | Config = env vars only | decision fixed in architecture doc |
| E1 | P2 | Detector thresholds uncalibrated | strategy in `ARCHITECTURE_AND_PLAN.md` §4; **data generator delivered** — counterfactual review (phase 2) |
| E2 | P3 | Chat import collapses same-second messages | **Implemented** — source timestamps preserved (phase 3) |
| E3 | P3 | No shell completion / man page | **Implemented** — `lre completion` + runtime engine (phase 3; man page not built — completion covers discovery) |
| S1 | P2 | Roadmap incoherence (old README list) | resolved by `ARCHITECTURE_AND_PLAN.md` |
| I1 | P2 | UI is English-only | **Implemented** — i18n via stdlib catalog (`LRE_LANG=zh`), display-time localization, canonical English persisted |
| I2 | P3 | Plain-text CLI output | **Implemented** — optional `rich` presentation (`pretty` extra, soft import, plain fallback) |
| D5 | P2 | Docs drift from code (detector counts, test counts, stale roadmaps) | **Implemented** — hard numbers purged or pin-guarded by `tests/test_docs.py` (invariant #11) |
| C1 | P2 | Detector thresholds uncalibrated; no evaluation data | **Measurement phase implemented** — `lre evaluate` labels + `lre calibration` honest per-rule counts (schema v5); threshold overrides deferred until labeled data exists |
| C2 | P3 | No open-source license | **Implemented** — Apache-2.0 `LICENSE` + `pyproject` license field |

**No P0 issues found.** The P1s are data-safety items and are the first thing
the optimization plan discharges.
