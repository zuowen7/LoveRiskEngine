# LoveRiskEngine — DESIGN.md

> 一套为「个人关系决策支持框架」服务的前端设计系统。
> 风格基调：**冷静的仪器（Calm Instrument）** —— 借鉴 Stripe 的精确与清晰、Linear 的克制与留白，加入一抹人文暖色。
> 本系统面向未来 Web/桌面 UI（v0.1 为 CLI，roadmap 含可视化面板）。所有 token 均以 HEX + CSS 变量双格式给出，可直接被 AI 编程代理消费。

---

## 1. Visual Theme & Atmosphere

- **设计哲学**：把「关系决策」当作一件需要清醒、耐心、克制的认真事。界面应当是一台冷静的仪器，而不是诱人的社交产品。信息密度高但不喧闹，把注意力留给证据本身。
- **视觉基调**：克制、清醒、可信、带人文温度。
- **核心关键词**：`calm` · `precise` · `honest` · `restrained` · `paper-like`
- **光影与质感**：极轻阴影、1px 细边框、柔和大圆角；表面采用略带暖意的浅色纸感（非纯白），避免玻璃拟态与炫技渐变。数字与 ID 使用等宽字体，强调「可核对」的仪器感。

---

## 2. Color Palette & Roles

所有色值精确到 HEX；暖中性底 + 冷调信任主色 + 暖调人文强调。

### Neutral / Warm Gray（暖中性，纸感底）
| Token | HEX | 用途 |
|---|---|---|
| `--color-bg` | `#FAF8F5` | 应用背景（暖纸白） |
| `--color-surface` | `#FFFFFF` | 卡片 / 浮层表面 |
| `--color-surface-sunken` | `#F2EFEA` | 凹陷区 / 代码块 / 输入底色 |
| `--color-border` | `#E7E2DA` | 默认边框 |
| `--color-border-strong` | `#D6CFC4` | 强调边框 / 分隔线 |
| `--color-ink` | `#1E2235` | 主文字（深石板，非纯黑） |
| `--color-ink-soft` | `#565A6E` | 次级文字 |
| `--color-ink-faint` | `#8C8F9E` | 占位符 / 元信息 |

### Primary Colors（信任锚点 · 冷靛蓝）
| Token | HEX | 用途 |
|---|---|---|
| `--color-primary` | `#4B5BD6` | 主操作 / 链接 / 选中态 |
| `--color-primary-dark` | `#3640A8` | hover / 按压 |
| `--color-primary-darker` | `#282F7E` | 文本型主色 |
| `--color-primary-tint` | `#EEF0FB` | 主色淡底 / 选中背景 |

### Accent / Interactive（人文暖色 · 陶土）
| Token | HEX | 用途 |
|---|---|---|
| `--color-accent` | `#C76B53` | 人文强调 / 个体数据高亮 |
| `--color-accent-dark` | `#A8523C` | 暖色 hover |
| `--color-accent-tint` | `#F7ECE7` | 暖色淡底 |

### Semantic Colors（语义状态）
| Token | HEX | Tint | 用途 |
|---|---|---|---|
| `--color-success` | `#2E8B6F` | `#E6F3EE` | 已解决 / 证据充分 |
| `--color-info` | `#3B7DD8` | `#E7F0FB` | 提示 / 中性信息 |
| `--color-warning` | `#C79233` | `#FBF1DD` | 偏差告警 |
| `--color-danger` | `#C2453D` | `#FBEAE8` | 硬边界 / EXIT |

### Domain Metric Colors（领域度量 · 强化「Attraction != Trust」）
> 设计决策：用**暖玫瑰 = attraction**，**冷青 = trust**，让「喜欢」与「可信证据」在视觉上天然分离，呼应核心原则 #1。
| Token | HEX | Tint | 用途 |
|---|---|---|---|
| `--color-attraction` | `#C25E7E` | `#F8E9EF` | 好感度轴（暖） |
| `--color-trust` | `#2E8B7F` | `#E6F3F1` | 信任证据轴（冷） |
| `--color-uncertainty` | `#8A7FB0` | `#F0ECF7` | 不确定性轴 |
| `--color-exposure` | `#C97B3C` | `#FBEDE0` | 风险敞口轴 |

