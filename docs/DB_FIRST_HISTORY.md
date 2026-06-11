# DB-first history database

This document is the operational guide for the MyInvest DB-first history layer.
It records how to migrate, ingest, query, validate, and expose historical facts
without changing the current JSON/Markdown research workflow.

## 中文摘要

历史事实库是从 `research/` 下 JSON 研究产物派生出来的本地 SQLite
查询层，不替代现有 Markdown/JSON 研究流程。历史库只放在
`temp/history_db/`，可以重建；现有 Web current-only cache 仍然是
`temp/web_db/myinvest.sqlite`。证券价格不是隐私，金额、数量、账户、
委托、成交、凭证和本机绝对路径才是隐私边界。所有历史 Web API
保持只读，不新增自动交易或 QMT 写入能力。

## Status

- The current research source of truth remains `research/latest_index.json` and
  timestamped JSON/Markdown artifacts under `research/`.
- The history database is a derived fact store. It is safe to rebuild from
  research JSON artifacts.
- The Web current cache remains `temp/web_db/myinvest.sqlite`.
- The history database must live under `temp/history_db/`.
- SQLite database files are runtime artifacts and must not be committed.

## Files

Core DB code:

```text
migrations/
myinvest/db/
scripts/db_migrate.py
scripts/db_ingest_research_artifacts.py
scripts/db_export_report.py
scripts/db_build_latest_index_shadow.py
scripts/db_query_*_history.py
```

Read-only Web integration:

```text
web/backend/app/routers/history.py
web/backend/app/services/valuation_history.py
web/backend/app/services/history_workbench.py
web/backend/app/templates/*history*.html
web/backend/app/templates/history_quality.html
```

## Build or rebuild a test history DB

Use the test DB for development and validation:

```bash
python scripts/db_migrate.py --db temp/history_db/test_myinvest_history.sqlite3 --reset
python scripts/db_ingest_research_artifacts.py --db temp/history_db/test_myinvest_history.sqlite3 --all
python scripts/project_check.py --current-only --db temp/history_db/test_myinvest_history.sqlite3 --db-strict
```

Expected high-level result:

- migration status is `ok`
- pending migrations are empty
- all research JSON artifacts are covered
- normalized coverage exists for valuation, portfolio, target allocation, and action plan artifacts
- privacy scan rows exist for all imported artifacts
- no DB quality `FAIL`

## Production-local history DB

Use this path for the local Web history pages:

```bash
python scripts/db_migrate.py --db temp/history_db/myinvest_history.sqlite3 --reset
python scripts/db_ingest_research_artifacts.py --db temp/history_db/myinvest_history.sqlite3 --all
```

Then start the existing Web backend:

```bash
python scripts/run_web.py --host 127.0.0.1 --port 8011
```

Useful pages:

```text
/securities/{code}/valuation
/market/history
/positions/history
/actions/history
/history/quality
/history/coverage
/securities/{code}/history
```

Useful APIs:

```text
/api/securities/{code}/valuation-history
/api/market/history
/api/positions/history
/api/actions/history
/api/history/quality
/api/history/coverage
/api/securities/{code}/history
```

All history APIs are read-only GET endpoints. Do not add POST, PUT, PATCH, or
DELETE endpoints for the history DB.

## Export an audit snapshot

The history DB can export a derived audit snapshot to `temp/history_db/exports/`.
This is for review and handoff only; it does not replace source research files.

```bash
python scripts/db_export_report.py --db temp/history_db/test_myinvest_history.sqlite3 --format both --code 688333.SH --limit 20
```

The export writes Markdown and JSON, includes only ratio-only/history facts, and
keeps output under ignored `temp/`.

Optional filters and ZIP packaging:

```bash
python scripts/db_export_report.py --db temp/history_db/test_myinvest_history.sqlite3 --format both --zip --since 2026-06-01 --until 2026-06-30 --bucket defense
```

## Optional generator dual-write

The existing generators keep their default behavior unless `--db` is passed.
When `--db` is provided, the generated JSON artifact is ingested into the
history DB using the same artifact ingestion path and transaction boundary.

