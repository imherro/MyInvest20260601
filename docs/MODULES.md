# 模块架构

## DB-first history module

The DB-first history module is a derived fact layer, not a trading module and
not a replacement for timestamped research artifacts.

Responsibilities:

- migrate a local SQLite schema under `temp/history_db/`
- ingest existing research JSON artifacts
- normalize durable valuation, portfolio, target allocation, action, market,
  theme, and security profile facts
- provide read-only query CLIs and read-only Web history pages
- support optional generator dual-write with `--db`

Inputs:

- `research/**/*.json`
- generated JSON artifacts from supported generators when `--db` is passed

Outputs:

- SQLite rows under `temp/history_db/*.sqlite3`
- read-only API responses from existing `web/backend`
- query command output from `scripts/db_query_*_history.py`

Boundaries:

- no automatic trading
- no QMT write operation
- no order placement, cancellation, or modification
- no DB files committed to Git
- no amount, quantity, account, order, fill, deal, credential, or local absolute path in DB/Web output
- security prices are allowed research facts and are not private by themselves

本文定义本项目的模块边界。原则是：每个模块只解决一个层级的问题，研究结论先保存，后续建议必须引用已有结论。

## 总流程

```text
读取项目记忆和已有研究
→ 更新市场仓位
→ 更新主线研究
→ 更新 ETF/个股档案
→ 分析当前组合
→ 生成盘前策略简报
→ 生成操作建议
→ 盘前执行检查
→ 记录决策日志
→ 盘中提醒
→ 盘后复盘
```

盘前策略简报模块提供类似券商晨报的综合视图，但不替代操作建议。操作建议模块不能绕过前置研究直接给出买卖结论。

## 数据源路由

各模块使用数据前必须先读取 `docs/DATA_SOURCES.md`。当前默认分工：

- Tushare：A 股结构化行情、指数、ETF/基金、财务、估值和交易日历主数据源。
- QMT / XtQuant：A 股盘中实时行情、本地终端行情、触发条件验证。
- BaoStock：A 股历史行情、指数和部分财务数据的免费补充与交叉验证。
- yfinance / Yahoo Finance：海外股票、海外 ETF、海外指数、ADR 和跨市场资产行情补充。
- FRED：美国及全球宏观时间序列，包括利率、通胀、就业、金融条件和外部风险偏好。

使用 yfinance 或 FRED 时，报告必须注明来源、代码、日期、币种或指标口径。A 股主数据源优先级不变：Tushare、QMT、BaoStock 仍优先于 yfinance。

## 01 市场仓位模块

职责：决定当前总权益仓位区间。

核心问题：

- 当前适合多少股票/ETF 权益仓位？
- 债券、短融、现金类仓位应该保留多少？
- 当前市场是进攻、防守还是观望？

输入：

- 指数趋势
- 市场广度
- 成交量与流动性
- 资金流与风险偏好
- 主线强度
- 估值赔率
- 宏观政策环境
- 海外市场、美元利率、美元指数和全球风险偏好；需要时使用 yfinance 和 FRED
- 拥挤惩罚

输出：

- 市场机会分数
- 拥挤惩罚
- 市场仓位分数
- 建议权益仓位区间
- 债券/现金仓位区间
- 主要风险
- 对进攻仓的限制

更新频率：

- 盘前每日简版
- 周末完整版
- 重大政策、暴跌、暴涨时临时更新

禁止事项：

- 不推荐具体股票。
- 不临时改写主线评级。
- 不因为单日大涨大跌直接推翻仓位框架。

## 02 主线研究模块

职责：判断 A 股当前主线、主线等级和变化原因。

核心问题：

- 当前 A/B/C/D 档主线分别是什么？
- 哪些主线上调、下调、维持、移出或新增？
- 哪些方向可以进入进攻仓？

输入：

- 行业和主题表现
- ETF 趋势和成交
- 龙头股强度
- 产业逻辑
- 政策催化
- 资金参与程度
- 板块内部扩散情况

输出：

- 主线评级
- 主线评分
- 变化类型
- 变化原因
- 对仓位的影响
- 对应 ETF 和龙头观察池

更新频率：

