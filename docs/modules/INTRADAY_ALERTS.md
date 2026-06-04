# 盘中提醒模块

版本：v1.1

本模块用于监控已定义的触发条件，并提醒是否需要执行原计划。它不负责重新分析市场，不负责临时改写主线，也不负责发明新的买卖逻辑。

盘中提醒的定位是“执行纪律和风险验证”，不是自动交易系统。所有提醒默认需要人工确认，除非用户未来单独建立自动化交易规则。

## 1. 模块目标

回答五个问题：

1. 盘前操作建议中的触发条件是否出现？
2. 持仓 ETF/个股的买入、加仓、减仓、卖出或失效条件是否触发？
3. 触发后应执行、等待确认、取消，还是复核？
4. 是否仍然满足市场仓位、主线和组合约束？
5. 是否需要人工确认？

盘中提醒是执行纪律工具，不是临场投研工具。

## 2. 必须读取的前置结论

盘中提醒至少应读取：

- 当日盘前操作建议：`research/actions/`
- 最新市场仓位报告：`research/market/`
- 最新主线登记册：`research/themes/theme_registry.json`
- ETF/个股档案中的触发条件
- 当前组合分析或持仓快照
- 固定盘中规则：`research/alerts/intraday_rules.json`
- 盘中行情快照：来自 QMT 的实时行情文件，格式参考 `templates/intraday_quotes_snapshot_template.json`

如果没有盘前操作建议或标的档案，本模块只能输出“无法提醒，需要先补计划或研究”。

## 2.1 数据源分工

| 数据源 | 角色 | 用途 | 边界 |
| --- | --- | --- | --- |
| Tushare | 研究底座 | 生成关键均线、估值、财务、资金流和历史参考 | 不作为盘中实时主源 |
| QMT | 盘中实时 | 实时价格、成交额、涨跌幅、盘口和盘中验证 | 盘中提醒主数据源 |
| BaoStock | 历史备份 | 免费历史行情、均线和关键位交叉验证 | 不作为实时主源 |
| 官网/公告 | 权威事实 | 财报、分红、重大公告和事实确认 | 不做高频价格触发 |

第一版盘中监测采用“QMT 行情快照文件”作为输入，不直接连接下单或自动交易接口。

## 2.2 规则文件

固定规则文件：

```text
research/alerts/intraday_rules.json
```

规则文件只保存已经被研究报告、ETF档案、操作建议或人工确认过的触发器。盘中脚本不得临时生成新规则。

规则分为三层：

1. 市场门禁：判断是否允许新增进攻、只允许验证、只允许减风险。
2. 标的触发器：指数、ETF、个股的关键价位和条件。
3. 组合边界：金融、资源、主题、进攻仓等暴露是否需要人工复核。

## 2.3 行情快照格式

盘中脚本读取 JSON 行情快照，格式参考：

```text
templates/intraday_quotes_snapshot_template.json
```

核心字段：

- `timestamp`：行情快照时间。
- `source`：`qmt|manual|other`。
- `quotes`：按代码保存实时行情。
- `market_context`：可选，保存市场状态、上涨家数、成交额、当前权益仓位等。

如果缺少标的实时行情，相关标的输出 `blocked`，不得推断。

## 3. 提醒类型

| 类型 | 含义 |
| --- | --- |
| buy_trigger | 买入条件触发 |
| add_trigger | 加仓条件触发 |
| reduce_trigger | 减仓条件触发 |
| sell_trigger | 卖出条件触发 |
| invalidation_trigger | 原逻辑失效条件触发 |
| risk_trigger | 风险或硬约束触发 |
| watch_trigger | 观察条件触发 |
| no_trigger | 未触发 |
| blocked | 缺少前置计划或研究 |

补充类型：

| 类型 | 含义 |
| --- | --- |
| near_trigger | 接近关键位，但还未触发 |
| gate_blocked | 市场门禁或组合约束禁止执行 |

## 4. 触发后动作

| 动作 | 含义 |
| --- | --- |
| execute | 符合原计划，可执行 |
| wait | 条件不完整，等待确认 |
| cancel | 原计划失效，取消 |
| review | 需要人工复核 |
| log_only | 只记录，不操作 |

第一版不输出自动下单指令。即使 `suggested_action=execute`，含义也只是“符合原计划，可提交人工确认或操作建议模块复核”。

所有 `execute` 都应默认需要人工确认，除非用户未来明确设置自动化规则。

## 5. 盘中硬规则

