# 盘前策略简报模块

本模块用于生成类似券商晨报的盘前综合报告。用户说“盘前分析”“盘前策略”“策略简报”“今日晨报”“市场策略”时，默认进入本模块。

本模块不是操作建议模块。它可以给出市场判断、重点方向、核心观点、风险提示和需要跟踪的条件，但不能绕过 `ACTION_PLAN` 直接生成买入、加仓、减仓或卖出动作。

## 1. 模块目标

回答八个问题：

1. 昨夜和今早有哪些重大新闻、政策、公告或外盘事件？
2. 这些事件影响市场仓位、主线、行业、ETF、个股还是组合风险？
3. 今日市场环境是进攻、防守、观望，还是只允许减风险？
4. 今日策略精要是什么？
5. 今日重点方向和需要回避的方向是什么？
6. 今日核心观点有哪些？
7. 今日盘中需要重点观察哪些触发条件？
8. 哪些结论必须交给市场仓位、主线研究、ETF/个股研究、操作建议或盘前执行检查模块处理？

## 2. 必须读取的前置文件

至少读取：

- `README.md`
- `docs/PROJECT_MEMORY.md`
- `docs/DAILY_PROCESS.md`
- `docs/DATA_SOURCES.md`
- `docs/FILE_NAMING.md`
- 最新市场仓位报告：`research/market/market_score_*.md/json`
- 最新主线研究报告：`research/themes/theme_review_*.md/json`
- `research/themes/theme_registry.json`
- 最新组合快照：`research/portfolio/portfolio_snapshot_*.md/json`
- ETF 登记册：`research/etfs/etf_registry.json`
- 个股登记册：`research/stocks/stock_registry.json`
- 最新操作建议，如存在：`research/actions/action_plan_*.md/json`
- 最新盘前执行检查，如存在：`research/checks/premarket_check_*.md/json`
- 决策日志：`research/logs/decision_log.md`

如涉及 A 股行情、指数、ETF、估值、财务或交易日历，必须先按 `docs/DATA_SOURCES.md` 检查并优先使用本地 Tushare。新闻、政策、公告和海外市场信息可以使用网页或公开来源补充，但必须注明来源和日期。

## 3. 输出内容

每份盘前策略简报必须包含：

- 读取文件和数据来源
- 重大新闻与事件清单
- 策略精要
- 市场分析
- 重点方向
- 核心观点
- 今日可关注条件
- 今日禁止事项
- 风险提示
- 需要交给其他模块处理的问题
- 决策日志条目

重大新闻必须区分：

| 类型 | 说明 |
| --- | --- |
| policy | 政策、监管、央行、部委、交易所事件 |
| macro | 汇率、利率、商品、海外市场、宏观数据 |
| industry | 行业景气、订单、价格、产业事件 |
| company | 持仓或观察股公告、财报、风险事件 |
| market | 指数、成交、资金、风格、外盘表现 |

## 4. 简报结论类型

| 结论 | 含义 |
| --- | --- |
| offensive_allowed | 市场和主线允许在条件触发后考虑新增风险 |
| verify_only | 只允许观察和验证触发条件 |
| risk_reduce_or_watch_only | 只允许减风险或观察，不新增进攻仓 |
| research_first | 重点标的或方向缺少档案，必须先补研究 |
| blocked | 关键前置文件或数据缺失，不能形成可靠盘前策略 |

## 5. 与其他模块的边界

本模块可以说：

- “今日策略精要：弱修复但不追涨，进攻仓只验证不新增。”
- “重点方向：AI 应用只观察修复，半导体仍需等待止跌确认。”
- “重大新闻影响：某政策利好电网设备，但主线评级仍需由主线研究模块复核。”
- “今日禁止事项：不新增未建档 ETF，不把新闻利好直接转成买入建议。”

本模块不能说：

- “买入某 ETF 多少仓位。”
- “减仓某股票多少仓位。”
- “把某主题临时升为 A 档。”
- “绕过缺失档案直接给买卖结论。”

如果用户明确要求“能不能买、买多少、减多少”，本模块只能先生成策略简报或指出需要进入 `ACTION_PLAN`。最终动作由操作建议模块读取本模块和其他前置研究后生成。

## 6. 文件输出

标准输出：

```text
research/briefings/strategy_briefing_YYYY-MM-DD_HHMMSS.md
research/briefings/strategy_briefing_YYYY-MM-DD_HHMMSS.json
```

重要简报应写入：

```text
research/logs/decision_log.md
```

## 7. 使用提示词

```text
请按 docs/modules/STRATEGY_BRIEFING.md 生成今日盘前策略简报。
风格参考券商晨报，包含重大新闻、策略精要、市场分析、重点方向、核心观点和风险提示。
必须读取最新市场仓位、主线研究、组合快照、ETF/个股登记册、最新操作建议和决策日志。
如涉及 A 股结构化数据，优先使用本地 Tushare；新闻和政策必须注明来源和日期。
可以给方向、观点和条件，不要绕过 ACTION_PLAN 直接生成买卖指令。
```