- 每周完整版
- 盘前只做重大变化检查
- 重大事件时临时更新

禁止事项：

- 不在操作建议中临时重写主线。
- 不把短期主题暴涨直接升级为 A 档。
- 不只根据新闻热度给主线评级。

## 03 ETF 研究模块

职责：单独分析每只 ETF 的角色、估值、趋势、风险和操作条件。

核心问题：

- 这只 ETF 属于核心仓、进攻仓、防御仓还是主题仓？
- 当前适合买、持有、加仓、减仓还是观察？
- 它对应的主线或指数是否仍然有效？

输入：

- 跟踪指数
- 成分结构
- 估值分位
- 趋势状态
- 成交和资金流
- 对应主线评级
- 与组合中其他资产的重叠度

输出：

- ETF 角色
- 当前评级
- 目标仓位区间
- 买入条件
- 加仓条件
- 减仓条件
- 失效条件

更新频率：

- 每周或触发条件更新
- 主线评级变化时更新
- 估值或趋势明显变化时更新

禁止事项：

- 不把 ETF 当成单一个股分析。
- 不忽略成分股重叠导致的集中风险。
- 不用短期涨跌替代指数估值和结构判断。

## 04 个股研究模块

职责：单独分析每只股票的商业逻辑、估值、业绩、风险和操作条件。

核心问题：

- 这家公司是否值得持有？
- 当前价格是否有赔率？
- 买入逻辑是否仍然成立？
- 触发减仓或卖出的条件是什么？

输入：

- 公司业务
- 行业景气
- 财务和业绩预期
- 估值区间
- 竞争格局
- 风险事件
- 技术状态
- 所属主线评级

输出：

- 投资逻辑
- 估值判断
- 当前评级
- 目标仓位区间
- 买入条件
- 加仓条件
- 减仓条件
- 卖出/失效条件
- 核心风险

更新频率：

- 财报后更新
- 重大公告后更新
- 价格或估值明显偏离时更新
- 主线降级时检查

禁止事项：

- 不只因为所属主线强就忽视个股估值和风险。
- 不把短线交易理由包装成长线逻辑。
- 不给没有失效条件的买入建议。

## 05 组合分析模块

职责：判断当前持仓是否匹配市场仓位、主线评级和风险约束。

核心问题：

- 当前权益仓位是否过高或过低？
- 核心仓、进攻仓、防御仓、主题仓比例是否合理？
- 行业和单一主线是否过度集中？
- 持仓是否与已固化研究结论一致？

输入：

- 当前持仓
- 现金/债券仓位
- 市场仓位分数
- 主线评级
- ETF 档案
- 个股档案
- 硬约束

输出：

- 当前组合偏离
- 需要调整的仓位
- 风险暴露
- 优先处理项
- 不建议操作项

更新频率：

- 每次操作前
- 每周完整版
- 组合发生明显变化后

禁止事项：

- 不绕过市场仓位和主线结论直接推荐买卖。
- 不只看单个标的，忽略组合整体风险。

## 06 操作建议模块

职责：基于前置研究成果，给出具体买、卖、加、减、持有、观察建议。

核心问题：

- 今天是否需要操作？
- 如果操作，操作哪个标的、多少仓位、为什么？
- 如果不操作，是因为没有机会、等待确认，还是风险过高？

输入：

- 市场仓位结论
- 主线研究结论
- ETF/个股档案
- 组合分析
- 盘中触发条件

输出：

- 操作类型
- 标的
- 建议仓位变化
- 依据
- 失效条件
- 风险提示
- 复盘点

更新频率：

- 盘前
- 盘中触发条件出现时
- 盘后复盘前

禁止事项：

- 不凭空给建议。
- 不重写市场仓位或主线评级。
- 不给没有依据、没有条件、没有复盘点的操作。

## 07 盘前策略简报模块

职责：生成类似券商晨报的盘前综合报告，汇总重大新闻、策略精要、市场分析、重点方向、核心观点和风险提示。

触发口径：

- 用户说“盘前分析”“盘前策略”“策略简报”“今日晨报”“市场策略”时，默认使用本模块。
- 如果用户明确说“盘前执行检查”，才只进入盘前执行检查模块。

