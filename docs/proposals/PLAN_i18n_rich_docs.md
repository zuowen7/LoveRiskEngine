# Implementation Plan — i18n (中文适配) + rich Output + Docs

> Status: **the implementation contract for the localization & polish phase.**
> Two architecture decisions are made here and amend
> `ARCHITECTURE_AND_PLAN.md` (recorded there at the end of this phase):
>
> 1. **i18n stays stdlib-only.** A msgid-keyed catalog in `core/i18n.py` —
>    no gettext/.po toolchain, no new dependency (invariant #7 untouched).
> 2. **rich is an *optional* presentation dependency.** Soft import with a
>    plain-text fallback: the engine, storage and logic remain stdlib-only;
>    rich only prettifies what `cli.py` already renders. Invariant #7 is
>    amended, not broken — "no *required* runtime dependency".
>
> Test-first throughout.

## 1. Scope boundary

| In scope | Out of scope (documented honestly) |
|---|---|
| Detector finding messages (all 12 variants) via `msg_key` + params, localized **at display** | Persisted review notes — canonical English (they are evidence records) |
| CLI chrome: help texts, command outputs, errors, status/timeline/history section labels | Contradiction-tracker explanation lines and timeline event bodies (evidence records); history delta notation; user data |
| `LRE_LANG` env var (`en` default, `zh` Chinese) | Per-word or DB-persisted language settings; other languages |
| rich rendering of `status` / `review` / warnings (calm, DESIGN.md colors) | Rich in core/detectors; hard dependency |
| `README_zh.md` + `docs/getting-started.en.md` + `docs/getting-started.zh.md` | Rewriting the English README |

## 2. i18n design

- `core/i18n.py`: `Language` StrEnum, `current_language()` (env `LRE_LANG`,
  unknown → `en` — fail-open), `CATALOG: dict[str, dict[Language, str]]`,
  `t(msgid, **kwargs)` (`.format` placeholders; missing key falls back to
  English, then to the msgid itself — never crashes).
- `BiasFinding` gains `msg_key: str = ""` and `msg_params: dict[str, object]`
  (defaults keep every existing construction valid). Detectors keep building
  the canonical English `message` (persisted) **and** attach key/params.
  Display sites use `localize_finding(finding)`.
- Display sites: `format_status` warnings, `cmd_review` hook list/notes stays
  English-by-design (notes are records), `cmd_counterfactual` finding line,
  and every static label in `format_status`.
- All static CLI strings move to `t("msgid")` — help texts resolve at
  `build_parser()` time (per-invocation), so `LRE_LANG=zh lre --help` works.

## 3. rich design (optional dependency)

- `pyproject.toml`: `[project.optional-dependencies] pretty = ["rich==…"]`
  (pinned); dev extras include it so tests exercise the rich path; runtime
  `dependencies` stays `[]`.
- `cli.py`: `try: from rich.console import Console  # optional presentation
  except ImportError: Console = None`. Rendering helpers keep the *text*
  unchanged (all existing assertions keep passing) and add restrained
  presentation: status in a Panel, warnings in amber, EXIT in red, section
  headers bold — nothing animated, nothing gradient (DESIGN.md).
- Plain-text fallback is the same code path minus Console.

## 4. Docs

- `README_zh.md`: full Chinese README (定位、原则、安装、用法、备份、补全),
  linked from `README.md`.
- `docs/getting-started.en.md` / `docs/getting-started.zh.md`: install,
  first relationship, daily loop (observe → review → history), backup,
  language switch, completion, FAQ.

## 5. TDD test list (written first, red, then green)

`tests/test_i18n.py` (new):

1. `test_current_language_defaults_to_en` / `zh` env / unknown env → en
2. `test_t_placeholder_substitution`
3. `test_t_falls_back_to_msgid_for_unknown_key` (never crashes)
4. `test_catalog_has_both_languages_for_every_key`
5. `test_localize_finding_uses_key` / falls back to `.message`

`tests/test_bias.py` / `test_promises.py` / `test_escalation.py`:

6. every fired finding carries a non-empty `msg_key` (parametrized across the
   detector test fixtures)

`tests/test_cli_commands.py`:

7. `test_status_labels_localize_to_chinese` (`LRE_LANG=zh`: 「建议」「警告」…)
8. `test_help_localizes_to_chinese` (`lre --help` contains 「用法」)
9. `test_review_warning_localizes_to_chinese`
10. `test_english_is_default_and_unchanged` (default output still English)
11. `test_rich_path_renders_same_content` (rich installed in dev; output
    text substrings unchanged)

`tests/test_completion.py`:

12. completion candidates unchanged under `LRE_LANG=zh` (language never
    affects the command surface)

## 6. TDD order

1. Write tests 1–12 → red.
2. `core/i18n.py` + `BiasFinding` fields → unit green.
3. Detectors attach key/params (catalog entries pinned by tests) → green.
4. CLI chrome via `t()` + display localization → CLI tests green.
5. rich soft import + rendering helpers → green.
6. Docs (README_zh + getting-started ×2) — content work, no tests.
7. Four-gate + coverage; amend `ARCHITECTURE_AND_PLAN.md` (invariant #7
   amendment + phase-4 note), register in `AUDIT_REPORT.md`. Commit, push,
   watch CI.
