# LoveRiskEngine — Target Architecture & Optimization Plan

> Date: 2026-09-01 · This document is the **canonical architecture**. Any
> future change that conflicts with §1 (invariants) or §2 (module boundaries)
> must amend this document *first* — proposal → review → code. That rule, not
> discipline, is what keeps engineering debt out.
> It discharges every issue in `AUDIT_REPORT.md` §8 and incorporates the
> community scan (`RESEARCH_COMMUNITY.md`, including the pi agent study).

## 1. Architectural invariants (the anti-debt contract)

Every slice from here on must hold these ten. A violation is a defect, not a
style preference:

1. **`core/` is pure.** No IO except time; never imports `storage`, `services`,
   `cli`, or any network module. Privacy is the product — a CI guard test
   fails the build if a network import ever appears (phase 1).
2. **`storage/` returns domain objects only.** Schema changes happen only as
   versioned migrations with tested upgrade paths (v0→v3 precedent).
3. **Presentation is an adapter, never logic.** `cli.py` formats and routes;
   no rule, threshold, or decision logic may live there. A future TUI/Web
   consumes the same `services/` — additive, never a rewrite.
4. **Honest numerics.** Ordinals + placeholders labeled "uncalibrated"; no
   pseudo-precise scores; calibration is only permitted on data we actually
   have (see §4).
5. **The user decides.** Nothing auto-sets; EXIT requires a recorded
   hard-boundary hit; overrides are audited; boundary seeds are suggestions.
6. **Append-only data.** Rows are never deleted or rewritten; display
   windowing is presentation-only; export must be lossless. (Deliberate
   divergence from pi's lossy compaction: audit integrity outranks token
   savings here.)
7. **Zero runtime dependencies.** Stdlib-only is a reviewable property; any
   future dependency needs a written justification in a proposal.
   *(Amended 2026-09-01, i18n/rich phase: `rich` is an **optional**
   presentation dependency — soft-imported with a plain-text fallback;
   engine, storage and all logic remain stdlib-only. The required-runtime
   dependency count stays zero. i18n is stdlib-only by design — a msgid
   catalog, no gettext toolchain.)*
8. **Test-first + four gates.** New behavior ships with failing tests first;
   ruff / format / mypy / pytest green; coverage ≥ 95%; `cli.py` 100%.
9. **Config layering, one data home.** Global data dir > env > defaults; one
   database per user, discoverable (phase 1). Adopted from pi's
   global-vs-project layering, simplified for a single-user CLI.
10. **Docs as contracts.** Every slice keeps its proposal/plan in
    `docs/proposals/`; this document is amended before deviation, and
    `AUDIT_REPORT.md` carries the live issue register.

## 2. Target module architecture

```
love_risk_engine/
  cli.py            presentation adapter #1 (argparse — thin, format-only)
  core/             PURE domain + detectors (no DB, no CLI, no network)
    relationship/observation/state/exposure/boundaries/inconsistency/
    review/cooldown/override/history/signals          domain objects
    profiles                                          editorial config
    bias_detector/patterns/signals/promises/
    escalation/contradiction/evidence                 detectors
  services/         orchestration (owns storage access)
    review.py       (existing review workflow)
    export.py       phase 1 — lossless export/restore bundle
  storage/          SQLite + versioned migrations; domain objects only
  adapters/         (gated, planned) tui/ or web/ — consume services only
examples/ tests/ docs/
```

**Dependency rule:** `cli` → `services` → {`core`, `storage`}; `adapters` →
`services`; `storage` → `core`; `core` → nothing internal. Compile-time
checkable and test-enforced (phase 1 guard test).

## 3. Data layer design

- **One discoverable database.** Default path moves from CWD to the platform
  data dir (Windows `%LOCALAPPDATA%\LoveRiskEngine`, macOS
  `~/Library/Application Support/LoveRiskEngine`, Linux `$XDG_DATA_HOME`),
  `LRE_DB_PATH` still overrides. Fixes audit issue D2: "my data" becomes a
  single, findable place.
- **Lossless export/restore** (`lre export <file>` / `lre restore <file>`):
  a JSON bundle of every table + schema version + SHA-256 checksum. Export
  *is* the backup and the interchange format — one mechanism, not two. This
  is the pi lesson applied: the file is the truth, readable and versionable.
  Fixes D1.
- **Integrity** (`lre db check`): `PRAGMA integrity_check` + foreign-key
  check, paired with export in docs. Fixes D3.
- **Config** stays env-only until a concrete need exists; if one appears, a
  TOML file via stdlib `tomllib` under the same layering — still zero
  dependencies. Fixes D4 by decision, not drift.
- **No compaction, no pruning.** History grows; that is the point.

## 4. Engine roadmap (calibrated honesty)

