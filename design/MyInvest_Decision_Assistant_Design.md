# MyInvest Decision Assistant 设计文档

版本：v0.2
日期：2026-06-12
适用范围：MyInvest DB-first worktree / Web 只读决策辅助层
状态：可执行设计

---

## 1. 目标

从用户角度，系统下一阶段要解决三个问题：

1. 提升收益：让用户更早看到市场状态、仓位偏离、研究阻塞和可准备事项。
2. 降低风险：把分散的 ResearchFirst、估值、流动性、仓位偏离、盘中规则和系统检查汇总成可扫描风险图。
3. 方便好用：把“今天先看哪里、下一步点哪里、为什么不能做某事”做成日常入口，而不是让用户在多个页面里找线索。

本设计新增 **Decision Assistant 决策辅助层**。它不是新的投资生成器，不产生新的买卖观点，不连接交易接口，只把 current-only 和 history DB 的既有事实组织成更好用的只读页面/API。

## 2. 硬边界

- 只读 Web 页面和 `GET /api/...` API。
- 数据来自 `temp/web_db/myinvest.sqlite` current-only Web cache 和 `temp/history_db/` 历史事实库查询服务。
- 不写研究 JSON/MD，不生成新投资观点。
- 不展示金额、股数、账户、订单、成交、成本、资产总额、本地绝对路径。
- 股票价格、估值区间、比例、百分点、状态、原因、日期、相对路径是允许字段。
- 不新增 QMT 写入、下单、撤单、改单或自动交易能力。
- 情景推演只复用已固化的市场仓位映射，不临时改写策略。

## 3. 用户体验结构

新增一个主入口：

```text
/assistant
```

页面名称：`每日指挥台`

页面分区：

1. **今日状态**
   - 市场分数/状态
   - 权益当前比例与目标区间
   - 现金/短融当前比例与目标区间
   - ResearchFirst 阻塞数量
   - 系统/盘中规则状态

2. **下一步**
   - 按盘前、盘中、盘后三个流程列出优先入口。
   - 每个入口说明为什么要看、会解决什么问题。

3. **风险热力图**
   - 仓位偏离风险
   - ResearchFirst 风险
   - 估值缺失/过期风险
   - 流动性缺口风险
   - 盘中规则 stale/degraded 风险
   - 系统检查风险
   - 历史库质量风险

4. **研究优先级**
   - 当前持仓优先。
   - 仓位比例越高优先级越高。
   - ResearchFirst 阻塞项优先。
   - 估值/流动性/Profile 缺口越多优先级越高。
   - 即将影响操作计划或 bucket 偏离的标的优先。

5. **情景推演**
   - 使用市场仓位映射模拟若市场分数变化，权益/现金目标区间如何变化。
   - 默认展示当前分数、当前分数 -10、当前分数 -5、当前分数 +5、当前分数 +10。
   - 只展示区间变化和需要复核事项，不生成交易动作。

6. **仓位偏离**
   - 按 bucket 展示 actual、target、gap、状态。
   - 点到仓位钻取和历史缺口页面。

7. **决策复盘线索**
   - 展示最近决策事件类型、数量和复盘入口。
   - 提示哪些规则或阻塞项需要盘后复盘，不判断策略对错。

8. **解释层**
   - 每个风险/建议入口有 `why` 和 `next_step`。
   - 用户能看到“为什么被阻塞”“为什么需要先研究”“为什么是当前风险等级”。

## 4. API 设计

新增：

```text
GET /api/assistant/daily
```

响应结构：

```json
{
  "module": "decision_assistant_daily",
  "current_only": true,
  "generated_at": "...",
  "today": {...},
  "next_steps": [...],
  "risk_heatmap": {"summary": {...}, "items": [...]},
  "research_priorities": {"summary": {...}, "items": [...]},
  "scenario_simulation": {"summary": {...}, "items": [...]},
  "allocation_drift": {"summary": {...}, "items": [...]},
  "review_loop": {"summary": {...}, "items": [...]},
  "history_visuals": [...],
  "explanations": [...],
  "safety": {...}
}
```

所有字段必须通过 `RatioOnlyService.assert_safe`。

## 5. 数据来源