```bash
python scripts/generate_valuation_reports.py --db temp/history_db/myinvest_history.sqlite3
python scripts/qmt_portfolio_snapshot.py --db temp/history_db/myinvest_history.sqlite3
python scripts/generate_target_allocation.py --db temp/history_db/myinvest_history.sqlite3
python scripts/generate_action_plan.py --db temp/history_db/myinvest_history.sqlite3
```

The dual-write path does not create trading capability. It only writes research
facts and normalized ratio-only rows into SQLite.

For QMT portfolio snapshot validation, use read-only mode and avoid extra rule
or log side effects during a test run:

```bash
python scripts/qmt_portfolio_snapshot.py --probe
python scripts/qmt_portfolio_snapshot.py --no-sync-rules --no-log --db temp/history_db/test_myinvest_history.sqlite3
```

Run the second command only when the QMT client is open and the read-only query
connection is available.

## latest_index shadow

The DB can build a shadow latest-index view for comparison only. This command
does not replace `research/latest_index.json`.

```bash
python scripts/db_build_latest_index_shadow.py --db temp/history_db/test_myinvest_history.sqlite3 --out temp/history_db/latest_index_shadow.json --strict
```

## Query examples

```bash
python scripts/db_query_valuation_history.py --db temp/history_db/test_myinvest_history.sqlite3 --code 688333.SH
python scripts/db_query_position_history.py --db temp/history_db/test_myinvest_history.sqlite3 --bucket defense
python scripts/db_query_action_history.py --db temp/history_db/test_myinvest_history.sqlite3 --action-type Reduce --limit 20
python scripts/db_query_market_history.py --db temp/history_db/test_myinvest_history.sqlite3 --limit 10
python scripts/db_query_theme_history.py --db temp/history_db/test_myinvest_history.sqlite3 --theme AI --limit 10
python scripts/db_query_security_research_history.py --db temp/history_db/test_myinvest_history.sqlite3 --code 588200.SH
```

## CI

GitHub Actions runs the DB-first and Web gates on push and pull request:

- build the history test DB
- import all research JSON artifacts
- run `project_check.py --current-only`
- run `project_check.py --current-only --db ... --db-strict`
- run DB tests
- run Web backend tests
- run `scripts/web_check.py --mode smoke`

## Privacy and ratio-only boundary

Allowed in DB rows, Web API responses, and reports:

- security code
- security name
- price or valuation metric
- ratio
- percentage point
- target range
- action type
- gate status
- generated time and basis date
- relative artifact path
- blocking reason

Not allowed:

- total asset
- cash amount
- market value
- trade amount
- profit amount
- cost amount
- share count
- quantity
- available quantity
- full account identifier
- order record
- fill record
- deal record
- local absolute path
- credential or token

Important clarification: a security price is not private by itself. Privacy is
amount-related or account/trade-record related. Keep price available where it is
needed for valuation and research history, but do not combine it with private
position quantity or account amount fields.

## Reset safety

`scripts/db_migrate.py --reset` is guarded. Without explicit dangerous override
support in code, reset is only allowed under `temp/`.

Never reset, delete, or overwrite a database outside this repository's `temp/`
directory during normal DB-first development.

## Quality gates

Run these after DB or Web history changes:

```bash
python scripts/db_migrate.py --db temp/history_db/test_myinvest_history.sqlite3 --check
python scripts/project_check.py --current-only
python scripts/project_check.py --current-only --db temp/history_db/test_myinvest_history.sqlite3 --db-strict
python -m pytest tests -q
python -m pytest web/backend/tests -q
python scripts/web_check.py
```

When an action plan is touched, also run:

```bash
python scripts/check_ratio_only.py --path research/actions/action_plan_2026-06-11_141647_latest_ratio_only.json
python scripts/check_research_first_gate.py --path research/actions/action_plan_2026-06-11_141647_latest_ratio_only.json
python scripts/check_cross_file_allocation_consistency.py
```

Use the current action plan path from `research/latest_index.json`; do not
hardcode a timestamp in reusable automation.

## Design constraints

- Do not add automatic trading.
- Do not add QMT write APIs.
- Do not place orders, cancel orders, or modify orders.
- Do not move the history pages into a parallel `web/app.py`.
- Do not make the history DB the current-only Web cache.
- Do not treat `latest_index.files` as current effective state.
- Do not generate buy/add/reduce/sell advice without ResearchFirst gates.