- **Calibration strategy (issue E1):** never fake it. The only honest path is
  personal: (1) keep thresholds labeled placeholders; (2) ship counterfactual
  review (below), which produces *user-labeled* decision outcomes locally;
  (3) only then may thresholds be tuned against that user's own data — a
  personal calibration, still never presented as probability.
- **Counterfactual review / RedTeamMe (roadmap #2):** re-run a past decision
  against only the evidence available at that time. Audit your own
  rationalization; feeds the calibration pipeline.
- **Mutual verification checklist (roadmap #3):** user-curated verifiable
  facts whose costly-signal status can be confirmed — sharpens the
  cheap-talk/costly-signal boundary.
- **Promise re-promise counting:** the known S2 limitation (repeated
  re-promising restarts the window without counting) — small, bounded slice.

### Roadmap reconciliation (nothing dies silently)

Items from the pre-audit README roadmap that conflict with the invariants are
re-decided here, permanently:

| Old item | Decision | Reason |
|---|---|---|
| LLM Devil's Advocate | **Rejected** | Depends on an LLM — violates local-only, zero-dep, honest-numerics |
| Bayesian updater, value-of-information, real-option/optimal-stopping | **Deferred behind §4 calibration** | Pseudo-precision risk; admissible only on real labeled data |
| Relationship backtesting | **Deferred** | Needs labeled outcomes — same gate as calibration |
| Public-information consistency check | **Rejected** | Privacy conflict with "no scraping/lookup of people" |

## 5. Presentation & future integration (gated, not debt)

- **CLI-first remains the product.** The adapter boundary (§2) means any UI
  later is additive.
- **UI form-factor gate:** build order is (1) phase 1 data safety, (2) the
  decision itself — TUI (terminal, pi-style keyboard-first minimalism) vs
  Web (the `docs/DESIGN.md` token system already exists for it). The design
  system is form-factor-agnostic; the calm-instrument tone carries over
  either way. **Decision belongs to the user and is not required for any
  phase-1 work.**
- **Agent-ecosystem integration (from the pi study):** if the engine is ever
  consumed by coding agents, the recorded shape is pi's — expose a *minimal*
  tool surface (read relationships, append observations, run review), default
  read-only, project-level trust gate, every call observable via an
  `on(tool_call)`-style audit hook. Assets (profiles, boundaries, plans) stay
  versioned files under one data home. This is recorded now so a future
  integration cannot skip the permission boundary; nothing is built until the
  core UX is done.

## 6. Testing & CI policy

- Keep: TDD, four gates, 95% floor, `cli.py` 100%, CI matrix 3.11–3.13.
- Add (phase 1–2): **no-network-import guard test** (invariant #1,
  executable); **mypy hook in pre-commit** (issue R2); import-order and
  boundary guard test for §2 (optional but cheap).
- Coverage exclusions stay reviewable: `hooks.py` / `evidence.py` precedent —
  re-justified whenever the files are touched.

## 7. Versioning & release policy

- Package semver and `PRAGMA user_version` are independent; both bump per
  policy. Next release moves `pyproject.toml` 0.1.0 → **0.3.0** (kinds +
  promise expiry + sensitivity + history + escalation landed; export/restore
  in phase 1 lands in the same or the following minor). Fixes R1.
- `docs/overview.md` remains the built-list; `docs/proposals/` remains the
  why-log; this doc remains the target.

## 8. Phased optimization plan

| Phase | Scope (discharges register items) | Acceptance criteria |
|---|---|---|
| **0 — hygiene** *(done this session)* | docs structure, README de-staling, pre-commit installed & verified, audit + this doc | gates green; issue register published |
| **1 — data safety** *(done 2026-09-01)* | D2 data-home default; D1 export/restore + checksum; D3 `lre db check`; network-import guard test; backup guidance in README | export→restore round-trip lossless; 275 tests; `cli.py`/`export.py`/`paths.py` 100%; gates green |
| **2 — rigor** *(done 2026-09-01)* | R2 mypy pre-commit hook; R1 version bump; E1 calibration strategy + counterfactual review (roadmap #2); mutual verification checklist (roadmap #3); promise re-promise counting | 314 tests; `cli.py` / `counterfactual.py` 100%; gates green |
| **3 — UX & surface** *(done 2026-09-01, except UI)* | shell completion (`lre completion` + runtime engine); E2 chat-import ordering; **UI form-factor decision deferred by the user**; config file skipped (no concrete need appeared) | 328 tests; `cli.py` 100%; gates green |

**Debt policy:** nothing ships "temporarily" without a register entry
(`AUDIT_REPORT.md` §8) plus a doc note; every slice ends with the register
updated; this document is re-audited quarterly or whenever an invariant is
tempted.