核心问题：

- 昨夜和今早有哪些重大新闻、政策、公告或外盘事件？
- 这些事件影响市场仓位、主线、ETF、个股还是组合风险？
- 今日市场环境是进攻、防守、观望，还是只允许减风险？
- 今日重点方向和核心观点是什么？
- 今日有哪些观察条件、禁止事项和风险提示？

输入：

- 最新市场仓位报告
- 最新主线研究和主线登记册
- 最新组合快照
- ETF/个股登记册和档案
- 最新操作建议和盘前执行检查，如存在
- 新闻、政策、公告、外盘和宏观事件来源；海外行情可用 yfinance，宏观序列可用 FRED
- 决策日志

输出：

- 重大新闻与事件清单
- 策略精要
- 市场分析
- 重点方向
- 核心观点
- 今日观察清单
- 风险提示和禁止事项
- 需要交给其他模块处理的问题

更新频率：

- 每个交易日盘前
- 重大隔夜新闻或政策事件后
- 市场大幅波动或主线突发变化后

禁止事项：

- 不直接生成买入、加仓、减仓或卖出动作。
- 不临时改写市场仓位或主线评级。
- 不把新闻利好直接转换为买入建议。
- 不新增未建档标的。
- 不使用金额。

## 08 盘前执行检查模块

职责：在开盘前确认已有研究和操作建议是否可以进入执行。

核心问题：

- 前置文件是否齐全、最新、可用？
- 市场仓位、主线、组合和操作建议是否互相冲突？
- 今天允许新增操作、只允许减风险，还是只能观察？
- 盘中只需要监控哪些已定义触发条件？

输入：

- 每日流程标准
- 最新市场仓位
- 最新主线研究和主线登记册
- 最新组合快照
- ETF/个股登记册和档案
- 最新操作建议

输出：

- 执行门禁状态
- 今日允许动作范围
- 今日禁止事项
- 盘中监控清单
- blocked / ResearchFirst 清单

更新频率：

- 每个交易日盘前
- 操作建议变化后
- 重大隔夜事件后

禁止事项：

- 不给具体买卖动作。
- 不临时改写市场仓位或主线评级。
- 不新增未建档标的。
- 不使用金额。

## 09 盘中提醒模块

职责：监控已定义触发条件，并提醒是否需要执行原计划。

核心问题：

- 是否触发买入、加仓、减仓、止损、止盈或观察条件？
- 触发后是执行、等待确认，还是取消？

输入：

- 盘前操作计划
- 持仓标的触发条件
- 观察池触发条件
- 市场仓位限制
- 主线状态

输出：

- 触发提醒
- 对应原计划
- 建议动作
- 是否需要人工确认

更新频率：

- 盘中按触发条件

禁止事项：

- 不在盘中临时发明新策略。
- 不因为价格波动频繁改变原计划。

## 10 盘后复盘模块

职责：记录当天市场表现、操作执行、判断偏差和后续修正。

核心问题：

- 盘前判断是否正确？
- 操作是否执行？
- 执行是否符合计划？
- 哪些判断需要修正？

输入：

- 盘前分析
- 盘中提醒
- 实际操作
- 收盘市场表现
- 持仓表现

输出：

- 当日复盘
- 判断偏差
- 执行偏差
- 需要更新的研究文件
- 第二天观察重点

更新频率：

- 每日简版
- 周末完整版

禁止事项：

- 不只记录涨跌结果。
- 不把单日结果简单归因为策略正确或错误。

## 11 决策日志模块

职责：保存关键结论变化和操作理由，形成长期可追溯记录。

核心问题：

- 什么时候做了什么判断？
- 判断为什么变化？
- 当时依据是什么？
- 后来结果如何？

输入：

- 市场仓位变化
- 主线评级变化
- ETF/个股评级变化
- 操作建议
- 实际操作
- 复盘结论

输出：

- 日期
- 决策类型
- 原结论
- 新结论
- 变化原因
- 对仓位或操作的影响
- 后续复盘入口

更新频率：

- 每次重要结论变化后
- 每次实际操作后
- 每次规则修订后

禁止事项：

