# MyInvest Web 版架构设计手册（B/S Read-only MVP）

> 基于开发种子包：`MyInvest_dev_web_seed_2026-06-09_165947.zip`
> 目标：先做只读 Web MVP，再引入 SQLite/DuckDB 缓存，最后才考虑本地 execution runtime。
> 核心原则：**ResearchFirst + ratio-only + current-only + no automatic trading**。

---

## 1. 总体架构

Phase 1 采用轻量 B/S 架构：

```text
Browser
  ↓ HTTP
FastAPI Backend
  ↓ current-only resolver
research/latest_index.json
  ↓ modules[*].path
current JSON artifacts
```

第一阶段不引入数据库，不改变现有 JSON/Markdown 产物生成逻辑。

---

## 2. 分层设计

```text
web/
  backend/
    app/
      main.py
      core/
        config.py
        paths.py
        security.py
        sanitizer.py
        errors.py
      services/
        latest_index_service.py
        artifact_loader.py
        action_plan_service.py
        target_allocation_service.py
        intraday_rules_service.py
        portfolio_service.py
        gate_service.py
        system_check_service.py
        decision_log_service.py
      api/
        routes_health.py
        routes_latest_index.py
        routes_action_plan.py
        routes_allocation.py
        routes_intraday.py
        routes_portfolio.py
        routes_gates.py
        routes_system.py
      schemas/
        common.py
        action_plan.py
        allocation.py
        gates.py
    tests/
      test_api_ratio_only.py
      test_api_current_only.py
      test_research_first_api.py

  frontend/
    package.json
    src/
      main.tsx
      App.tsx
      api/client.ts
      pages/
        Dashboard.tsx
        ActionPlan.tsx
        TargetAllocation.tsx
        ResearchFirst.tsx
        Portfolio.tsx
        IntradayRules.tsx
        DecisionLog.tsx
        SystemChecks.tsx
      components/
        StatusTag.tsx
        BucketGapTable.tsx
        RatioCard.tsx
        SourceFileBadge.tsx
        GateStatusPanel.tsx
```

如果希望更简单，也可以 Phase 1 先使用：

```text
FastAPI + Jinja2 + HTMX
```

这会少一个前端工程，适合本地单人使用。但如果未来页面会越来越多，建议使用 React + Ant Design。

---

## 3. 后端技术选型

推荐：

- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic v2
- pytest
- httpx for API tests

Phase 1 不需要 ORM。

Phase 2 数据库可选：

- SQLite：通用、简单。
- DuckDB：更适合分析型查询和表格数据。

推荐顺序：

```text
Phase 1: JSON direct read
Phase 2: SQLite/DuckDB cache
Phase 3: DB state layer
```

---

## 4. 前端技术选型

推荐：

- React
- Vite
- TypeScript
- Ant Design
- ECharts 或 Recharts

页面主题以“审计型 Dashboard”为主，不做交易终端风格。

---

## 5. 后端核心服务

### 5.1 LatestIndexService

职责：

- 读取 `research/latest_index.json`
- 返回 `modules`
- 提供 `get_current_module(module_name)`
- 提供 `get_current_path(module_name)`
- 禁止使用文件系统 mtime 判断当前文件

关键函数：

```python
class LatestIndexService:
    def load_latest_index(self) -> dict: ...
    def get_module(self, module: str) -> dict: ...
    def get_current_artifact_path(self, module: str) -> Path: ...
```

### 5.2 ArtifactLoader

职责：

- 只读取仓库相对路径
- 禁止本地绝对路径
- 读取 JSON / Markdown
- 给响应附带 source metadata
- 统一调用 sanitizer

关键函数：

```python
class ArtifactLoader:
    def read_current_json(self, module: str) -> ArtifactResponse: ...
    def read_json_by_relative_path(self, path: str) -> dict: ...
```

### 5.3 RatioOnlySanitizer

职责：

- 后端统一过滤/阻断 forbidden fields
- 所有 API 返回前必须调用
- 检测 key 和 value 两类风险

Forbidden keys：

```python
FORBIDDEN_KEY_PATTERNS = [
    "total_asset",
    "amount",
    "market_value",
    "shares",
    "quantity",
    "available_quantity",
    "trade_amount",
    "profit_amount",
    "account",
    "full_account",
    "order",
    "fill",
    "deal",
]
```

Forbidden Chinese terms：

