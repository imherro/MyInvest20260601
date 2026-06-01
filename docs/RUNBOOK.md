# 日常运行手册

本文说明本项目每天、盘中、盘后和周末如何运行。目标是让任何一台电脑 clone 项目后，都能按固定顺序继续工作。

## 1. 每次开始前

1. 拉取最新项目。
2. 阅读 `README.md`、`docs/PROJECT_MEMORY.md`、`docs/MODULES.md`。
3. 阅读 `docs/DATA_SOURCES.md`，确认 Tushare 等数据源权限。
4. 查看 `research/logs/decision_log.md` 的最近记录。
5. 确认本次要做的是盘前、盘中、盘后、周末，还是临时事件更新。
6. 完成后提交并推送。

推荐开场指令：

```text
请先阅读 README.md、docs/PROJECT_MEMORY.md、docs/MODULES.md、docs/RUNBOOK.md、docs/DATA_SOURCES.md 和 research/logs/decision_log.md，然后按今天的任务继续。
本项目已知可使用 Tushare 数据权限；做 A 股结构化数据研究时请优先检查并使用本地 Tushare token。
```

## 2. 盘前流程

目标：形成当天仓位环境、操作计划和盘中触发条件。

步骤：

1. 更新市场仓位模块。
2. 检查主线登记册是否有重大变化。
3. 如有必要，更新相关 ETF/个股档案。
4. 更新或读取当前持仓快照。
5. 运行组合分析。
6. 生成盘前操作建议。
7. 写入决策日志。
8. 提交并推送。

产物：

```text
research/market/market_score_YYYY-MM-DD.md
research/market/market_score_YYYY-MM-DD.json
research/portfolio/portfolio_snapshot_YYYY-MM-DD.md
research/portfolio/portfolio_snapshot_YYYY-MM-DD.json
research/actions/action_plan_YYYY-MM-DD_premarket.md
research/actions/action_plan_YYYY-MM-DD_premarket.json
research/logs/decision_log.md
```

推荐指令：

```text
请按 docs/RUNBOOK.md 执行今日盘前流程。
先更新市场仓位，再检查主线登记册，然后基于持仓快照做组合分析，最后生成盘前操作建议。
不要临时重写前置研究结论；缺少研究时输出 ResearchFirst。
```

## 3. 盘中流程

目标：只检查已定义触发条件，不临时发明新策略。

步骤：

1. 读取当日盘前操作建议。
2. 读取 ETF/个股档案中的触发条件。
3. 检查是否触发买入、加仓、减仓、卖出、失效或风险条件。
4. 输出盘中提醒。
5. 如果实际执行，记录执行信息。
6. 必要时写入决策日志。
7. 提交并推送重要变更。

产物：

```text
research/alerts/intraday_alert_YYYY-MM-DD_HHMM.md
research/alerts/intraday_alert_YYYY-MM-DD_HHMM.json
research/logs/decision_log.md
```

推荐指令：

```text
请按 docs/modules/INTRADAY_ALERTS.md 检查当前盘中提醒。
只能检查盘前计划和标的档案中已经定义的触发条件。
如果缺少盘前计划或标的档案，输出 blocked。
```

## 4. 盘后流程

目标：复盘判断、提醒、执行和组合风险。

步骤：

1. 读取盘前市场仓位和操作建议。
2. 读取盘中提醒。
3. 读取实际操作记录。
4. 对比收盘市场表现和持仓变化。
5. 做盘后复盘。
6. 判断是否需要更新市场仓位、主线、ETF、个股或组合分析。
7. 写入决策日志。
8. 提交并推送。

产物：

```text
research/reviews/post_market_review_YYYY-MM-DD.md
research/reviews/post_market_review_YYYY-MM-DD.json
research/logs/decision_log.md
```

推荐指令：

```text
请按 docs/modules/POST_MARKET_REVIEW.md 做今日盘后复盘。
必须对比盘前计划、盘中提醒和实际执行。
不要用事后结果重写事前判断；如果缺少实际执行信息，请明确标注。
```

## 5. 周末流程

目标：做更完整的市场、主线、组合和规则复盘。

步骤：

1. 汇总本周市场仓位变化。
2. 做完整主线研究，更新 `research/themes/theme_registry.json`。
3. 更新需要变化的 ETF/个股档案。
4. 做完整组合分析。
5. 检查决策日志中的重复偏差。
6. 判断是否需要修正规则。
7. 更新项目记忆。
8. 提交并推送。

产物：

```text
research/themes/theme_review_YYYY-MM-DD.md
research/themes/theme_review_YYYY-MM-DD.json
research/themes/theme_registry.json
research/portfolio/portfolio_snapshot_YYYY-MM-DD.md
research/reviews/post_market_review_YYYY-MM-DD_weekly.md
research/logs/decision_log.md
docs/PROJECT_MEMORY.md
```

推荐指令：

```text
请按 docs/RUNBOOK.md 执行周末流程。
重点更新主线研究、组合分析和决策日志，检查本周是否存在重复偏差。
只有发现重复问题或明确规则缺陷时，才建议修改项目规则。
```

## 6. 临时事件流程

适用场景：

- 重大政策变化
- 市场暴跌或暴涨
- 持仓公司重大公告
- 财报发布
- 主线突发变化
- ETF/个股触发失效条件

步骤：

1. 判断事件影响哪个模块。
2. 只更新受影响模块。
3. 标记变化类型和原因。
4. 如果影响仓位或操作，生成临时操作建议。
5. 写入决策日志。
6. 提交并推送。

推荐指令：

```text
请按 docs/RUNBOOK.md 处理临时事件。
先判断影响市场仓位、主线、ETF、个股、组合还是操作建议，只更新受影响模块。
不要因为单条新闻推翻整个系统。
```

## 7. 提交规则

每次完成一个清晰阶段后提交。

推荐提交信息：

```text
research: update market position
research: update theme review
portfolio: update holdings analysis
actions: add premarket action plan
review: add post-market review
docs: update project memory
```

提交前检查：

- 没有提交 `.env`。
- 重要结论已写入 Markdown 和 JSON。
- 结论变化有原因。
- 操作建议有依据、触发条件和失效条件。
- 重要变化已写入 `research/logs/decision_log.md`。

## 8. 当前系统状态

已建立：

- 市场仓位模块
- 主线研究模块
- ETF 研究模块
- 个股研究模块
- 组合分析模块
- 操作建议模块
- 盘中提醒模块
- 盘后复盘模块
- 决策日志模块

尚未完成：

- 首次正式市场仓位报告
- 首次正式主线研究
- 真实持仓快照
- ETF/个股首批档案
- 自动化数据接入
