# MyInvest Web 版需求手册（B/S Read-only MVP）

> 基于开发种子包：`MyInvest_dev_web_seed_2026-06-09_165947.zip`
> 整理日期：2026-06-09
> 默认口径：**current-only**，即 Web 默认只读取 `research/latest_index.json` 的 `modules` 当前指针。
> 当前种子包中 `latest_index.modules.action_plan.path` 指向：`research/actions/action_plan_2026-06-09_160249_latest_ratio_only.json`。

---

## 1. 项目目标

MyInvest Web 版的第一阶段目标是把现有本地 A 股投资研究系统改造成一个**本地浏览器可访问的只读 B/S Dashboard**。

它不是自动交易系统，不生成订单，不接入 QMT 下单，不展示金额、股数、账号、成交、订单等敏感信息。

第一阶段只解决：

1. 通过浏览器查看当前有效研究状态。
2. 展示当前 action plan、target allocation、bucket gap、ResearchFirst gate、intraday rules、portfolio ratio snapshot、decision log 摘要。
3. 保持 `ratio-only` 隐私边界。
4. 保持 `ResearchFirst` 门禁。
5. 使用 `latest_index.modules` 作为 current-only 的唯一当前入口。
6. 让后续 Phase 2 可以平滑引入 SQLite/DuckDB 缓存层。

---

## 2. 非目标

Phase 1 明确不做：

- 不自动下单。
- 不生成真实委托。
- 不展示总资产、单项金额、市值、股数、可用数量、交易金额、盈亏金额、账号。
- 不读取 `.env` 给前端。
- 不暴露本地绝对路径。
- 不把 `runtime/`、`temp/`、数据库、缓存、日志、QMT 原始导出暴露给 Web。
- 不把历史文件默认为当前状态。
- 不绕过 `ResearchFirst`。
- 不把主题热度直接转成买卖动作。
- 不把前端做成研究结论生成器；前端只展示后端返回的受控 JSON。

---

## 3. 用户角色

### 3.1 个人投资研究员

查看每日市场状态、仓位区间、组合比例偏离、ResearchFirst 阻塞项和风险提示。

### 3.2 系统审计员

检查当前 action plan 是否满足：

- ratio-only
- ResearchFirst gate
- bucket allocation consistency
- current-only index consistency
- sensitive scan
- project check

### 3.3 后续开发者 / Codex

基于明确 API、页面、边界和验收标准开发 Web MVP，不改变交易/研究业务逻辑。

---

## 4. 硬边界

### 4.1 Ratio-only 隐私边界

Web API 和页面只允许展示：

- 比例
- 百分点变化
- 目标区间
- bucket 名称
- action type
- gate status
- research blocking reason
- 文件相对路径
- generated_at / basis_trade_date
- 风险说明
- 审计状态

Web API 和页面禁止展示：

