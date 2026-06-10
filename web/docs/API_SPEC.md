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
- `GET /api/subjects/status`
- `GET /api/subjects/status/{code}`
- `GET /api/market-position/mapping`
- `GET /api/market-position/current`
- `GET /api/market-position/score/{score}`
- `GET /api/action-plan/current`
- `GET /api/target-allocation/current`
- `GET /api/target-allocation/shadow`
- `GET /api/target-allocation/shadow/compare`
- `GET /api/target-allocation/shadow/export`
- `GET /api/target-allocation/candidate-audit`
- `GET /api/history/export`
- `GET /api/research-first/current`
- `GET /api/portfolio/current`
- `GET /api/intraday-rules/current`
- `GET /api/system-check/current`
- `GET /api/decision-log/current`
- `GET /api/allocation-consistency/current`
- `GET /api/export/review_package`

All responses pass `RatioOnlyService` before returning. A sanitizer failure returns HTTP 500.

OpenAPI docs are exposed by FastAPI at `GET /docs` while the local server is running.

## Subject Status

Phase 7A adds a read-only subject research status center:

- `GET /api/subjects/status`
- `GET /api/subjects/status/{code}`

The service reads SQLite current-state tables loaded from `latest_index.modules` and returns one row per current subject. It does not read `latest_index.files`, does not generate research artifacts, and does not create action-plan or target-allocation output.

Returned fields include `code`, `name`, `subject_type`, `bucket`, `profile_status`, `valuation_status`, `liquidity_status`, `research_first_status`, `gate_conclusion`, `blocking_reason`, repo-relative `source_paths`, `generated_at`, and `basis_trade_date`.

Gate conclusions are limited to neutral review states: `eligible_for_review`, `research_first`, `watch`, `hold`, `no_action`, `unknown`, and `blocked`. The endpoint must not return buy/add/reduce/sell conclusions. Missing profile, valuation, liquidity, or theme binding keeps the subject in `research_first` or `blocked` status. Short-duration cash-equivalent instruments such as 511360 are displayed as cash-equivalent / cash-short status after profile, valuation, and liquidity gates pass.

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

## Target Allocation Controlled Export

Phase 5C-3 adds a controlled export for the shadow target allocation:

- `GET /api/target-allocation/shadow/export`
- `GET /api/target-allocation/shadow/export?format=json`
- `GET /api/target-allocation/shadow/export?format=zip`

The API is read-only and generates the export in memory. It does not write `research/allocation`, does not update `latest_index`, does not update `current_modules`, and does not generate action plans. The ZIP contains only:

- `manifest.json`
- `shadow_target_allocation.json`
- `compare_result.json`
- `provenance.json`
- `system_checks.json`

The CLI companion writes only to `temp/web_exports/`, which is ignored by Git.

## Target Allocation Candidate Audit

Phase 5G adds a candidate audit bundle for target-allocation promotion review:

- `GET /api/target-allocation/candidate-audit`
- `GET /api/target-allocation/candidate-audit?format=json`
- `GET /api/target-allocation/candidate-audit?format=zip`

The API is read-only and generates the audit bundle in memory. It does not write `research/allocation`, does not update `latest_index`, does not update `current_modules`, does not generate action plans, and does not make candidate output official. Official promotion remains blocked.

The ZIP contains only:

- `manifest.json`
- `candidate_target_allocation.json`
- `compare_result.json`
- `replay_summary.json`
- `promotion_mode.json`
- `safety_checks.json`
- `provenance.json`

The CLI companion writes only to `temp/candidate_exports/`, which is ignored by Git. The exported filename must include `candidate_audit`.

## History Snapshot Export

Phase 6 adds a read-only history snapshot export:

- `GET /api/history/export`
- `GET /api/history/export?format=json`
- `GET /api/history/export?format=zip`

The API is read-only and generates the snapshot in memory. It consolidates temporary shadow, candidate, and candidate-audit export summaries with a live current safety summary. It does not write `research/latest_index.json`, does not update `current_modules`, does not write `research/allocation` or `research/actions`, does not generate official target allocation, and does not generate action plans.

The ZIP contains only:

- `manifest.json`
- `history_snapshot.json`
- `history_entries.json`
- `live_current_summary.json`
- `safety_checks.json`

The CLI companion writes only to ignored temporary export folders and keeps the local history database under ignored runtime storage. Exported JSON and ZIP payloads must not contain runtime paths.

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