### Decision-State Ramp（决策输出 · 5 级冷静→紧急）
> 对应引擎 `decide()` 输出，构成一条感知上连续的渐强色阶。
| State | Token | HEX |
|---|---|---|
| `CONTINUE_OBSERVING` | `--state-continue` | `#3B7DD8` |
| `WAIT` | `--state-wait` | `#C79233` |
| `PAUSE` | `--state-pause` | `#D2762E` |
| `DECREASE_EXPOSURE` | `--state-decrease` | `#C2593F` |
| `EXIT` | `--state-exit` | `#B23B36` |

### Shadow Colors（暖墨色阴影）
所有阴影基于 `rgba(30,34,53, …)`，见第 6 章。

---

## 3. Typography Rules

- **Font Family（UI / 中文）**：`'Inter', 'Noto Sans SC', system-ui, -apple-system, 'Segoe UI', sans-serif`
- **Font Family（数据 / ID / 分数）**：`'JetBrains Mono', 'SF Mono', ui-monospace, 'Cascadia Code', monospace`
- **设计哲学**：大标题用较紧字距 + 中等字重制造呼吸感；正文克制（400 / 1.6）；所有分数、ID、时间戳用等宽字体右对齐，强化「可核对仪器」感。

### Type Scale
| 级别 | 尺寸 | 字重 | 行高 | 字距 | 用途 |
|---|---|---|---|---|---|
| Display Hero | 40px | 600 | 1.2 | -0.02em | 关系总览大标题 |
| H1 | 30px | 600 | 1.25 | -0.015em | 页面标题 |
| H2 | 24px | 600 | 1.3 | -0.01em | 区块标题 |
| H3 | 19px | 600 | 1.35 | 0 | 卡片标题 |
| Title | 16px | 600 | 1.4 | 0 | 列表项 / 标签组 |
| Body | 15px | 400 | 1.6 | 0 | 正文 / 观察原文 |
| Small | 13px | 400 | 1.5 | 0 | 元信息 / 辅助说明 |
| Nano (UPPER) | 11px | 600 | 1.4 | 0.06em | 字段标签 / 状态徽章 |

---

## 4. Component Stylings

### Buttons
```css
.btn { font: 600 14px/1 'Inter', sans-serif; border-radius: 10px; padding: 10px 16px;
       border: 1px solid transparent; cursor: pointer; transition: background .15s, border-color .15s; }
.btn-primary   { background: var(--color-primary); color: #fff; }
.btn-primary:hover { background: var(--color-primary-dark); }
.btn-secondary { background: var(--color-surface); color: var(--color-ink); border-color: var(--color-border-strong); }
.btn-secondary:hover { background: var(--color-surface-sunken); }
.btn-ghost     { background: transparent; color: var(--color-primary); }
.btn-ghost:hover { background: var(--color-primary-tint); }
.btn-danger    { background: var(--color-danger); color: #fff; }
.btn-danger:hover { background: #972F29; }
```
变体：Primary / Secondary / Ghost / Danger。最小高度 40px；图标按钮 40×40。

### Cards
```css
.card { background: var(--color-surface); border: 1px solid var(--color-border);
        border-radius: 14px; padding: 20px; box-shadow: var(--shadow-sm); }
.card:hover { box-shadow: var(--shadow-md); }
```
观察卡片用 `surface`；凹陷区（如 raw observation 字段）用 `surface-sunken` 无边框。

### Inputs
```css
.input { background: var(--color-surface-sunken); border: 1px solid var(--color-border);
         border-radius: 10px; padding: 10px 12px; font: 400 15px/1.5 'Inter', sans-serif;
         color: var(--color-ink); }
.input:focus { outline: none; border-color: var(--color-primary);
               box-shadow: 0 0 0 3px var(--color-primary-tint); }
.input::placeholder { color: var(--color-ink-faint); }
```