- 不覆盖旧记录。
- 不只记录结论，不记录原因。

## 文件产物建议

研究报告类文件必须按 `docs/FILE_NAMING.md` 使用日期加时间戳：`YYYY-MM-DD_HHMMSS`。基于前期研究时，默认读取同类文件中时间戳最新的版本，除非用户明确指定历史版本。

```text
research/
  market/
    market_score_YYYY-MM-DD_HHMMSS.md
    market_score_YYYY-MM-DD_HHMMSS.json
  themes/
    theme_review_YYYY-MM-DD_HHMMSS.md
    theme_review_YYYY-MM-DD_HHMMSS.json
    theme_registry.json
  etfs/
    ETF代码_名称_YYYY-MM-DD_HHMMSS.md
    ETF代码_名称_YYYY-MM-DD_HHMMSS.json
  stocks/
    股票代码_名称_YYYY-MM-DD_HHMMSS.md
    股票代码_名称_YYYY-MM-DD_HHMMSS.json
  portfolio/
    portfolio_snapshot_YYYY-MM-DD_HHMMSS.md
    portfolio_snapshot_YYYY-MM-DD_HHMMSS.json
  actions/
    action_plan_YYYY-MM-DD_HHMMSS_premarket.md
    action_plan_YYYY-MM-DD_HHMMSS_premarket.json
    action_plan_YYYY-MM-DD_HHMMSS_close.md
    action_plan_YYYY-MM-DD_HHMMSS_close.json
  briefings/
    strategy_briefing_YYYY-MM-DD_HHMMSS.md
    strategy_briefing_YYYY-MM-DD_HHMMSS.json
  checks/
    premarket_check_YYYY-MM-DD_HHMMSS.md
    premarket_check_YYYY-MM-DD_HHMMSS.json
  logs/
    decision_log.md
```

## 当前优先级

第一阶段先完成：

1. 市场仓位模块模板（已建立：`docs/modules/MARKET_POSITION.md`、`templates/market_score_template.md`、`templates/market_score_template.json`）
2. 主线研究模块模板（已建立：`docs/modules/THEME_RESEARCH.md`、`templates/theme_review_template.md`、`templates/theme_review_template.json`、`research/themes/theme_registry.json`）
3. ETF 档案模板（已建立：`docs/modules/ETF_RESEARCH.md`、`templates/etf_profile_template.md`、`templates/etf_profile_template.json`、`research/etfs/etf_registry.json`）
4. 个股档案模板（已建立：`docs/modules/STOCK_RESEARCH.md`、`templates/stock_profile_template.md`、`templates/stock_profile_template.json`、`research/stocks/stock_registry.json`）
5. 决策日志模板（已建立：`docs/modules/DECISION_LOG.md`、`templates/decision_log_entry_template.md`、`templates/decision_log_entry_template.json`、`research/logs/decision_log.md`）
6. 组合分析模块模板（已建立：`docs/modules/PORTFOLIO_ANALYSIS.md`、`templates/portfolio_snapshot_template.md`、`templates/portfolio_snapshot_template.json`、`research/portfolio/current_holdings_template.md`）
7. 操作建议模块模板（已建立：`docs/modules/ACTION_PLAN.md`、`templates/action_plan_template.md`、`templates/action_plan_template.json`）
8. 盘前策略简报模块模板（已建立：`docs/modules/STRATEGY_BRIEFING.md`、`templates/strategy_briefing_template.md`、`templates/strategy_briefing_template.json`）
9. 盘前执行检查模块模板（已建立：`docs/modules/PREMARKET_CHECK.md`、`templates/premarket_check_template.md`、`templates/premarket_check_template.json`）
10. 盘中提醒模块模板（已建立：`docs/modules/INTRADAY_ALERTS.md`、`templates/intraday_alert_template.md`、`templates/intraday_alert_template.json`）
11. 盘后复盘模块模板（已建立：`docs/modules/POST_MARKET_REVIEW.md`、`templates/post_market_review_template.md`、`templates/post_market_review_template.json`）

暂时不做：

- 自动化行情接入
- SQLite 数据库
- 复杂回测
- 盘中自动交易