| 功能 | 数据服务 |
|---|---|
| 今日状态 | `CurrentStateService`、`DashboardService`、`SystemCheckService` |
| 风险热力图 | `SubjectStatusService`、`SubjectGapService`、`HistoryWorkbenchService`、`CurrentStateService` |
| 研究优先级 | `SubjectStatusService`、`SubjectGapService`、`CurrentStateService.action_plan()` |
| 情景推演 | `MarketPositionService.get_position_for_score()` |
| 仓位偏离 | `CurrentStateService.target_allocation()`、`SubjectGapService.gap()` |
| 复盘线索 | `DecisionTimelineService`、`CurrentStateService.decision_log_entries()` |
| 历史可视化 | `HistoricalMetricsService`、`HistoryGapDashboardService`、History workbench pages |

## 6. 风险等级规则

统一等级：

- `ok`：无需处理。
- `watch`：需要关注，但不阻塞。
- `warn`：建议复核。
- `block`：阻塞新增动作或需要先处理。

风险等级只代表工作流优先级，不代表买卖建议。

## 7. 开发计划

### MIV-DA-001 设计文档

- 新增本设计文档。
- 明确只读、ratio-only、ResearchFirst、current-only 和 no-trading 边界。

### MIV-DA-002 Decision Assistant 服务

- 新增 `web/backend/app/services/decision_assistant.py`。
- 汇总 daily payload。
- 实现风险热力图、研究优先级、情景推演、仓位偏离、复盘线索、解释层。
- 所有输出走 ratio-only 检查。

### MIV-DA-003 API 与页面

- 新增 `GET /api/assistant/daily`。
- 新增 `/assistant` 页面。
- 顶部“总览”或角色工作台增加入口。

### MIV-DA-004 前端展示

- 新增模板 `decision_assistant.html`。
- 复用现有 CSS 风格，避免营销化页面。
- 支持窄屏无横向溢出。

### MIV-DA-005 测试与验收

- 新增服务/API/页面测试。
- 更新 `scripts/web_check.py` 页面和交互 marker。
- 运行：

```bash
python -m pytest web/backend/tests -q
python -m pytest tests -q
python scripts/project_check.py --current-only
python scripts/web_check.py
python scripts/web_release_check.py
```

### MIV-DA-006 后续增强

- 用户偏好模拟：保守/平衡/进取模式仅做只读 preview。
- 更细的历史 DB 图表：估值区间带、市场分数与仓位区间曲线、ResearchFirst 阻塞趋势。
- 复盘质量评分：只基于已记录事实，不使用未来函数，不写交易结论。

## 8. 验收标准

- `/assistant` 返回 200。
- `/api/assistant/daily` 返回 ratio-only、安全、current-only payload。
- 页面包含每日状态、下一步、风险热力图、研究优先级、情景推演、仓位偏离、复盘线索。
- 不出现本地绝对路径。
- 不新增 POST/PUT/PATCH/DELETE API。
- 不改动研究 JSON/MD，不写交易能力。
- Web smoke 和 release check 通过。

---

## 9. 第二阶段：完整 Assistant Suite

用户要求把前面讨论过的功能全部进入设计和开发，不只限于风险预警中心、研究任务闭环、标的详情中心。第二阶段采用一个统一套件：

```text
/assistant/risk-center
/assistant/research-tasks
/assistant/preferences
/assistant/scenarios
/assistant/history-visuals
/assistant/review-score
/assistant/premarket
/assistant/search
/assistant/securities/{code}
/assistant/weekly-safety
```

对应 API：

```text
GET /api/assistant/risk-center
GET /api/assistant/research-tasks
GET /api/assistant/preferences
GET /api/assistant/scenarios
GET /api/assistant/history-visuals
GET /api/assistant/review-score
GET /api/assistant/premarket
GET /api/assistant/search?q=...
GET /api/assistant/securities/{code}
GET /api/assistant/weekly-safety
```

### 9.1 风险预警中心

目标：把每日指挥台里的风险热力图独立成可筛选工作台。

内容：

- 风险等级汇总。
- 风险类型、原因、影响、下一步入口。
- 支持按 `category` 聚合：allocation、research、valuation、liquidity、intraday、system、history。

### 9.2 研究任务闭环

目标：把研究优先级升级为任务闭环。

任务状态：

