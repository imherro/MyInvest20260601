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
- `GET /api/market-position/mapping`
- `GET /api/market-position/current`
- `GET /api/market-position/score/{score}`
- `GET /api/action-plan/current`
- `GET /api/target-allocation/current`
- `GET /api/target-allocation/shadow`
- `GET /api/target-allocation/shadow/compare`
- `GET /api/research-first/current`
- `GET /api/portfolio/current`
- `GET /api/intraday-rules/current`
- `GET /api/system-check/current`
- `GET /api/decision-log/current`
- `GET /api/allocation-consistency/current`
- `GET /api/export/review_package`

All responses pass `RatioOnlyService` before returning. A sanitizer failure returns HTTP 500.

OpenAPI docs are exposed by FastAPI at `GET /docs` while the local server is running.

## Market Position

Phase 5C-1 adds read-only market-position endpoints backed by SQLite
`market_position_mappings`.

- `GET /api/market-position/mapping` returns active score ranges.
- `GET /api/market-position/current` reads the current market score from SQLite and maps it to the active range.
- `GET /api/market-position/score/{score}` maps an explicit score to the active range.

These endpoints do not generate target allocations or action plans. They return only score ranges, labels, percentage ranges, and `source = "db.market_position_mappings"`. Invalid scores return a non-500 error without local paths.

## Target Allocation Shadow

Phase 5C-2 adds read-only target-allocation shadow endpoints:

- `GET /api/target-allocation/shadow`
- `GET /api/target-allocation/shadow/compare`

The shadow service reads current SQLite state, calls `MarketPositionService`, computes ratio-only bucket targets, and compares core fields with the current `latest_index.modules.target_allocation` JSON. It does not write `research/allocation`, does not update `current_modules`, and does not generate action plans.

`/api/target-allocation/shadow/compare` returns `matched`, `diffs`, `compared_fields`, `unsupported_fields`, `source_shadow`, and `source_reference`. Core-field mismatches are test failures; unsupported fields must be explicit and are not used to hide core diffs.

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
