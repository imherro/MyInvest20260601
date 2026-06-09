# Web API Spec

All endpoints are read-only and return:

```json
{
  "ok": true,
  "data": {},
  "warnings": [],
  "errors": [],
  "source": {}
}
```

Endpoints:

- `GET /api/health`
- `GET /api/current`
- `GET /api/latest-index`
- `GET /api/modules/current`
- `GET /api/action-plan/current`
- `GET /api/target-allocation/current`
- `GET /api/research-first/current`
- `GET /api/portfolio/current`
- `GET /api/intraday-rules/current`
- `GET /api/system-check/current`
- `GET /api/decision-log/current`
- `GET /api/allocation-consistency/current`
- `GET /api/export/review_package`

All responses pass `RatioOnlyService` before returning. A sanitizer failure returns HTTP 500.

OpenAPI docs are exposed by FastAPI at `GET /docs` while the local server is running.

## Review Package Export

`GET /api/export/review_package?format=json` returns the current-only review snapshot as JSON.

`GET /api/export/review_package` returns a ZIP file with:

- `manifest.json`
- `current_snapshot.json`
- `action_plan.json`
- `target_allocation.json`
- `intraday_rules.json`
- `portfolio_snapshot.json`
- `market_position_mapping.json`
- `bucket_registry.json`
- `liquidity_gate_registry.json`
- `decision_log.json`
- `system_checks.json`

Both formats are read-only and ratio-only sanitized.
