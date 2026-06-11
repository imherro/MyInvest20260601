# MyInvest Decision Assistant 设计文档

版本：v0.1
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
