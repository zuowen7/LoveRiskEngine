# LoveRiskEngine

[![CI](https://github.com/zuowen7/LoveRiskEngine/actions/workflows/ci.yml/badge.svg)](https://github.com/zuowen7/LoveRiskEngine/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()

> 一个**个人关系决策支持框架**。它帮助你记录观察、审计自己的认知偏差、追踪风险敞口，并在重大关系决策前触发结构化复盘——在信息不完备的条件下。

[English README](README.md) · [英文上手文档](docs/getting-started.en.md) · [中文上手文档](docs/getting-started.zh.md)

## 它不是什么

- 不是"给人打分 / 鉴渣"的系统。
- 不是监控、追踪或秘密调查工具。
- 不是社工数据库、PII 爬虫或灰黑产查询。
- 不是单方面宣布某人"好"或"坏"的 AI。

## 理论基础（theory-informed engineering）

本引擎的设计参考了判断与决策、人际信任、自我调节和行为经济学领域的研究。每个设计决策对应的文献锚点——以及同样重要的：**哪些规则没有理论锚点、只是工程启发式**——维护在
[docs/SCIENTIFIC_FOUNDATIONS.md](docs/SCIENTIFIC_FOUNDATIONS.md)（英文），并由文档契约测试锁定。所有具体阈值和计分规则均为工程启发式，**未经过临床或实证校验**。

## 核心设计原则

1. **吸引力 ≠ 信任** —— 你喜欢一个人，和"有多少*证据*支撑你信任他"，分开记录。吸引力的变化永远不会自动改写信任。
2. **观察 ≠ 解释** —— 客观观察单独记录；一旦填写解释，就必须同时填写至少一个替代解释，外加来源与置信度。
3. **敞口不能跑赢证据** —— 时间 / 情绪 / 隐私 / 财务 / 重大决定五轴敞口分开追踪；敞口涨得比证据快，就会告警。
4. **默认动作是继续观察** —— 系统从不默认"信任"或"拒绝"。输出五种状态：`CONTINUE_OBSERVING`、`WAIT`、`PAUSE`、`DECREASE_EXPOSURE`、`EXIT`。
5. **硬边界** —— 你自己预先画线。边界命中只有在**有记录证据**时才能给出 `EXIT` 建议；单条模糊观察永不自动定罪。
6. **偏差审计** —— 决策复盘内置 9 个检测器（见下）；另有五规则一致性审计，但不改变建议。
7. **隐私优先** —— 仅本地 SQLite，无多余 PII，无爬取、无定位接口，**零网络依赖**。

## 安装（开发模式）

```bash
python -m venv .venv && .venv/Scripts/activate   # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"          # 开发（含测试工具与 rich）
pip install -e ".[dev,pretty]"   # 顺带启用美化输出（可选）
```

`rich` 是**可选**依赖：装了它，`status` / `review` 的输出在真实终端里会带上克制的面板边框；不装也完全可用，引擎与逻辑始终纯标准库。

## 五分钟上手

```bash
lre init
lre relationship add "Alex" --kind LOVER     # 类型: LOVER/FRIEND/PARENT/BOSS/MENTOR/COLLEAGUE/STRANGER
lre observe Alex --category honesty \
    --observation "本周两次临时取消约会" \
    --interpretation "对方在失去兴趣" \
    --alternative "最近工作压力大" \
    --source self --confidence 4 --signal-type COSTLY
lre state set Alex --attraction 8.5 --trust 4.0 --uncertainty 7.0 --emotional ANXIOUS
lre exposure set Alex --time 3 --emotional 4 --privacy 1
lre boundary add --description "从不无视我明说的边界" --severity HARD
lre observe Alex --observation "他说自己单身" --claim "relationship_status=single"
lre observe Alex --observation "他提到了妻子" --claim "relationship_status=married"
lre contradictions Alex --save     # 自动标记冲突声明
lre observe Alex --observation "当晚没有回复" \
    --criterion-key responsiveness --judgment-direction WEAKENS_TRUST
lre consistency Alex --days 30     # 只做记录一致性审计
lre status Alex
lre review Alex
lre history Alex
```

## 中文界面

```bash
LRE_LANG=zh lre status Alex     # 本次会话切换为中文
# 永久生效（Windows PowerShell）：
setx LRE_LANG zh
```

语言只影响**显示**：存进数据库的复盘笔记保持规范英文（它们是证据记录，永不改写）。检测器告警在显示时按语言渲染，落库文本不变。

## 数据位置与备份

数据库默认放在系统数据目录（Windows `%LOCALAPPDATA%\LoveRiskEngine`、macOS
`~/Library/Application Support/LoveRiskEngine`、Linux `$XDG_DATA_HOME` 或
`~/.local/share/LoveRiskEngine`）；当前目录下旧版的 `./love_risk.db` 仍然可用，
`LRE_DB_PATH` 永远优先。`lre init` 会打印实际路径。

备份只有一条命令：

```bash
lre export backup.json   # 无损 JSON 包，带 SHA-256 校验
lre restore backup.json  # 整体替换数据库；损坏/版本不符的文件会被拒绝
lre db check             # 完整性 + 外键检查
```

导出包包含你记录的一切——请把它当作日记文件：放在加密存储里，随重要数据一起备份。

## Shell 补全

候选词由已安装的 `lre` 本尊实时计算，永远不会和真实命令面脱节：

```bash
eval "$(lre completion bash)"                    # bash
lre completion zsh > "${fpath[1]}/_lre"          # zsh
lre completion fish > ~/.config/fish/completions/lre.fish   # fish
lre completion powershell | Out-String | Invoke-Expression  # PowerShell
```

## 自我一致性审计（仅提供信息）

`lre consistency <关系> --days 30` 审计已经记录的判断过程；它不诊断自欺，
也永远不会进入决策引擎。报告包括：没有同期新增证据的信任变更、缺少替代解释的
历史/导入记录、连续三条用户自报的合理化标记、当前未解决的结构化冲突，以及
同一显式 `--criterion-key` 下相反的 `SUPPORTS_TRUST` / `WEAKENS_TRUST`
方向。

系统不猜自由文本语义。两个结构化判断参数可以都不填，但填写时必须成对出现；
候选项只表示需要复核情境，不证明存在双重标准。

## 检测器（有意未校准的启发式规则）

| 规则 | 触发条件 |
|------|---------|
| `attraction_exceeds_trust` | 吸引力 − 信任 ≥ 3 **且** 观察 < 3 条 |
| `repeated_rationalization` | ≥ 3 条连续的自我合理化标记 |
| `exposure_outpaces_evidence` | 敞口总量 > **证据支撑单位** |
| `high_emotion_major_decision` | 高情绪状态 **且** 重大决定敞口 > 0 |
| `unresolved_inconsistencies` | ≥ 1 个未解决的矛盾 |
| `love_bombing_pattern` | 早期窗口：≥3 廉价 + ≥1 昂贵 + ≥5 总信号 |
| `rapid_exposure_escalation` | 2 天内敞口 +≥3 分 **且** 窗口内零新观察 |
| `promise_expiry` | 仅窗口类关系：未来时态 `--claim` 超过承诺窗口未被触及 |
| `repeated_repromises` | 仅窗口类关系：同一属性窗口内重复承诺 ≥3 次 |

> 这些阈值是**占位值**，不是校准过的概率。本引擎**绝不**产出"可信度 87.34%"这类伪精确分数。

## 关系类型（kinds）

`lre relationship add <别名> --kind KIND` 给关系打上类型标签
（默认 `LOVER`）。类型选择一份 *画像*：

- **展示上下文** —— 权力不对称 / 退出成本档位，由 `status` 与 `review` 打印，供你自己判断；
- **承诺窗口**（90 天）—— 仅 `BOSS / MENTOR / COLLEAGUE`：超期未兑现的承诺以 `WAIT` 告警呈现，`lre promises <关系>` 查看全部；
- **提前告警** —— 退出成本为 `HIGH`（`PARENT / BOSS / MENTOR`）时，差距与合理化阈值提前，告警中写明偏移后的数值。

档位是序数（`HIGH / MED / LOW`），**永远不是数字**，引擎也绝不会用它来教你该怎么回话。改类型用
`lre relationship set <id> --kind KIND`。

## 项目结构

```
love_risk_engine/
  core/          领域模型 + 决策引擎 + 检测器（偏差规则、爱情轰炸、廉价/昂贵信号、
                 承诺过期、敞口快速升级）+ 冲突追踪 + 证据支撑 + 关系画像 +
                 变更历史 + 时间线 + 冷却护栏 + 离线聊天导入 + 一致性审计 + i18n
  storage/       SQLite（版本化迁移）+ 数据访问
  services/      复盘、反事实复盘、一致性审计工作流、无损导出
  cli.py         命令行界面
examples/        示例 claim-rules.json
tests/           340+ 测试，覆盖率 98%+
docs/           设计系统、审计与架构报告、上手文档、每个已交付切片的提案档案
```

## 路线图

已实现：✅ 冲突追踪 ✅ 质量校准的证据支撑 ✅ 廉价/昂贵信号分类 ✅ 爱情轰炸检测
✅ 矛盾三态了结 ✅ 冷却/预承诺护栏 ✅ 时间线 ✅ 离线聊天导入 ✅ 关系类型与画像
✅ 承诺过期 ✅ 退出成本敏感度 ✅ 状态/敞口变更历史 ✅ 敞口快速升级
✅ 数据目录默认 ✅ 无损导出/恢复 ✅ `db check` ✅ 再承诺计数 ✅ 反事实复盘
✅ 互相验证清单 ✅ 两阶段自我一致性审计 ✅ shell 补全 ✅ 中文界面（i18n）
✅ rich 美化（可选）

权威路线图与目标架构见 `docs/ARCHITECTURE_AND_PLAN.md`；现状审计（强项、欠账、缺口）
见 `docs/AUDIT_REPORT.md`；社区调研与 pi agent 架构研究见 `docs/RESEARCH_COMMUNITY.md`。