```python
["总资产", "金额", "市值", "股数", "数量", "可用数量", "交易金额", "盈亏金额", "账号", "委托", "成交"]
```

Forbidden local path patterns：

```python
["C:/Users/", "C:\\Users\\", "/Users/", "/home/"]
```

响应策略：

- 默认 fail closed。
- 发现违规字段直接返回错误，不返回部分敏感 payload。

### 5.4 GateService

职责：

- 复用或封装 `scripts/check_research_first_gate.py`
- 检查当前 action plan
- 解析 gate 结果给前端展示
- 不由前端自行判断 gate

推荐实现方式：

```python
class GateService:
    def run_research_first_gate(self) -> GateResult:
        # subprocess 调用脚本，或重构脚本为可 import 函数
```

Phase 1 可以 subprocess；Phase 2 再重构为纯函数。

### 5.5 SystemCheckService

职责：

- 运行：
  - check_ratio_only.py
  - check_research_first_gate.py
  - check_cross_file_allocation_consistency.py
  - project_check.py --current-only
- 返回结构化结果
- 将 WARN 和 FAIL 区分展示

### 5.6 ActionPlanService

职责：

- 读取当前 action plan
- 提取 summary/actions/no_action/research_first/risks/constraints
- 只返回 ratio-only 字段
- 对 subject 进行安全检查

### 5.7 AllocationService

职责：

- 读取当前 target allocation
- 提取 bucket target / actual / gap
- 读取 intraday_rules allocation_map
- 可调用 consistency check

### 5.8 PortfolioService

职责：

- 读取当前 portfolio snapshot
- 只返回 ratio-only 字段
- 禁止返回 cost/current price/account/QMT timetag

### 5.9 DecisionLogService

职责：

- Phase 1：读取 Markdown，返回纯文本摘要
- Phase 2：解析为 entry list
- Phase 3：迁移 JSONL/数据库

---

## 6. API 路由设计

### 6.1 Health

```text
GET /api/health
```

返回：

```json
{
  "ok": true,
  "app": "MyInvest Web",
  "mode": "read-only",
  "current_only": true
}
```

### 6.2 Latest Index

```text
GET /api/latest-index
```

返回：

- generated_at
- modules
- current paths
- stale/degraded summary

### 6.3 Action Plan

```text
GET /api/action-plan/current
```

返回：

- summary
- actions
- no_action_list
- research_first_list
- hard_constraints
- risks
- decision_log_entry
- source metadata

### 6.4 Target Allocation

```text
GET /api/target-allocation/current
```

返回：

- target equity/cash
- bucket target/actual/gap
- transition targets
- constraints

### 6.5 Intraday Rules

```text
GET /api/intraday-rules/current
```

返回：

- global_gate
- staleness
- allocation_map
- subjects
- disabled triggers

### 6.6 Portfolio

```text
GET /api/portfolio/current
```

返回：

- ratio-only portfolio summary
- bucket exposure
- subject exposure only if redacted and allowed

### 6.7 ResearchFirst

```text
GET /api/research-first/current
```

返回：

- gate status
- gate messages
- cash-equivalent gate status
- source files used by gate

### 6.8 System Checks

```text
GET /api/system-check/current
```

返回：

```json
{
  "ratio_only": "ok",
  "research_first": "ok",
  "allocation_consistency": "ok",
  "project_check": {
    "fail": 0,
    "warn": 1
  }
}
```

---

## 7. Current-only Resolver

所有“current” API 必须使用统一 resolver：

```python
def resolve_current(module: str) -> Path:
    latest = load_latest_index()
    item = latest["modules"][module]
    return safe_relative_path(item["path"])
```

禁止：

- 扫目录找最新。
- 用文件 mtime。
- 读取 `latest_index.files` 作为当前状态。
- 让前端传任意路径读取文件。

如果要支持历史文件，必须另建 `/api/history/...`，并标注 `current: false`。

---

## 8. Web 数据流

```text
User opens Dashboard
  ↓
Frontend GET /api/latest-index
  ↓
Backend reads research/latest_index.json
  ↓
Frontend requests current modules
  ↓
Backend loads current JSON by latest_index.modules path
  ↓
Backend sanitizer
  ↓
Frontend renders cards/tables/charts
```

System Checks 数据流：

```text
Frontend GET /api/system-check/current
  ↓
Backend subprocess runs check scripts
  ↓
Parse stdout/stderr/exit_code
  ↓
Return structured check result
```