- 不临时重写市场仓位分数。
- 不临时重写主线评级。
- 不临时新增未经研究的标的。
- 不把短期价格波动解释成新策略。
- 不把未触发条件的标的强行变成操作建议。
- 如果提醒与盘前计划冲突，必须标记为 `review`。
- 如果前置研究缺失，必须标记为 `blocked`。
- 不自动读取或调用 QMT 下单接口。
- 不把“价格触发”单独等同于“可以买/可以卖”。
- 加仓类提醒必须同时检查市场门禁、主线/个股/ETF档案和组合暴露。
- 减风险类提醒优先级高于加仓类提醒。

## 6. 提醒优先级

| 优先级 | 说明 |
| --- | --- |
| 高 | 失效条件、风险约束、减仓/卖出触发 |
| 中 | 买入、加仓、观察条件触发 |
| 低 | 未触发但接近触发、需要盘后观察 |

优先级高不代表一定交易，只代表需要优先确认。

## 7. 输出口径

每次盘中提醒必须包含：

- 日期和时间
- 来源计划
- 监控标的
- 触发条件
- 当前状态
- 提醒类型
- 建议动作
- 是否需要人工确认
- 依据
- 风险
- 需要写入决策日志的内容

标准输出文件：

```text
research/alerts/intraday_alert_YYYY-MM-DD_HHMMSS.md
research/alerts/intraday_alert_YYYY-MM-DD_HHMMSS.json
```

脚本入口：

```powershell
python scripts\intraday_monitor.py --quotes-file path\to\qmt_snapshot.json
```

实时作战地图入口：

```powershell
py -3.11 scripts\intraday_dashboard.py
```

实时作战地图直接读取 QMT 行情和 `research/alerts/intraday_rules.json`，每隔数秒刷新一次，不调用大模型、不生成报告、不自动下单。状态变化日志默认写入本地 `runtime/alerts/`，该目录不作为研究报告提交。

实时数据源自检：

```powershell
py -3.11 scripts\intraday_dashboard.py --once-json
```

该命令只读取一次 QMT 实时行情并输出 JSON，不打开窗口，适合排查 QMT 连接、字段缺失和规则误报。

可选参数：

```powershell
python scripts\intraday_monitor.py --quotes-file path\to\qmt_snapshot.json --rules-file research\alerts\intraday_rules.json --dry-run
```

## 8. 与其他模块的关系

- 操作建议模块定义盘中触发条件。
- ETF/个股档案定义标的自身触发条件。
- 市场仓位和主线模块提供操作边界。
- 决策日志记录触发、执行和偏差。
- 盘后复盘模块检查提醒是否有效。

## 9. 使用提示词

日常使用时，可以对 Codex 说：

```text
请按 docs/modules/INTRADAY_ALERTS.md 和 templates/intraday_alert_template.md 检查盘中提醒。
只能检查已定义触发条件，不要临时生成新策略。
如果缺少盘前计划或标的档案，输出 blocked。
```

## 10. 作战地图显示规范

实时窗口的主界面应优先显示图示，不以成交额、涨跌幅、MA20、MA60 等表格字段为核心。

顶部基础底图读取最新 `research/allocation/target_allocation_*.json` 和 `research/portfolio/portfolio_snapshot_*.json`：

- 市场权益目标与现金/短融目标。
- 权益内仓位桶：宽基/核心底仓、进攻主线仓、防御仓。
- 其他/待清理桶目标为 0，用于暴露组合拖尾和非理想持仓。
- 每个桶显示目标仓位、实际仓位和偏离百分点。

单标的图示至少包含：

- 估值作战带：低估观察区、合理配置区、偏贵区、拥挤/风险区。
- 实时当前位置：黑色竖线。
- 风控位：蓝色三角标记；用于提示需要优先复核风险，不代表自动卖出。
- 右侧确认位：青色菱形标记；用于提示重新站回确认位后才允许考虑由观察转配置，不代表自动买入。
- 风险区起点：红色竖线标记。
- 长期/中期/短期趋势灯：按固定规则展示上行、震荡、下行或样本不足。
- 前高回撤与前低反弹：用条形图展示当前回撤/反弹，并用竖线标记历史常见水平。
- 仓位差距：显示当前仓位、目标区间和偏离。

盘中刷新只读取 QMT 实时行情和 `research/alerts/intraday_rules.json`。趋势、估值分段、风控位、右侧确认位和仓位底图由盘前或每日规则生成脚本更新，盘中窗口不调用大模型、不临时发明新策略。
