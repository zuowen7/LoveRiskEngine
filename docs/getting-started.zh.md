# 上手文档 — LoveRiskEngine（中文）

从安装到养成"每天记一笔"的决策支持习惯，五分钟。设计理念与完整命令参考见
[README_zh](../README_zh.md)；权威路线图见
[`ARCHITECTURE_AND_PLAN.md`](ARCHITECTURE_AND_PLAN.md)。

## 1. 安装

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"                                 # 或 ".[dev,pretty]" 启用可选 rich 美化
```

零运行时依赖；`rich`（可选）只在真实终端里给 `status` / `review` 加克制的面板。

## 2. 初始化与创建关系

```bash
lre init                                             # 会打印数据库的确切路径
lre relationship add "Alex" --kind LOVER
```

类型：`LOVER / FRIEND / PARENT / BOSS / MENTOR / COLLEAGUE / STRANGER`。
类型选择一份画像——展示上下文（权力不对称 / 退出成本档位）、90 天承诺窗口
（BOSS/MENTOR/COLLEAGUE）、高退出成本关系的提前告警。档位是序数，永远不是数字。

## 3. 每天一圈

```bash
# 记录：观察、解释，以及至少一个替代解释。
lre observe Alex --observation "本周两次临时取消约会" \
    --interpretation "对方在失去兴趣" --alternative "最近工作压力大" \
    --confidence 4 --signal-type COSTLY

# 结构化声明驱动冲突追踪。
lre observe Alex --observation "他说自己单身" --claim "relationship_status=single"
lre observe Alex --observation "他提到了妻子" --claim "relationship_status=married"
lre contradictions Alex --save

# 自己的状态与敞口，严格分开记录。
lre state set Alex --attraction 8.5 --trust 4 --uncertainty 7 --emotional ANXIOUS
lre exposure set Alex --time 3 --emotional 4

# 看全貌 + 结构化复盘。
lre status Alex
lre review Alex
lre history Alex
```

`review` 给出五种建议之一：`CONTINUE_OBSERVING / WAIT / PAUSE /
DECREASE_EXPOSURE / EXIT`；`EXIT` 只来自**有记录证据的硬边界命中**。会拦截
动作的建议会启动冷却期（可覆盖，覆盖必留审计日志）。

## 4. 预先给自己画线

```bash
lre boundary add --description "从不无视我明说的边界" --severity HARD
lre boundary hit B001 --relationship Alex --evidence "当着朋友的面嘲笑我的边界"
lre verify add Alex --item "把我介绍给了他的朋友们"
lre verify check V001          # 确认你实际验证过的昂贵信号
```

## 5. 备份——只有一条命令

```bash
lre export backup.json        # 无损导出，带 SHA-256 校验
lre restore backup.json       # 整体替换数据库；损坏/版本不符会被拒绝
lre db check                  # 完整性 + 外键检查
```

把导出包当日记文件对待：放在加密存储里，随重要数据一起备份。

## 6. 中文界面与补全

```bash
LRE_LANG=zh lre status Alex            # 本次调用切换中文（Windows 持久化：setx LRE_LANG zh）
eval "$(lre completion bash)"          # bash 补全，候选词由安装的 lre 本尊生成
```

> Windows 老式控制台（GBK 代码页）显示中文可能乱码：使用 Windows Terminal，
> 或先执行 `chcp 65001` / 设环境变量 `PYTHONIOENCODING=utf-8`。

## 7. 审计自己的判断

```bash
lre counterfactual Alex                # 列出历史复盘
lre counterfactual Alex --review RV001 # 用"当时"的证据重跑那次复盘
                                       # （今天的规则、过去的证据）
```

## 常见问题

- **数据在哪？** `lre init` 会打印路径：默认在系统数据目录；`LRE_DB_PATH` 可覆盖。
- **会不会删数据？** 不会。边界只退役、观察只追加、窗口只影响显示。导出是无损的。
- **中文模式下，为什么落库的复盘笔记还是英文？** 规范记录保持英文——它们是证据；
  只有显示层会本地化。