### Navigation（侧栏）
```css
.nav { background: var(--color-surface-sunken); border-right: 1px solid var(--color-border); }
.nav-item { padding: 10px 14px; border-radius: 10px; color: var(--color-ink-soft); }
.nav-item:hover { background: var(--color-surface); color: var(--color-ink); }
.nav-item.active { background: var(--color-primary-tint); color: var(--color-primary-darker); font-weight: 600; }
```

### Badges / Tags（状态徽章）
```css
.badge { display: inline-flex; align-items: center; gap: 6px; font: 600 11px/1 'Inter', sans-serif;
         letter-spacing: .04em; text-transform: uppercase; padding: 5px 10px; border-radius: 999px; }
/* 决策状态映射：背景=tint，文字=主色 */
.badge-continue { background: #E7F0FB; color: #2A5DA8; }
.badge-wait    { background: #FBF1DD; color: #9C6E1E; }
.badge-pause   { background: #FBEDE0; color: #9C531E; }
.badge-decrease{ background: #FBEAE8; color: #972F29; }
.badge-exit    { background: #FBEAE8; color: #972F29; }
/* severity */
.badge-sev-high { background: #FBEAE8; color: #972F29; }
.badge-sev-med  { background: #FBF1DD; color: #9C6E1E; }
.badge-sev-low  { background: #E6F3EE; color: #1F6650; }
```

### Modals / Dialogs
```css
.modal-overlay { background: rgba(30,34,53,0.32); backdrop-filter: blur(2px); }
.modal { background: var(--color-surface); border-radius: 16px; padding: 24px;
         box-shadow: var(--shadow-2xl); animation: modal-in .18s ease-out; }
@keyframes modal-in { from { opacity:0; transform: translateY(8px); } to { opacity:1; transform:none; } }
```

---

## 5. Layout Principles

- **Spacing System**：4px 基数 → `4 / 8 / 12 / 16 / 24 / 32 / 48 / 64`。
- **Grid**：12 列，列间距 24px；内容容器 `max-width: 1200px`，左右 padding 24px。
- **典型布局**：左 `nav`（240px 固定）+ 右 `detail` 主区；关系列表可用两栏（列表 320px + 详情）。
- **Section Spacing**：区块间 48–64px；卡片内 padding 20–24px。
- **留白哲学**：以留白承载「克制」。高密度数据（观察流）与低密度呼吸区（决策建议）交替，避免连续压迫感。

---

## 6. Depth & Elevation

### Shadow System（暖墨 `rgba(30,34,53,…)`）
```css
--shadow-xs:  0 1px 2px rgba(30,34,53,.06);
--shadow-sm:  0 1px 3px rgba(30,34,53,.08), 0 1px 2px rgba(30,34,53,.04);
--shadow-md:  0 4px 10px rgba(30,34,53,.08), 0 2px 4px rgba(30,34,53,.05);
--shadow-lg:  0 12px 28px rgba(30,34,53,.12), 0 4px 8px rgba(30,34,53,.06);
--shadow-2xl: 0 24px 48px rgba(30,34,53,.16);
```

### Surface Layers
`background (#FAF8F5)` → `surface (#FFFFFF)` → `elevated (shadow-md)` → `overlay (modal/tooltip)`。

### Z-index Scale
`nav 10` · `dropdown 100` · `sticky-header 200` · `modal 1000` · `toast 1100`。

### Backdrop
仅 modal 使用极轻 `blur(2px)` + 32% 暖墨遮罩；不用于常驻面板。

---

## 7. Do's and Don'ts

**Do's**
1. 用等宽字体呈现所有分数、ID、时间戳，强化「可核对」感。
2. 用 rose/teal 双色明确区分 attraction 与 trust，绝不以单一「好感度」混淆。
3. 告警文案写清**依据**（哪条观察 / 哪个阈值），不抛伪精确百分比。
4. 默认状态用冷静蓝（CONTINUE_OBSERVING），紧急色仅留给 PAUSE/EXIT。
5. 留白承载克制，高密度数据与呼吸区交替。
6. 硬边界命中必须展示「依据」字段后才允许呈现 EXIT 建议。
7. 中文界面使用 Noto Sans SC 回退，保证跨平台字形一致。