---

## 9. 安全设计

### 9.1 路径安全

只允许读取项目根目录下的相对路径：

```python
def safe_join(root: Path, rel: str) -> Path:
    p = (root / rel).resolve()
    if not str(p).startswith(str(root.resolve())):
        raise SecurityError
    return p
```

拒绝：

- 绝对路径
- `..`
- symlink escape
- Windows 用户目录
- home 目录

### 9.2 API 安全

- Phase 1 只在 localhost 使用。
- 默认不开放公网。
- 如需局域网访问，需增加简单登录或反向代理认证。
- 不返回 `.env` 内容。
- 不返回 package 原始 zip。
- 不返回数据库文件。
- 不返回 execution runtime。

### 9.3 前端安全

- 不允许用户输入文件路径。
- 不允许上传文件覆盖 research。
- 不允许执行 shell 命令。
- System check 只能运行后端 allowlist 命令。

---

## 10. 测试设计

### 10.1 后端测试

```text
tests/test_api_health.py
tests/test_api_latest_index.py
tests/test_api_current_only.py
tests/test_api_ratio_only.py
tests/test_api_research_first.py
tests/test_api_allocation_consistency.py
```

### 10.2 关键测试场景

1. `/api/action-plan/current` 返回当前 action plan。
2. API 不包含 forbidden fields。
3. 如果 action plan 中注入 forbidden field，API 阻断。
4. current-only resolver 只读取 `latest_index.modules`。
5. 历史 action plan 不被当作 current。
6. ResearchFirst gate 失败时 `/api/system-check/current` 返回 FAIL。
7. allocation consistency 失败时 Dashboard 显示 FAIL。
8. 本地绝对路径被 sanitizer 阻断。

---

## 11. 运行方式

后端：

```bash
cd web/backend
python -m venv .venv
pip install -r ../../requirements.txt
pip install fastapi uvicorn pydantic pytest httpx
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

前端：

```bash
cd web/frontend
npm install
npm run dev
```

浏览器：

```text
http://127.0.0.1:5173
```

Phase 1 也可以用 FastAPI 静态页面/Jinja2 简化，不强制 React。

---

## 12. 数据库 Phase 2 设计

### 12.1 数据库位置

```text
temp/db/myinvest_current.sqlite
```

或：

```text
temp/db/myinvest_current.duckdb
```

不得进入 Git、review package、developer package。

### 12.2 ingest 脚本

```text
scripts/ingest_current_state_to_db.py
```

输入：

```text
research/latest_index.json
latest_index.modules[*].path
```

流程：

```text
load current artifacts
→ ratio-only sanitizer
→ schema normalize
→ write DB
→ record source hash/generated_at
```

### 12.3 核心表

```text
latest_module
market_score
market_position_mapping
target_allocation
bucket_allocation
action_plan
action_item
research_first_item
portfolio_snapshot
intraday_rule_status
liquidity_gate
decision_log_entry
system_check_result
```

### 12.4 数据库与 JSON 关系

Phase 2：

```text
JSON is source of truth
DB is read-only cache
```

Phase 3：

```text
DB is state layer
JSON/MD are audit exports
```

---

## 13. Execution Runtime Phase 4

只有在 Phase 1-3 稳定后才考虑。

必须隔离：

```text
runtime/execution/
```

硬要求：

- 默认关闭。
- 不进 Git。
- 不进 review/developer package。
- 不进入 research JSON。
- 必须人工确认。
- 必须有 kill switch。
- 必须 paper trading 先行。
- 必须订单去重。
- 必须成交核对。
- 必须独立敏感日志。

---

## 14. 当前开发包前置修复

本设计文档可继续使用，但当前 seed package 在交给 Codex 开发前建议修复：

1. `latest_index.modules.action_plan.path` 当前为 `research/actions/action_plan_2026-06-09_160249_latest_ratio_only.json`，但 `DEV_PACKAGE_MANIFEST.md` 的 Required Evidence 仍写 `142000`。开发时必须以 latest_index 为准。
2. `liquidity_gate_registry.json` 的 `valuation_source` 指向包内不存在的旧文件；需要更新到包内存在的 valuation 文件，或补入缺失文件。
3. `.env.example` 缺失，导致 `project_check.py --current-only` 报 FAIL。developer package 应包含空 token 的 `.env.example`。

建议修复后重新生成 dev seed package，再进入 Codex Web MVP 开发。
