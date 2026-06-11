# 日常运行手册

## DB-first history runbook

Use the history DB only as a derived local fact store. It does not replace the
current `research/latest_index.json` flow.

Rebuild a test DB:

```bash
python scripts/db_migrate.py --db temp/history_db/test_myinvest_history.sqlite3 --reset
python scripts/db_ingest_research_artifacts.py --db temp/history_db/test_myinvest_history.sqlite3 --all
python scripts/project_check.py --current-only --db temp/history_db/test_myinvest_history.sqlite3 --db-strict
```

Rebuild the Web history DB:

```bash
python scripts/db_migrate.py --db temp/history_db/myinvest_history.sqlite3 --reset
python scripts/db_ingest_research_artifacts.py --db temp/history_db/myinvest_history.sqlite3 --all
python scripts/run_web.py --host 127.0.0.1 --port 8011
```

History Web pages:

- `/securities/{code}/valuation`
- `/market/history`
- `/positions/history`
- `/actions/history`
- `/history/quality`

Do not commit `temp/history_db/`, `temp/web_db/`, `.env`, runtime/cache files,
or SQLite files. Keep `temp/web_db/myinvest.sqlite` as the current-only Web
cache.

本文说明本项目每天、盘中、盘后和周末如何运行。目标是让任何一台电脑 clone 项目后，都能按固定顺序继续工作。

## 1. 每次开始前

1. 拉取最新项目。
2. 阅读 `README.md`、`docs/PROJECT_MEMORY.md`、`docs/MODULES.md`、`docs/WORKFLOW.md`。
3. 阅读 `docs/DATA_SOURCES.md`，确认 Tushare、QMT、BaoStock、yfinance、FRED 等数据源权限。
4. 阅读 `docs/FILE_NAMING.md`，确认文件命名和最新版本读取规则。
5. 阅读 `docs/DAILY_PROCESS.md`，确认本次要做的是读取、更新、复盘还是补研究。
6. 查看 `research/logs/decision_log.md` 的最近记录。
7. 读取 `research/latest_index.json`；如果索引缺失或明显过期，只运行 `python scripts/build_latest_index.py` 重建索引，不顺带生成其他研究产物。
8. 确认本次要做的是盘前、盘中、盘后、周末，还是临时事件更新。
9. 完成后先查看 `git status` 和暂存清单，只提交本次任务相关文件，再推送。

推荐开场指令：

```text
请先阅读 README.md、docs/PROJECT_MEMORY.md、docs/MODULES.md、docs/WORKFLOW.md、docs/RUNBOOK.md、docs/DAILY_PROCESS.md、docs/DATA_SOURCES.md、docs/FILE_NAMING.md、research/latest_index.json 和 research/logs/decision_log.md，然后按今天的任务继续。
本项目已知可使用 Tushare 数据权限；做 A 股结构化数据研究时请优先检查并使用本地 Tushare token。
如涉及盘中 A 股行情，可调用 QMT；如涉及海外行情、海外 ETF、ADR 或外盘风险，可调用 yfinance；如涉及美国利率、通胀、就业或全球宏观变量，可调用 FRED。
生成研究产物时文件名必须包含 YYYY-MM-DD_HHMMSS；基于前期研究时默认读取同类最新时间戳版本。
提交前先查看 git status，只提交本次任务相关文件，不混入其他未提交改动。
```

## 2. 盘前流程

目标：形成当天仓位环境、操作计划和盘中触发条件。具体是否需要重做市场仓位或主线研究，先按 `docs/DAILY_PROCESS.md` 判断。

步骤：

1. 读取最新市场仓位模块；必要时更新。
2. 读取主线登记册；只有触发条件变化时才更新主线研究。
3. 如有必要，更新相关 ETF/个股档案；缺档案时标记 ResearchFirst。
4. 读取或更新当前持仓快照。
5. 运行组合分析。
6. 如果用户说“盘前分析”“盘前策略”“策略简报”“今日晨报”或“市场策略”，生成盘前策略简报。
7. 生成盘前操作建议或读取已有操作建议。
8. 生成盘前执行检查。
9. 写入决策日志。
10. 提交并推送。

产物：

```text
research/market/market_score_YYYY-MM-DD_HHMMSS.md
research/market/market_score_YYYY-MM-DD_HHMMSS.json
research/portfolio/portfolio_snapshot_YYYY-MM-DD_HHMMSS.md
research/portfolio/portfolio_snapshot_YYYY-MM-DD_HHMMSS.json
research/briefings/strategy_briefing_YYYY-MM-DD_HHMMSS.md
research/briefings/strategy_briefing_YYYY-MM-DD_HHMMSS.json
research/actions/action_plan_YYYY-MM-DD_HHMMSS_premarket.md
research/actions/action_plan_YYYY-MM-DD_HHMMSS_premarket.json
research/checks/premarket_check_YYYY-MM-DD_HHMMSS.md
research/checks/premarket_check_YYYY-MM-DD_HHMMSS.json
research/logs/decision_log.md
```