**Don'ts**
1. 不要做「可靠度 87.34%」这类伪精确 Bayesian 分数。
2. 不要使用炫技渐变、玻璃拟态、脉冲动画等干扰清醒判断的视觉。
3. 不要用大红大绿把界面变成「鉴渣 / 评判」工具。
4. 不要因单条含糊观察自动渲染 EXIT（详见原则 #5）。
5. 不要用纯黑文字或纯白底造成刺眼对比。
6. 不要为了美观隐藏证据来源（source / alternative_explanation 必须可见）。
7. 不要引入任何暗示「监控 / 抓取 / 定位」的图标或文案。

---

## 8. Responsive Behavior

| Breakpoint | 范围 | 策略 |
|---|---|---|
| mobile | ≤ 640px | 单栏堆叠；nav 收为底部 tab；detail 全宽 |
| tablet | 641–1024px | 列表 280px + 详情；隐藏次要元信息 |
| desktop | 1025–1440px | 完整两栏 + 右栏度量卡 |
| wide | ≥ 1441px | `max-width: 1200px` 居中，两侧留白 |

- **Touch Targets**：最小 44×44px。
- **折叠**：`< 1024px` 时 `nav` 与列表合并为抽屉；观察流改为单列卡片流。
- **Font Scaling**：Display 在 mobile 降至 32px；其余层级不变。

---

## 9. Agent Prompt Guide

### Quick Reference
- 主色 `--color-primary: #4B5BD6`；底 `--color-bg: #FAF8F5`；墨 `--color-ink: #1E2235`。
- 度量双色：attraction `#C25E7E`（暖）、trust `#2E8B7F`（冷）。
- 决策 5 态：`continue #3B7DD8` → `wait #C79233` → `pause #D2762E` → `decrease #C2593F` → `exit #B23B36`。
- 字体：UI=Inter+Noto Sans SC，数据=JetBrains Mono。
- 圆角 8/12/14/16，阴影暖墨系，留白 4px 基数。

### Component Prompts（可直接复制）
1. 「生成一个关系总览卡片，左侧展示 attraction（暖玫瑰）与 trust（冷青）双仪表，右侧展示 5 态决策徽章，遵循 LoveRiskEngine DESIGN.md。」
2. 「做一个观察流列表项组件：observation 用等宽时间戳 + 原文，interpretation 与 alternative_explanation 并排双栏，来源用 Nano 标签。」
3. 「实现 bias warning 横幅：warning 琥珀底色，文案含触发规则 ID 与依据，不使用伪精确百分比。」
4. 「设计暴露雷达 / 柱状图，5 轴（time/emotional/privacy/financial/life_decision）用 exposure 橙 `#C97B3C`，叠加 evidence support 参考线。」
5. 「生成硬边界配置页：每条 boundary 含 severity 徽章，命中时必须展示 evidence 依据字段才可呈现 EXIT。」

### Iteration Guide
1. 先定中性底与墨色，再引入主色，最后加领域度量色 —— 避免色彩过载。
2. 任何状态变化必须可读出「依据」，否则退回更中性的呈现。
3. 数字一律等宽右对齐；标题紧字距。
4. 告警强度与色彩紧急度严格对应 5 态色阶，不自定义新色。
5. 阴影只增不炫；hover 仅在必要处（按钮、卡片、nav）出现。
6. 移动端优先保证 44px 触摸目标与单栏可读性。
7. 每次迭代后核对：是否出现伪精确评分？是否暗示监控？是否混淆 attraction/trust？三否则通过。
8. 中文文案用 Noto Sans SC 回退，勿用衬线制造距离感。
9. 组件间距严格走 4px 倍数，勿随手填值。
10. 新增颜色前先问：能否复用现有 token？能则不新增。