- total asset / 总资产
- amount / 金额
- market value / 市值
- shares / 股数
- quantity / 数量
- available quantity / 可用数量
- trade amount / 交易金额
- profit amount / 盈亏金额
- full account / 完整账号
- order id / 委托编号
- fill / 成交记录
- 本地绝对路径，例如 `C:/Users/`、`C:\Users\`、`/Users/`、`/home/`

### 4.2 ResearchFirst 门禁

任何单标的 `buy/add/reduce/sell` 必须同时满足：

- profile pass
- valuation pass
- liquidity pass

现金/短融工具还必须满足：

- valuation pass
- liquidity pass
- duration boundary confirmed
- interest-rate risk disclosed
- credit risk disclosed
- liquidity risk disclosed

如果门禁不通过，Web 只允许展示：

- `research_first`
- `hold`
- `no_action`
- `watch`
- `blocked`

不得展示为可执行 `buy/add/reduce/sell`。

### 4.3 Current-only 口径

Web 默认只使用：

```text
research/latest_index.json -> modules -> path
```

不得把 `latest_index.files` 或目录中的历史文件当作当前状态。

历史文件只能在单独的 History 页面中显示，并必须标明：

```text
not current
```

Phase 1 可以暂不实现 History 页面。

---

## 5. 当前种子包的关键当前指针

当前 `latest_index.generated_at`：

```text
2026-06-09_163940
```

当前模块示例：

| 模块 | 当前路径 |
|---|---|
| action_plan | `research/actions/action_plan_2026-06-09_160249_latest_ratio_only.json` |
| target_allocation | `research/allocation/target_allocation_2026-06-09_150300.json` |
| intraday_rules | `research/alerts/intraday_rules.json` |
| portfolio_snapshot | `research/portfolio/portfolio_snapshot_2026-06-09_143440.json` |
| market_score | `research/market/market_score_2026-06-09_100448.json` |
| theme_leaders | `research/theme_leaders/theme_leaders_2026-06-09_140848.json` |
| valuation_report | `research/valuations/valuation_588200_SH_科创芯片ETF嘉实_2026-06-09_163552.json` |

Web 不应硬编码这些路径，应通过 `/api/latest-index` 动态解析。

---

## 6. 页面需求

### 6.1 Dashboard

首页展示系统当前状态总览：

- 当前 action state
- 市场分数与权益目标区间
- 当前权益比例与目标区间
- 当前现金/短融比例与目标区间
- bucket actual / target / gap
- ResearchFirst gate 状态
- intraday rules 状态
- project_check 状态
- sensitive scan 摘要
- latest_index generated_at
- 当前有效文件清单

Dashboard 需要突出三种颜色状态：

- OK：通过
- WARN：非阻断提醒
- FAIL：阻断

### 6.2 Action Plan 页面

展示当前 action plan：

- one-line conclusion
- action_state
- recommendation_strength
- actions 列表
- no_action_list
- research_first_list
- triggered_hard_constraints
- risks
- decision_log_entry

Action item 展示字段：

- priority
- action_type
- subject.name
- subject.type
- bucket_role
- current_position
- target_position
- suggested_change
- needs_manual_confirmation
- evidence
- trigger_conditions
- invalidation_conditions
- risks
- review_points

禁止展示任何金额、股数、账号、订单字段。

### 6.3 Target Allocation 页面

展示：

- 权益目标区间
- 现金/短融目标区间
- bucket target / actual / gap
- transition_targets
- constraints
- target allocation 依赖文件

推荐可视化：

- bucket target vs actual 条形图
- gap 表格
- equity/cash summary card

### 6.4 ResearchFirst Gate 页面

展示：

- 当前 gate 结果
- 可执行 action 是否全部通过 gate
- 现金/短融 gate 明细
- `liquidity_gate_registry.json`
- profile / valuation / liquidity evidence path
- ResearchFirst blocking reasons

状态必须来自后端检查，不由前端自行推断。

### 6.5 Portfolio Ratio Snapshot 页面

展示 ratio-only 组合快照：

- total equity ratio
- cash_short ratio
- bucket ratio
- 单标的名称/桶/权重，如果已脱敏且 ratio-only
- 数据质量 warning

禁止展示：

- cost price
- current price
- market value
- share count
- account
- QMT raw timetag

### 6.6 Intraday Rules 页面

展示：

- global_gate
- staleness
- allocation_map
- bucket actual / target / gap
- subjects
- buy/add 是否禁用
- degraded/stale 提醒

如果 `intraday_rules` 为 degraded/stale：

- 页面可显示风险提醒。
- 不得把 buy/add 展示为可执行。

### 6.7 Decision Log 页面

展示：

- 最新若干条 decision log 摘要
- action plan 对应的 `decision_log_entry`
- 可按日期筛选

Phase 1 可只做 Markdown 文本只读展示；Phase 2 再结构化为 JSONL 或数据库表。

### 6.8 System Checks 页面

展示后端运行检查结果：

- ratio-only check
- ResearchFirst gate
- allocation consistency
- project_check --current-only
- sensitive scan summary
- review/developer package integrity summary

---

## 7. 后端 API 需求

### 7.1 基础 API

```text
GET /api/health
GET /api/latest-index
GET /api/modules/current
```

### 7.2 当前研究产物 API

```text
GET /api/action-plan/current
GET /api/target-allocation/current
GET /api/intraday-rules/current
GET /api/portfolio/current
GET /api/market-score/current
GET /api/theme-leaders/current
GET /api/decision-log/current
```

### 7.3 Gate / Check API

```text
GET /api/research-first/current
GET /api/system-check/current
GET /api/sensitive-scan/current
GET /api/allocation-consistency/current
```

### 7.4 Registry API

```text
GET /api/registries/etfs/current
GET /api/registries/stocks/current
GET /api/registries/buckets/current
GET /api/registries/liquidity-gates/current
GET /api/registries/market-position-mapping/current
```

### 7.5 API 通用响应格式

```json
{
  "ok": true,
  "data": {},
  "warnings": [],
  "errors": [],
  "source": {
    "path": "research/...",
    "generated_at": "...",
    "basis_trade_date": "..."
  }
}
```

失败响应：

```json
{
  "ok": false,
  "data": null,
  "warnings": [],
  "errors": [
    {
      "code": "RATIO_ONLY_VIOLATION",
      "message": "Forbidden field detected",
      "path": "..."
    }
  ]
}
```

---

## 8. API 安全要求

所有 API 响应必须通过统一 sanitizer：

```text
ratio_only_sanitizer(response)
```

如果发现 forbidden field：

- 默认返回 HTTP 500 或 422。
- 写入后端日志。
- 前端显示“隐私边界阻断”，不显示原始数据。

禁止前端自己过滤敏感字段；过滤必须在后端完成。

---

## 9. 数据库演进需求

### Phase 1：无数据库，直接读取 JSON

- 后端通过 `latest_index.modules` 解析当前文件。
- 每次请求读取当前 JSON。
- 可使用内存缓存，但不得改变源文件。

### Phase 2：SQLite/DuckDB 只读缓存层

新增 ingest 脚本：

```text
scripts/ingest_current_state_to_db.py
```

流程：

```text
latest_index.modules -> current JSON -> sanitizer -> SQLite/DuckDB
```

数据库放在：

```text
temp/db/
```

不得进 Git 或 package。

### Phase 3：数据库作为当前状态层

- 数据库成为 current state。
- JSON/MD 变成审计导出。
- 仍需保留 `latest_index` 或等价索引。
- 仍需 ratio-only 和 ResearchFirst gate。

### Phase 4：本地 execution runtime

仅未来可选。

- 仍然默认关闭。
- 只放在 `runtime/execution/` 或 `temp/runtime/`。
- 不进入 Git / review package / developer package。
- 必须有 kill switch、paper trading、订单去重、成交核对。
- 与 Web Research 层隔离。

---

## 10. 验收标准

Web MVP 完成后，必须满足：

```text
python scripts/check_ratio_only.py --path <latest_index.modules.action_plan.path>
python scripts/check_research_first_gate.py --path <latest_index.modules.action_plan.path>
python scripts/check_cross_file_allocation_consistency.py
python scripts/project_check.py --current-only
pytest
```

要求：

- ratio-only：OK
- ResearchFirst：OK
- allocation consistency：OK
- project_check：0 FAIL
- Web API tests：通过
- Web 前端不展示 forbidden fields
- no automatic trading

---

## 11. 当前开发包前置修复提醒

本次开发种子包可以用于需求/架构整理，但交给 Codex 开发前建议先修复：

1. `research/latest_index.json` 当前 action plan 指向 `research/actions/action_plan_2026-06-09_160249_latest_ratio_only.json`，但 `DEV_PACKAGE_MANIFEST.md` 仍强调 `142000` action plan。建议 manifest 改为“当前以 latest_index.modules 为准”，不要硬编码旧 action plan。
2. `research/config/liquidity_gate_registry.json` 中 `511360.valuation_source` 指向包内不存在的 `valuation_511360_SH_短融ETF海富通_2026-06-05_103909.json`，而包内实际存在的是 `2026-06-09_153822` 和 `2026-06-09_163552` 版本。需要更新 registry 或补入旧 valuation 文件。
3. 当前包缺少 `.env.example`，导致 `project_check.py --current-only` 在本环境中报 `.env.example is missing`。建议 developer package 包含 `.env.example`，且 token 留空。

这些是开发包卫生问题，不影响本文档整理，但会影响 Codex 后续验收。