- `pending`：存在 profile/valuation/liquidity/theme 缺口。
- `blocked`：已被 ResearchFirst 阻塞。
- `review`：缺口较轻或需要人工复核。
- `complete`：当前无缺口，仅保留参考。

字段：

- code、name、bucket、priority、status、missing_reasons、why、next_step、影响入口。

### 9.3 偏好模拟

目标：提供保守、平衡、进取三种只读 preview。

规则：

- 不改变正式 target allocation。
- 保守模式将权益目标区间下移 5pp。
- 平衡模式使用当前正式目标区间。
- 进取模式将权益目标区间上移 5pp。
- 所有区间限制在 0%-100%。

输出仅用于理解风险偏好差异，不作为操作建议。

### 9.4 深度情景推演

目标：在市场分数变化之外，联动展示：

- 权益/现金区间变化。
- bucket 偏离是否仍是关键风险。
- ResearchFirst 阻塞是否会限制加仓。
- 盘中规则是否是关键风险。

### 9.5 历史可视化增强

目标：集中展示当前已有历史图表入口和可用序列。

入口：

- 市场历史。
- bucket gap 历史。
- 标的估值历史。
- ResearchFirst/标的状态趋势。
- 决策事件趋势。

第一版不新增复杂图形库，先用当前 HTML 表格和现有历史页面承接。

### 9.6 复盘评分

目标：用规则遵守情况评价复盘质量，不评价收益金额。

评分项：

- ResearchFirst discipline。
- allocation drift control。
- intraday freshness。
- system readiness。
- history readiness。

评分只基于当前状态和历史事实，不生成交易结论。

### 9.7 一键盘前流程

目标：按盘前工作顺序组织页面和工具入口。

步骤：

1. 刷新 Web DB。
2. 项目 current-only 检查。
3. 每日指挥台。
4. 风险预警中心。
5. 研究任务闭环。
6. 操作计划。
7. 盘中规则。

工具入口必须继续走现有工具注册表，不执行任意命令。

### 9.8 全局搜索

目标：搜索页面、工具、标的、bucket、主题和历史入口。

第一版只读实现：

- 从 current Web DB 服务聚合候选。
- 支持 `q` 参数。
- 不扫描本地敏感文件，不暴露本地绝对路径。

### 9.9 标的详情中心

目标：每个 ETF/个股有统一入口。

内容：

- 当前 ResearchFirst 状态。
- profile/valuation/liquidity 状态。
- 当前 bucket、持仓比例、bucket gap。
- 历史估值、仓位、动作、档案数量。
- 相关页面入口。

### 9.10 安全周报

目标：以 ratio-only 方式汇总一周安全状态。

内容：

- 风险预警汇总。
- 研究任务汇总。
- 复盘评分。
- 历史库质量。
- 下周优先入口。

第一版只做只读页面/API，不生成文件、不写入 research。

## 10. 第二阶段开发计划

### MIV-DA-101 设计升级

- 更新本文档为 v0.2。
- 明确 10 个功能的 URL、API、边界和验收。

### MIV-DA-102 服务扩展

- 在 `DecisionAssistantService` 增加：
  - `risk_center()`
  - `research_tasks()`
  - `preference_simulation()`
  - `deep_scenarios()`
  - `history_visuals_page()`
  - `review_score()`
  - `premarket_workflow()`
  - `global_search(q)`
  - `security_center(code)`
  - `weekly_safety()`

### MIV-DA-103 API 和页面

- 为 10 个功能新增 GET API 和页面。
- 使用现有 FastAPI/Jinja2，不引入新前端框架。

### MIV-DA-104 导航与入口

- 在每日指挥台和 Dashboard 快捷入口加入 Assistant Suite。
- 在角色工作台加入对应入口。

### MIV-DA-105 测试与验收

- 新增服务/API/页面测试。
- 更新 `scripts/web_check.py` 的 API、页面和 marker。
- 浏览器验证桌面和 390px 窄屏。

验收命令：

```bash
python -m pytest web/backend/tests -q
python -m pytest tests -q
python scripts/project_check.py --current-only
python scripts/db_migrate.py --db temp/history_db/test_myinvest_history.sqlite3 --check
python scripts/web_check.py
python scripts/web_release_check.py
```