推荐指令：

```text
请按 docs/RUNBOOK.md 和 docs/DAILY_PROCESS.md 执行今日盘前流程。
先读取最新市场仓位、主线登记册和组合快照；只有必要时才更新市场仓位或主线研究。
如果我说的是盘前分析、盘前策略或策略简报，请按 docs/modules/STRATEGY_BRIEFING.md 输出券商晨报式盘前策略简报，包含重大新闻、策略精要、市场分析、重点方向、核心观点和风险提示。
如操作建议已存在，请按 docs/modules/PREMARKET_CHECK.md 生成盘前执行检查。
必须运行或引用 scripts/check_valuation_updates.py；如估值报告缺失、过期或需要更新，先提示是否更新估值报告。
不要临时重写前置研究结论；缺少研究时输出 ResearchFirst。
```

## 3. 盘中流程

目标：只检查已定义触发条件，不临时发明新策略。

QMT 前置条件：

- 启动 QMT 行情/交易客户端时必须勾选“独立交易”。
- 登录完成后确认 QMT 行情页能正常刷新。
- 若未勾选“独立交易”，本项目可能能导入 QMT SDK，但 `get_full_tick` 会报“无法连接行情服务”或返回空行情。
- 自检命令：`py -3.11 scripts\intraday_dashboard.py --once-json`。

步骤：

1. 读取当日盘前操作建议或盘前执行检查。
2. 读取 `research/alerts/intraday_rules.json`，只使用已经固化的触发条件。
3. 读取 ETF/个股档案中的触发条件；如果档案或规则缺失，标记 `blocked`，不得临时补算。
4. 用 QMT 实时行情检查是否触发买入、加仓、减仓、卖出、失效、观察或风险条件。
5. 运行或引用 `scripts/check_valuation_updates.py`；若估值报告缺失、过期或实时区间跨出报告基准区间，只提示是否更新估值报告，不改变触发结论。
6. 输出盘中提醒。
7. 如果实际执行，记录执行信息。
8. 必要时写入决策日志。
9. 提交并推送重要变更。

产物：

```text
research/alerts/intraday_alert_YYYY-MM-DD_HHMMSS.md
research/alerts/intraday_alert_YYYY-MM-DD_HHMMSS.json
research/logs/decision_log.md
```

推荐指令：

```text
请按 docs/DAILY_PROCESS.md 和 docs/modules/INTRADAY_ALERTS.md 检查当前盘中提醒。
只能检查盘前计划、intraday_rules 和标的档案中已经定义的触发条件。
必须运行或引用 scripts/check_valuation_updates.py；估值更新提示只作为数据质量提示，不新增交易条件。
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
research/reviews/post_market_review_YYYY-MM-DD_HHMMSS.md
research/reviews/post_market_review_YYYY-MM-DD_HHMMSS.json
research/logs/decision_log.md
```

推荐指令：

```text
请按 docs/DAILY_PROCESS.md 和 docs/modules/POST_MARKET_REVIEW.md 做今日盘后复盘。
必须对比盘前计划、盘中提醒和实际执行。
必须运行或引用 scripts/check_valuation_updates.py；如缺估值、估值过期或盘中跨区，先提示是否更新估值报告。
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
research/themes/theme_review_YYYY-MM-DD_HHMMSS.md
research/themes/theme_review_YYYY-MM-DD_HHMMSS.json
research/themes/theme_registry.json
research/portfolio/portfolio_snapshot_YYYY-MM-DD_HHMMSS.md
research/reviews/post_market_review_YYYY-MM-DD_HHMMSS_weekly.md
research/logs/decision_log.md
docs/PROJECT_MEMORY.md
```

推荐指令：

```text
请按 docs/RUNBOOK.md 和 docs/DAILY_PROCESS.md 执行周末流程。
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
briefing: add premarket strategy briefing
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
- 提交前查看 `git status` 和 `git diff --cached --name-status`，只暂存本次任务相关文件。
- 如果工作区已有其他未提交改动，保留它们，不要为本次任务顺手提交或回退。

## 8. 当前系统状态

已建立：

- 市场仓位模块
- 主线研究模块
- ETF 研究模块
- 个股研究模块
- 组合分析模块
- 操作建议模块
- 盘前策略简报模块
- 盘前执行检查模块
- 盘中提醒模块
- 盘后复盘模块
- 决策日志模块

尚未完成：

- 补齐全部持仓个股档案
- 补齐持仓中尚未建档的 ETF 档案
- 完成操作建议、盘中提醒和盘后复盘的持续样例
- 自动化交易、数据库化沉淀和更完整的质量检查
