"""Internationalization (stdlib-only, zero dependencies).

Design (docs/proposals/PLAN_i18n_rich_docs.md):
  - Canonical strings stay English **in the database** — findings persisted
    to review notes are evidence records and are never rewritten. Translation
    happens at display time only.
  - Language selection: `LRE_LANG` env var (`en` default, `zh` Chinese);
    unknown values fail open to English.
  - The catalog is msgid-keyed with `{named}` placeholders via `str.format`.
    Missing keys fall back to English, then to the msgid itself — display
    must never crash on a translation gap.

Known v1 boundaries (documented, deliberate): contradiction-tracker
explanation lines, timeline event bodies, history delta notation and user
data stay as recorded — they are evidence, not chrome.
"""

from __future__ import annotations

import os
from enum import StrEnum


class Language(StrEnum):
    EN = "en"
    ZH = "zh"


def current_language() -> Language:
    value = os.environ.get("LRE_LANG", "en").strip().lower()
    if value in ("zh", "zh_cn", "zh-cn", "chinese", "中文"):
        return Language.ZH
    return Language.EN


# msgid -> {Language: template}. English templates match the canonical strings
# exactly (existing English output and tests are unchanged).
CATALOG: dict[str, dict[Language, str]] = {
    # --- detector findings (display-time localization via msg_key/params) ---
    "attraction_exceeds_trust": {
        Language.EN: "Attraction ({attraction}) significantly exceeds supported trust ({trust}).",
        Language.ZH: "吸引力（{attraction}）显著高于有证据支撑的信任（{trust}）。",
    },
    "attraction_exceeds_trust_sensitive": {
        Language.EN: "Attraction ({attraction}) significantly exceeds supported trust ({trust}) (exit-cost sensitive: gap threshold {gap}).",
        Language.ZH: "吸引力（{attraction}）显著高于有证据支撑的信任（{trust}）（高退出成本敏感：差距阈值 {gap}）。",
    },
    "repeated_rationalization": {
        Language.EN: "{count} consecutive rationalizations detected.",
        Language.ZH: "检测到连续 {count} 次合理化。",
    },
    "repeated_rationalization_sensitive": {
        Language.EN: "{count} consecutive rationalizations detected (exit-cost sensitive: run threshold {threshold}).",
        Language.ZH: "检测到连续 {count} 次合理化（高退出成本敏感：连续阈值 {threshold}）。",
    },
    "exposure_outpaces_evidence": {
        Language.EN: "Exposure ({total}) outpaces current evidence support ({units} units from {count} observations, {sources} source(s)).",
        Language.ZH: "风险敞口（{total}）超出当前证据支撑（来自 {count} 条观察、{sources} 个来源，共 {units} 单位）。",
    },
    "exposure_within_support": {
        Language.EN: "Exposure remains within evidence support ({units} units; {alt}/{count} with alternative explanations, {claims}/{count} with claims).",
        Language.ZH: "风险敞口仍在证据支撑之内（{units} 单位；{alt}/{count} 条含替代解释，{claims}/{count} 条含结构化声明）。",
    },
    "exposure_empty_evidence": {
        Language.EN: "No observations recorded yet; evidence base is empty.",
        Language.ZH: "尚未记录任何观察；证据库为空。",
    },
    "high_emotion_major_decision": {
        Language.EN: "High emotional state while considering a major life decision.",
        Language.ZH: "在考虑重大人生决定时处于高情绪状态。",
    },
    "unresolved_inconsistencies": {
        Language.EN: "{count} unresolved inconsistencies.",
        Language.ZH: "{count} 个未解决的矛盾。",
    },
    "love_bombing_pattern": {
        Language.EN: "Possible love-bombing pattern in early window ({n} observations): {cheap} cheap-talk + {costly} costly signals compressed early. Pause before raising exposure; do not convict on a pattern alone.",
        Language.ZH: "早期窗口（{n} 条观察）可能出现「爱情轰炸」模式：{cheap} 条廉价话语 + {costly} 条昂贵信号密集出现。请暂停提升敞口；不要仅凭模式定罪。",
    },
    "promise_expiry": {
        Language.EN: "{count} promise claim(s) untouched for > {window} days: {details}.",
        Language.ZH: "{count} 条承诺声明超过 {window} 天未被触及：{details}。",
    },
    "repeated_repromises": {
        Language.EN: "{total} promise re-mention(s) within {window} days: {details}.",
        Language.ZH: "{window} 天内出现 {total} 次重复承诺：{details}。",
    },
    "rapid_exposure_escalation": {
        Language.EN: "Exposure grew {delta} points in the last {window} days ({baseline} -> {current}) with no new observations recorded in that window.",
        Language.ZH: "风险敞口在过去 {window} 天内上升了 {delta} 分（{baseline} -> {current}），而该窗口内没有任何新观察记录。",
    },
    # --- status layout ---
    "relationship_header": {
        Language.EN: "Relationship: {rid}",
        Language.ZH: "关系：{rid}",
    },
    "kind_line": {
        Language.EN: "Kind             {kind}",
        Language.ZH: "类型             {kind}",
    },
    "context_line": {
        Language.EN: "Context          {context}",
        Language.ZH: "上下文          {context}",
    },
    "context_power": {
        Language.EN: "power asymmetry: {v}",
        Language.ZH: "权力不对称：{v}",
    },
    "context_exit": {Language.EN: "exit cost: {v}", Language.ZH: "退出成本：{v}"},
    "attraction_metric": {
        Language.EN: "Attraction       {v} / 10",
        Language.ZH: "吸引力           {v} / 10",
    },
    "trust_metric": {
        Language.EN: "Trust            {v} / 10",
        Language.ZH: "信任             {v} / 10",
    },
    "uncertainty_metric": {
        Language.EN: "Uncertainty      {v} / 10",
        Language.ZH: "不确定性         {v} / 10",
    },
    "emotional_metric": {
        Language.EN: "Emotional        {v}",
        Language.ZH: "情绪             {v}",
    },
    "exposure_header": {Language.EN: "Exposure", Language.ZH: "风险敞口"},
    "exposure_time": {
        Language.EN: "  Time           {v}",
        Language.ZH: "  时间           {v}",
    },
    "exposure_emotional": {
        Language.EN: "  Emotional      {v}",
        Language.ZH: "  情绪           {v}",
    },
    "exposure_privacy": {
        Language.EN: "  Privacy        {v}",
        Language.ZH: "  隐私           {v}",
    },
    "exposure_financial": {
        Language.EN: "  Financial      {v}",
        Language.ZH: "  财务           {v}",
    },
    "exposure_life": {
        Language.EN: "  Life decision  {v}",
        Language.ZH: "  重大决定       {v}",
    },
    "evidence_header": {Language.EN: "Evidence support", Language.ZH: "证据支撑"},
    "evidence_observations": {
        Language.EN: "  Observations   {n}",
        Language.ZH: "  观察记录       {n}",
    },
    "evidence_sources": {
        Language.EN: "  Sources        {n}",
        Language.ZH: "  来源           {n}",
    },
    "evidence_alt": {
        Language.EN: "  w/ Alt expl.   {n}",
        Language.ZH: "  含替代解释     {n}",
    },
    "evidence_claims": {
        Language.EN: "  w/ Claims      {n}",
        Language.ZH: "  含结构化声明   {n}",
    },
    "evidence_costly": {
        Language.EN: "  Costly signals {n}",
        Language.ZH: "  昂贵信号       {n}",
    },
    "evidence_cheap": {
        Language.EN: "  Cheap talk     {n}",
        Language.ZH: "  廉价话语       {n}",
    },
    "evidence_units": {
        Language.EN: "  Support units  {v}",
        Language.ZH: "  支撑单位       {v}",
    },
    "warnings_header": {Language.EN: "Warnings:", Language.ZH: "警告："},
    "none_dash": {Language.EN: "- None.", Language.ZH: "- 无。"},
    "unresolved_count": {
        Language.EN: "Unresolved inconsistencies: {n}",
        Language.ZH: "未解决的矛盾：{n}",
    },
    "acknowledged_line": {
        Language.EN: "Acknowledged (closed): {n} ({parts})",
        Language.ZH: "已了结（关闭）：{n}（{parts}）",
    },
    "verified_facts": {
        Language.EN: "Verified facts: {v} of {t}",
        Language.ZH: "已验证事实：{v} / {t}",
    },
    "conflicts_header": {
        Language.EN: "Conflicting claims (top):",
        Language.ZH: "冲突声明（前几项）：",
    },
    "conflicts_more": {
        Language.EN: "  ...run `lre contradictions <rel> --save` to persist all.",
        Language.ZH: "  ...运行 `lre contradictions <关系> --save` 保存全部。",
    },
    "promises_header": {
        Language.EN: "Promises (window: {w}d)",
        Language.ZH: "承诺（窗口：{w} 天）",
    },
    "older_promises": {
        Language.EN: "Older promises ({n}): run `lre promises <rel>` for details.",
        Language.ZH: "更早的承诺（{n} 条）：运行 `lre promises <关系>` 查看详情。",
    },
    "recommendation_label": {Language.EN: "Recommendation:", Language.ZH: "建议："},
    "context_label": {
        Language.EN: "Context: {context}",
        Language.ZH: "上下文：{context}",
    },
    # --- profile voice lines (msgid = the canonical English voice text) ---
    "maintain explicit boundaries": {
        Language.EN: "maintain explicit boundaries",
        Language.ZH: "保持明确的边界",
    },
    "verify promises before escalating": {
        Language.EN: "verify promises before escalating",
        Language.ZH: "升级前先核实承诺",
    },
    "track promises; verify before escalating": {
        Language.EN: "track promises; verify before escalating",
        Language.ZH: "追踪承诺；升级前先核实",
    },
    "separate work claims from evidence": {
        Language.EN: "separate work claims from evidence",
        Language.ZH: "把工作声明与证据分开",
    },
    "low familiarity: prefer verification": {
        Language.EN: "low familiarity: prefer verification",
        Language.ZH: "熟悉度低：优先核实",
    },
    # --- command outputs ---
    "init_done": {
        Language.EN: "Initialized LoveRiskEngine database at {path}",
        Language.ZH: "已初始化 LoveRiskEngine 数据库：{path}",
    },
    "relationship_created": {
        Language.EN: "Created relationship {id} (alias: {alias}, kind: {kind})",
        Language.ZH: "已创建关系 {id}（别名：{alias}，类型：{kind}）",
    },
    "seed_boundaries_header": {
        Language.EN: "Suggested boundaries for this kind (add only what matches you):",
        Language.ZH: "该关系类型的建议边界（只添加符合你的）：",
    },
    "kind_set": {
        Language.EN: "Set kind {kind} for {id}",
        Language.ZH: "已将 {id} 的类型设为 {kind}",
    },
    "signal_hint": {
        Language.EN: "(hint) observation text suggests signal type {type}. Use --signal-type to confirm or override.",
        Language.ZH: "（提示）观察文本暗示信号类型为 {type}。可用 --signal-type 确认或覆盖。",
    },
    "observation_recorded": {
        Language.EN: "Recorded observation {id} for {rel}{extra}",
        Language.ZH: "已记录观察 {id}（关系 {rel}）{extra}",
    },
    "boundary_added": {
        Language.EN: "Added boundary {id}: {desc} [{sev}]",
        Language.ZH: "已添加边界 {id}：{desc} [{sev}]",
    },
    "boundary_hit_recorded": {
        Language.EN: "Recorded boundary hit {id} (boundary {bid}, relationship {rid})",
        Language.ZH: "已记录边界命中 {id}（边界 {bid}，关系 {rid}）",
    },
    "boundary_retired": {
        Language.EN: "Retired boundary {id}. Past hits remain in the audit trail; `lre list` still shows it as inactive.",
        Language.ZH: "已退役边界 {id}。过往命中保留在审计轨迹中；`lre list` 仍会显示它为停用。",
    },
    "list_relationships": {Language.EN: "Relationships:", Language.ZH: "关系列表："},
    "list_boundaries": {Language.EN: "Boundaries:", Language.ZH: "边界列表："},
    "list_none": {Language.EN: "  (none)", Language.ZH: "  （无）"},
    "list_active": {Language.EN: "ACTIVE", Language.ZH: "启用"},
    "list_inactive": {Language.EN: "inactive", Language.ZH: "停用"},
    "state_updated": {
        Language.EN: "Updated state for {rid}",
        Language.ZH: "已更新 {rid} 的状态",
    },
    "exposure_updated": {
        Language.EN: "Updated exposure for {rid} (total {old} -> {new})",
        Language.ZH: "已更新 {rid} 的风险敞口（总计 {old} -> {new}）",
    },
    "cooldown_blocked": {
        Language.EN: "BLOCKED: an active cooldown prevents raising exposure.",
        Language.ZH: "已拦截：有生效中的冷却期，禁止提升风险敞口。",
    },
    "cooldown_line": {
        Language.EN: "  - {id} [{decision}] {remaining} (reason: {reason})",
        Language.ZH: "  - {id} [{decision}] {remaining}（原因：{reason}）",
    },
    "cooldown_override_hint": {
        Language.EN: 'To override (logged for audit): lre exposure set {rel} ... --override --reason "..."',
        Language.ZH: '如需覆盖（会记录审计日志）：lre exposure set {rel} ... --override --reason "..."',
    },
    "override_logged": {
        Language.EN: "OVERRIDE logged: raising exposure {old} -> {new} during cooldown. This is recorded in your audit log.",
        Language.ZH: "已记录覆盖：在冷却期内将敞口从 {old} 提升到 {new}。此操作已写入审计日志。",
    },
    "inconsistency_recorded": {
        Language.EN: "Recorded inconsistency {id} for {rid}",
        Language.ZH: "已记录矛盾 {id}（关系 {rid}）",
    },
    "inconsistency_resolve_done": {
        Language.EN: "Resolved inconsistency {id} as {res}",
        Language.ZH: "已按「{res}」了结矛盾 {id}",
    },
    "inconsistency_list_header": {
        Language.EN: "{label} inconsistencies for {rid}:",
        Language.ZH: "关系 {rid} 的{label}矛盾：",
    },
    "inconsistency_none": {Language.EN: "  (none)", Language.ZH: "  （无）"},
    "no_contradictions": {
        Language.EN: "No contradictions detected for {rid}.",
        Language.ZH: "未在 {rid} 中检测到冲突。",
    },
    "contradictions_saved": {
        Language.EN: "Saved {n} new contradiction(s) as inconsistencies. Resolve with: lre inconsistency resolve <id>",
        Language.ZH: "已将 {n} 个新冲突保存为矛盾。用以下命令了结：lre inconsistency resolve <id>",
    },
    "chat_file_missing": {
        Language.EN: "Error: chat file not found: {file}",
        Language.ZH: "错误：找不到聊天文件：{file}",
    },
    "chat_parse_error": {
        Language.EN: "Error: could not parse {file}: {err}",
        Language.ZH: "错误：无法解析 {file}：{err}",
    },
    "chat_no_messages": {
        Language.EN: "No messages parsed from {file}.",
        Language.ZH: "未能从 {file} 解析出任何消息。",
    },
    "chat_imported": {
        Language.EN: "Imported {n} observation(s) from {file} into {rid}.",
        Language.ZH: "已从 {file} 导入 {n} 条观察到 {rid}。",
    },
    "chat_claims": {
        Language.EN: "Extracted {n} structured claim(s) via {m} rule(s).",
        Language.ZH: "通过 {m} 条规则提取了 {n} 条结构化声明。",
    },
    "chat_conflicts": {
        Language.EN: "Detected {n} potential contradiction(s). Review with: lre contradictions {rel} --save",
        Language.ZH: "检测到 {n} 个潜在冲突。用以下命令复核：lre contradictions {rel} --save",
    },
    "chat_clean": {
        Language.EN: "No contradictions detected in imported claims.",
        Language.ZH: "导入的声明中未检测到冲突。",
    },
    "timeline_header": {
        Language.EN: "Timeline for {rid} ({n} event(s)):",
        Language.ZH: "{rid} 的时间线（{n} 个事件）：",
    },
    "timeline_empty": {
        Language.EN: "(no timestamped events yet)",
        Language.ZH: "（还没有带时间戳的事件）",
    },
    "cooldowns_cleared": {
        Language.EN: "Cleared {n} active cooldown(s) for {rid}.",
        Language.ZH: "已清除 {rid} 的 {n} 个生效中的冷却期。",
    },
    "cooldowns_header": {
        Language.EN: "Active cooldowns for {rid}:",
        Language.ZH: "{rid} 生效中的冷却期：",
    },
    "overrides_header": {
        Language.EN: "Override history ({n}):",
        Language.ZH: "覆盖历史（{n} 条）：",
    },
    "history_empty": {
        Language.EN: "No state or exposure changes recorded yet.",
        Language.ZH: "还没有状态或敞口变更记录。",
    },
    "history_header": {
        Language.EN: "History for {rid}:",
        Language.ZH: "{rid} 的变更历史：",
    },
    "promises_no_window": {
        Language.EN: "Kind {kind} does not track a promise window.",
        Language.ZH: "类型 {kind} 不追踪承诺窗口。",
    },
    "promises_none": {
        Language.EN: "No promise claims recorded.",
        Language.ZH: "没有记录的承诺声明。",
    },
    "promises_cmd_header": {
        Language.EN: "Promises for {rid} (window: {w}d):",
        Language.ZH: "{rid} 的承诺（窗口：{w} 天）：",
    },
    "promises_within": {Language.EN: "Within window:", Language.ZH: "窗口内："},
    "promises_expired": {
        Language.EN: "Expired ({n}):",
        Language.ZH: "已过期（{n} 条）：",
    },
    "export_exists": {
        Language.EN: "Error: {file} already exists — refusing to overwrite.",
        Language.ZH: "错误：{file} 已存在——拒绝覆盖。",
    },
    "export_done": {
        Language.EN: "Exported {n} row(s) from {m} table(s) to {file} (sha256 {sha}).",
        Language.ZH: "已导出 {m} 张表的 {n} 行到 {file}（sha256 {sha}）。",
    },
    "restore_error": {
        Language.EN: "Error: cannot restore from {file}: {err}",
        Language.ZH: "错误：无法从 {file} 恢复：{err}",
    },
    "restore_done": {
        Language.EN: "Restored {n} row(s) from {file}.",
        Language.ZH: "已从 {file} 恢复 {n} 行。",
    },
    "db_ok": {Language.EN: "Database OK ({path})", Language.ZH: "数据库完好（{path}）"},
    "db_problem": {
        Language.EN: "Database problem: {detail}",
        Language.ZH: "数据库问题：{detail}",
    },
    "db_fk_violation": {
        Language.EN: "  foreign-key violation: table={table} rowid={rowid} parent={parent}",
        Language.ZH: "  外键违规：表={table} 行={rowid} 父行={parent}",
    },
    "db_check_failed": {
        Language.EN: "Database integrity check failed.",
        Language.ZH: "数据库完整性检查未通过。",
    },
    "verify_added": {
        Language.EN: "Added verification item {id} for {rid}: {item} [unverified]",
        Language.ZH: "已为 {rid} 添加验证项 {id}：{item} [未验证]",
    },
    "verify_none": {
        Language.EN: "No verification items for {rid}.",
        Language.ZH: "{rid} 还没有验证项。",
    },
    "verify_header": {
        Language.EN: "Verification items for {rid}:",
        Language.ZH: "{rid} 的验证项：",
    },
    "verify_checked": {
        Language.EN: "Marked {id} as verified.",
        Language.ZH: "已将 {id} 标记为已验证。",
    },
    "verify_failed": {
        Language.EN: "Marked {id} as failed.",
        Language.ZH: "已将 {id} 标记为不成立。",
    },
    "evaluate_done": {
        Language.EN: "Labeled review {id} as {outcome}.",
        Language.ZH: "已将复盘 {id} 标记为「{outcome}」。",
    },
    "calibration_header": {
        Language.EN: "Calibration for {rid} (your own labeled history)",
        Language.ZH: "{rid} 的校准报告（你自己的标注历史）",
    },
    "calibration_totals": {
        Language.EN: "{labeled} of {total} reviews labeled.",
        Language.ZH: "{total} 次复盘中有 {labeled} 次已标注。",
    },
    "calibration_stats_header": {
        Language.EN: "Rule stats (fired | labeled | labeled bad):",
        Language.ZH: "规则统计（触发 | 已标注 | 标注为差）：",
    },
    "calibration_honest_note": {
        Language.EN: "Note: these are counts from your own labeled history, not calibrated probabilities. Labels never feed the engine automatically.",
        Language.ZH: "说明：这些只是你自己标注历史中的计数，不是校准过的概率。标签永远不会自动喂回引擎。",
    },
    "counterfactual_none": {
        Language.EN: "No reviews recorded for {rid} yet.",
        Language.ZH: "{rid} 还没有复盘记录。",
    },
    "counterfactual_list_header": {
        Language.EN: "Reviews for {rid}:",
        Language.ZH: "{rid} 的复盘记录：",
    },
    "counterfactual_hint": {
        Language.EN: "Re-run one with: lre counterfactual <rel> --review <id>",
        Language.ZH: "用以下命令重跑：lre counterfactual <关系> --review <id>",
    },
    "counterfactual_header": {
        Language.EN: "Counterfactual review of {id} ({ts}, original: {rec})",
        Language.ZH: "反事实复盘 {id}（{ts}，原结论：{rec}）",
    },
    "counterfactual_evidence": {
        Language.EN: "Evidence frozen at that time: {obs} observation(s), {hits} boundary hit(s), {inc} unresolved inconsistencies",
        Language.ZH: "当时冻结的证据：{obs} 条观察、{hits} 次边界命中、{inc} 个未解决矛盾",
    },
    "counterfactual_state": {
        Language.EN: "  exposure {e} | attraction {a} | trust {t} | uncertainty {u} | emotional {em}",
        Language.ZH: "  敞口 {e} | 吸引力 {a} | 信任 {t} | 不确定性 {u} | 情绪 {em}",
    },
    "counterfactual_recomputed": {
        Language.EN: "Recomputed with today's rules: {rec}",
        Language.ZH: "用今天的规则重算：{rec}",
    },
    "counterfactual_findings": {
        Language.EN: "  findings at that time: {list}",
        Language.ZH: "  当时的发现：{list}",
    },
    "counterfactual_verdict": {
        Language.EN: "Original vs recomputed: {verdict}",
        Language.ZH: "原结论 vs 重算结论：{verdict}",
    },
    "counterfactual_note": {
        Language.EN: "Note: today's thresholds and profiles are applied to past evidence; the rules may have changed since the original decision. This is an audit tool, not a verdict on your past self.",
        Language.ZH: "说明：本工具用今天的阈值与画像去审视过去的证据；规则可能已与当初不同。这是审计工具，不是对过去自己的判决。",
    },
    "consistency_header": {
        Language.EN: ("Consistency audit for {rid} ({start} to {end}, {days} day(s))"),
        Language.ZH: "{rid} 的一致性审计（{start} 至 {end}，{days} 天）",
    },
    "consistency_none": {
        Language.EN: (
            "No recorded consistency signals matched these rules in this window."
        ),
        Language.ZH: "这个窗口内没有记录命中这些一致性规则。",
    },
    "consistency_note": {
        Language.EN: (
            "Note: this report identifies record-level inconsistencies; it is "
            "not a diagnosis of self-deception, intent, or truth."
        ),
        Language.ZH: (
            "说明：本报告只识别记录层面的不一致，不是对自欺的诊断，也不判断意图或事实真伪。"
        ),
    },
    "trust_change_without_new_evidence": {
        Language.EN: (
            "{count} trust change(s) had no currently recorded observation or "
            "verification timestamp between snapshots; latest "
            "{previous_id}->{current_id}: {before} -> {after}. This may reflect "
            "reconsideration of older evidence or a missing record, not "
            "self-deception."
        ),
        Language.ZH: (
            "有 {count} 次信任变更在两个快照之间没有当前可见的观察或验证时间戳；最近一次 "
            "{previous_id}->{current_id}：{before} -> {after}。这也可能是重新审视旧证据或漏记依据，不能据此认定自欺。"
        ),
    },
    "interpretation_without_alternative": {
        Language.EN: (
            "{count} interpretation(s) have no recorded alternative explanation "
            "({ids}). This is a one-sided record, not proof that the "
            "interpretation is wrong."
        ),
        Language.ZH: (
            "有 {count} 条解释没有记录替代解释（{ids}）。这是单侧记录，不证明原解释错误。"
        ),
    },
    "self_reported_rationalization_run": {
        Language.EN: (
            "{count} consecutive self-reported rationalization flags were "
            "recorded. These are user annotations, not automatic psychological "
            "detection."
        ),
        Language.ZH: (
            "记录了连续 {count} 条用户自报的合理化标记。这些是用户标注，不是自动心理检测。"
        ),
    },
    "unresolved_structured_conflicts": {
        Language.EN: (
            "{count} unresolved structured conflict(s) are recorded. This does "
            "not include semantic conflicts inferred from free text."
        ),
        Language.ZH: (
            "记录中有 {count} 个未解决的结构化冲突；这不包括从自由文本推断的语义冲突。"
        ),
    },
    "criterion_direction_conflict": {
        Language.EN: (
            "{count} pair(s) use the same explicit criterion with opposite "
            "trust directions; first '{criterion}' "
            "({observation_a}/{relationship_a} {direction_a} vs "
            "{observation_b}/{relationship_b} {direction_b}). Context may "
            "justify the difference; this is a review candidate, not a diagnosis."
        ),
        Language.ZH: (
            "有 {count} 对记录在同一显式标准下采用相反的信任方向；第一对为 "
            "'{criterion}'（{observation_a}/{relationship_a} {direction_a} 对比 "
            "{observation_b}/{relationship_b} {direction_b}）。情境可能足以解释差异；这只是复核候选，不是诊断。"
        ),
    },
    "review_header": {
        Language.EN: "Review {id} for {rid}",
        Language.ZH: "复盘 {id}（关系 {rid}）",
    },
    "panel_status_title": {
        Language.EN: "LoveRiskEngine — {rid}",
        Language.ZH: "LoveRiskEngine — {rid}",
    },
    "panel_review_title": {
        Language.EN: "Review {id} — {rid}",
        Language.ZH: "复盘 {id} — {rid}",
    },
    "panel_consistency_title": {
        Language.EN: "Consistency audit — {rid}",
        Language.ZH: "一致性审计 — {rid}",
    },
    "review_unresolved": {
        Language.EN: "Unresolved inconsistencies: {n}",
        Language.ZH: "未解决的矛盾：{n}",
    },
    "review_hooks_header": {
        Language.EN: "Triggered hooks:",
        Language.ZH: "触发的钩子：",
    },
    "review_none": {Language.EN: "  - none", Language.ZH: "  - 无"},
    "review_warnings_header": {Language.EN: "Warnings:", Language.ZH: "警告："},
    "review_cooldown": {
        Language.EN: "Cooldown {id} started — exposure-raising actions are gated until it expires. See: lre cooldown {rel}",
        Language.ZH: "冷却期 {id} 已启动——在到期前提升敞口的操作会被拦截。查看：lre cooldown {rel}",
    },
    # --- errors ---
    "error_relationship_not_found": {
        Language.EN: "Error: relationship not found: {token}",
        Language.ZH: "错误：找不到关系：{token}",
    },
    "error_claim_equals": {
        Language.EN: "Error: --claim must be attribute=value, got {item}",
        Language.ZH: "错误：--claim 必须是 属性=值 的形式，收到的是 {item}",
    },
    "error_claim_empty": {
        Language.EN: "Error: --claim attribute is empty in {item}",
        Language.ZH: "错误：{item} 中的 --claim 属性为空",
    },
    "error_alternative_required": {
        Language.EN: (
            "Error: --alternative is required when --interpretation is supplied"
        ),
        Language.ZH: "错误：提供 --interpretation 时必须同时提供 --alternative",
    },
    "error_judgment_pair_required": {
        Language.EN: (
            "Error: --criterion-key and --judgment-direction must both be supplied"
        ),
        Language.ZH: ("错误：--criterion-key 与 --judgment-direction 必须同时提供"),
    },
    "error_positive_days": {
        Language.EN: "Error: --days must be a positive integer",
        Language.ZH: "错误：--days 必须是正整数",
    },
    "error_boundary_not_found": {
        Language.EN: "Error: boundary not found: {id}",
        Language.ZH: "错误：找不到边界：{id}",
    },
    "error_inconsistency_not_found": {
        Language.EN: "Error: inconsistency not found: {id}",
        Language.ZH: "错误：找不到矛盾：{id}",
    },
    "error_review_not_found": {
        Language.EN: "Error: review {id} not found",
        Language.ZH: "错误：找不到复盘 {id}",
    },
    "error_review_wrong_relationship": {
        Language.EN: "Error: review {id} belongs to another relationship",
        Language.ZH: "错误：复盘 {id} 属于另一个关系",
    },
    "error_verification_not_found": {
        Language.EN: "Error: verification item not found: {id}",
        Language.ZH: "错误：找不到验证项：{id}",
    },
    # --- inconsistency list labels ---
    "inconsistency_open": {Language.EN: "Open", Language.ZH: "未了结"},
    "inconsistency_resolved": {Language.EN: "Resolved", Language.ZH: "已了结"},
    # --- help / parser description ---
    "help_description": {
        Language.EN: "LoveRiskEngine - personal relationship decision-support CLI",
        Language.ZH: "LoveRiskEngine —— 个人关系决策支持命令行工具",
    },
    "help_usage": {Language.EN: "usage", Language.ZH: "用法"},
    "help_consistency": {
        Language.EN: "Audit record-level consistency without changing decisions",
        Language.ZH: "审计记录层面的一致性，不改变决策",
    },
    "help_consistency_days": {
        Language.EN: "Positive audit window in days (default: 30)",
        Language.ZH: "审计窗口天数，必须为正整数（默认：30）",
    },
    "help_criterion_key": {
        Language.EN: "Explicit stable criterion key for later comparison",
        Language.ZH: "用于后续比较的显式稳定标准键",
    },
    "help_judgment_direction": {
        Language.EN: "How this observation explicitly affects trust",
        Language.ZH: "这条观察如何明确影响信任判断",
    },
    "observation_judgment_extra": {
        Language.EN: " [criterion={criterion} direction={direction}]",
        Language.ZH: " [标准={criterion} 方向={direction}]",
    },
}


def t(msgid: str, **kwargs: object) -> str:
    """Translate a catalog message; `{named}` placeholders via str.format.

    Missing keys fall back to English, then to the msgid itself — display
    must never crash on a translation gap.
    """
    entry = CATALOG.get(msgid)
    if entry is None:
        return msgid
    template = entry.get(current_language()) or entry[Language.EN]
    return template.format(**kwargs) if kwargs else template


def localize_finding(finding: object) -> str:
    """Display-time localization of a finding; stored text stays canonical.

    Duck-typed so `core/i18n.py` never imports the detector modules: findings
    carrying `msg_key`/`msg_params` are rendered from the catalog, anything
    else (legacy or uncatalogued) shows its canonical English message.
    """
    key = getattr(finding, "msg_key", "")
    if key:
        return t(key, **getattr(finding, "msg_params", {}))
    return str(getattr(finding, "message", finding))
