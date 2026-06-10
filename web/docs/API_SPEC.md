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

Exception: `GET /api/environment/status` returns its environment status object directly to match the Phase 10A workbench contract. It still has a dedicated read-only safety scan and must not expose sensitive fields.

Endpoints:

- `GET /api/health`
- `GET /api/environment/status`
- `GET /api/user/preferences`
- `GET /api/user/preferences/{user_id}`
- `GET /api/dashboard/summary`
- `GET /api/dashboard/user_metrics/{user_id}`
- `GET /api/dashboard/current`
- `GET /api/current`
- `GET /api/latest-index`
- `GET /api/modules/current`
- `GET /api/subjects/status`
- `GET /api/subjects/status/{code}`
- `GET /api/subjects/freshness`
- `GET /api/subjects/gap`
- `GET /api/themes/status`
- `GET /api/themes/status/{theme_name}`
- `GET /api/buckets/status`
- `GET /api/buckets/status/{bucket}`
- `GET /api/buckets/drilldown`
- `GET /api/subjects/drilldown`
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
- `GET /api/history/gap-summary`
- `GET /api/history/gap-summary/{bucket}`
- `GET /api/research-first/current`
- `GET /api/portfolio/current`
- `GET /api/intraday-rules/current`
- `GET /api/system-check/current`
- `GET /api/decision-log/current`
- `GET /api/decision-timeline`
- `GET /api/decision-timeline/{event_id}`
- `GET /api/historical-metrics`
- `GET /api/historical-metrics/{entity_id}`
- `GET /api/allocation-consistency/current`
- `GET /api/export/review_package`

All responses pass `RatioOnlyService` before returning. A sanitizer failure returns HTTP 500.

OpenAPI docs are exposed by FastAPI at `GET /docs` while the local server is running.

## Workbench Environment Center

Phase 10A adds a read-only workbench environment endpoint:

- `GET /api/environment/status`

The endpoint returns sanitized Git, worktree, runtime path, Web server, safety-boundary, and latest known check-status metadata for the local Web workbench. It does not read `latest_index.files`, write research artifacts, mutate `research/current`, generate target allocations, generate action plans, or connect to trading/QMT write interfaces.

All paths in the response are repo-relative strings such as `temp/web_db/myinvest.sqlite` or safe redacted labels. The response must not expose local absolute paths, `.env` content, tokens, secrets, passwords, API keys, account context, trade records, or execution output.

The environment endpoint uses a dedicated environment safety scan because it includes the negative safety declaration `safety.no_order_generation=true`. That key is allowed only as a boolean safety-boundary statement and must not contain or expose order records.

The same data backs `GET /settings` and `GET /environment`.

## Workbench User Preferences Center

Phase 10B adds read-only workbench preference endpoints:

- `GET /api/user/preferences`
- `GET /api/user/preferences/{user_id}`

The default endpoint returns the local workbench display profile, dashboard refresh interval, table options, safety flags, and current-module source metadata. Supported named ids such as `default` resolve to the same display-only profile. Unknown ids return a safe 404.

The service reads only the SQLite current read model through `UserPreferencesRepository` and `DatabaseService`. It does not read `latest_index.files`, write research artifacts, mutate current modules, generate target allocations, generate action plans, or connect to trading/QMT write interfaces.

Returned fields are limited to display settings, booleans, counts, timestamps, safe local Web links, and repo-relative source paths. The response passes the standard `RatioOnlyService` wrapper and must not expose local absolute paths, credentials, runtime files, SQLite file contents, or execution output.

The same data backs `GET /preferences`.

## Workbench Analytics Dashboard

Phase 10C extends the existing read-only dashboard with workbench analytics:

- `GET /api/dashboard/summary`
- `GET /api/dashboard/user_metrics/{user_id}`

`/api/dashboard/summary` returns current-only workbench metrics, gate statuses, time-window metadata, and a read-only history snapshot summary when the guarded runtime history database exists. The `time_window` query parameter accepts `current`, `7d`, or `30d`; all modes remain current-only because no persistent user event store is introduced in this phase.

`/api/dashboard/user_metrics/{user_id}` returns the same ratio-only metrics combined with the selected display preferences for supported local ids such as `default`. Unknown ids return a safe 404.

The analytics repository uses `DatabaseService` for SQLite current-state reads and `HistorySnapshotRepository` for the guarded runtime history snapshot summary. It does not read `latest_index.files`, write research artifacts, generate target allocations, generate action plans, or connect to trading/QMT write interfaces.

The existing `GET /api/dashboard/current` payload now includes `analytics_summary`, and `GET /dashboard` displays the workbench analytics section with a time-window selector.

## Research Dashboard

Phase 7D adds a read-only dashboard endpoint:

- `GET /api/dashboard/current`

The service aggregates existing SQLite current-state services into a research landing-page summary. It reads current state loaded from `latest_index.modules`; it does not read `latest_index.files`, write research artifacts, generate target allocations, generate action plans, or expose execution adapters.

The response contains `system_status`, `market_position`, `action_plan_summary`, `allocation_summary`, `subject_status_summary`, `subject_gap_summary`, and `quick_links`. Fields are limited to status labels, counts, timestamps, percentage ratios, percentage-point gaps, and local Web links. The response passes `RatioOnlyService` before returning.

The same dashboard data backs `GET /` and `GET /dashboard`.

## Subject Status

Phase 7A adds a read-only subject research status center:

- `GET /api/subjects/status`
- `GET /api/subjects/status/{code}`

The service reads SQLite current-state tables loaded from `latest_index.modules` and returns one row per current subject. It does not read `latest_index.files`, does not generate research artifacts, and does not create action-plan or target-allocation output.

Returned fields include `code`, `name`, `subject_type`, `bucket`, `profile_status`, `valuation_status`, `liquidity_status`, `research_first_status`, `gate_conclusion`, `blocking_reason`, repo-relative `source_paths`, `generated_at`, and `basis_trade_date`.

Gate conclusions are limited to neutral review states: `eligible_for_review`, `research_first`, `watch`, `hold`, `no_action`, `unknown`, and `blocked`. The endpoint must not return buy/add/reduce/sell conclusions. Missing profile, valuation, liquidity, or theme binding keeps the subject in `research_first` or `blocked` status. Short-duration cash-equivalent instruments such as 511360 are displayed as cash-equivalent / cash-short status after profile, valuation, and liquidity gates pass.

## Subject Gap And Freshness

Phase 7B adds a read-only subject gap and data freshness center:

- `GET /api/subjects/freshness`
- `GET /api/subjects/gap`

Both endpoints read SQLite current-state tables loaded from `latest_index.modules`. They do not read `latest_index.files`, do not write research artifacts, and do not generate target allocation or action plans.

`/api/subjects/freshness` returns each subject's `last_update_timestamp`, `basis_trade_date`, `staleness_flag`, `staleness_reason`, bucket, and repo-relative `source_paths`.

`/api/subjects/gap` returns each subject's bucket-level `actual_pct`, `target_pct`, `gap_pct`, `gap_status`, subject `position_pct`, freshness fields, and current market-position summary. The bucket actual/target/gap values must match the current target-allocation bucket rows.

Gap status is presentation-only:

- `green`: bucket gap is within a tight threshold.
- `yellow`: bucket gap needs review.
- `red`: bucket gap is large enough to highlight.
- `unknown`: no bucket gap row is available.

The endpoints are ratio-only and return percentages, timestamps, flags, status labels, and relative source metadata only.

Phase 7C keeps the same API contract and adds only frontend visualization on `/subjects/gap`. The page renders a color-coded bucket gap chart from `/api/subjects/gap`; hover details use the same ratio-only fields already returned by the API.

## Theme Research Center

Phase 7E adds a read-only theme research status center:

- `GET /api/themes/status`
- `GET /api/themes/status/{theme_name}`

The service reads current SQLite artifact payloads loaded from `latest_index.modules` for `theme_registry`, `theme_leaders`, `etf_registry`, and `stock_registry`. It does not read `latest_index.files`, write research artifacts, update `current_modules`, generate target allocations, or generate action plans.

Returned fields include `summary`, `themes`, associated ETF/stock gate summaries, leaders, conflicts, data-quality status, and safety flags. Theme states are neutral research states: `confirmed`, `watch`, `research_first`, `stale`, `conflict`, or `unknown`. They must not become buy/add/reduce/sell actions.

The page `GET /themes` uses the same API and supports refresh, search, status/rating/stage filters, sorting, pagination, and expandable details.

## Bucket Explorer

Phase 7F adds a read-only bucket allocation drilldown:

- `GET /api/buckets/status`
- `GET /api/buckets/status/{bucket}`

The service reads current SQLite data loaded from `latest_index.modules` through existing current-state, subject-status, and subject-gap services. It does not read `latest_index.files`, write research artifacts, update current module pointers, generate target allocations, or generate action plans.

Returned fields include `summary`, `buckets`, per-bucket actual/target/gap percentages, neutral `gap_status`, bucket risk notes, subject counts, and per-subject gate status. Subject rows include code, name, subject type, bucket, position percentage, profile/valuation/liquidity status, ResearchFirst status, neutral gate conclusion, blocking reason, staleness flag, and repo-relative source metadata.

Gap status is presentation-only: `near_target`, `overweight`, `underweight`, `zero_target_nonzero_actual`, or `unknown`. A legacy watch bucket with nonzero actual and zero target is shown as `zero_target_nonzero_actual`, not as an action.

The page `GET /buckets` uses the same API and supports refresh, search, bucket/gate filters, sorting, pagination, and expandable details.

## Allocation Drilldown

Phase 7H adds read-only allocation drilldown endpoints:

- `GET /api/buckets/drilldown`
- `GET /api/buckets/drilldown?bucket=<bucket>&detail=full`
- `GET /api/subjects/drilldown`
- `GET /api/subjects/drilldown?subject=<code>&detail=full`

The service reads only current SQLite state produced from `research/latest_index.json` `modules`. It joins current target-allocation bucket rows, portfolio-position rows, subject gap/freshness rows, neutral ResearchFirst status, market position, and theme association summaries.

Bucket rows return `actual_pct`, `target_pct`, `gap_pct`, `gap_status`, subject counts, neutral ResearchFirst counts, timestamps, and optional subject details. Subject rows return subject code/name/type, bucket, position percentage, bucket actual/target/gap percentages, neutral gate status, profile/valuation/liquidity status, theme count, timestamps, and relative Web review links.

The endpoints do not read `latest_index.files`, write research artifacts, update `current_modules`, generate target allocations, generate action plans, or connect to execution adapters. Responses are ratio-only and pass `RatioOnlyService`.

The pages `GET /buckets/drilldown` and `GET /subjects/drilldown` use the same APIs and support refresh, search, filters, sorting, pagination, charts/tooltips where applicable, and expandable details.

## Decision Timeline

Phase 7I adds read-only review timeline endpoints:

- `GET /api/decision-timeline`
- `GET /api/decision-timeline/{event_id}`

The service reads current SQLite state produced from `research/latest_index.json` `modules` and existing read-only history snapshot summaries. It combines current action plan metadata, current target allocation metadata, recent decision log entries, and history snapshot entries into neutral review events.

Returned fields include `event_id`, `event_type`, `timestamp`, `title`, `summary`, `status`, `basis_trade_date`, `details`, and relative `review_links`. Details are limited to ratio-only counts, statuses, percentages, percentage-point gaps, timestamps, and neutral review metadata.

The endpoints do not read `latest_index.files`, write research artifacts, update `current_modules`, generate target allocations, generate action plans, or connect to execution adapters. Responses are ratio-only and pass `RatioOnlyService`.

The page `GET /decision-timeline` uses the same API and supports refresh, search, event/status filters, sorting, pagination, timeline visualization, tooltips, and expandable details.

## Historical Metrics

Phase 8 adds read-only historical metrics endpoints:

- `GET /api/historical-metrics`
- `GET /api/historical-metrics/{entity_id}`

The service reads current SQLite state and existing read-only history summaries derived from `latest_index.modules`. It aggregates bucket gap trends, subject current status, theme status, decision timeline event types, and current market-score context into ratio-only metrics for review.

Returned fields include `summary`, `series`, `aggregations`, `entities`, `source_modules`, and `safety`. Entity rows use neutral fields such as `entity_id`, `entity_type`, `label`, `status`, ratio percentages, percentage-point gaps, timestamps, counts, trend indicators, and relative review links.

The endpoints do not read `latest_index.files`, write research artifacts, update `current_modules`, generate target allocations, generate action plans, or connect to execution adapters. Responses are ratio-only and pass `RatioOnlyService`.

The page `GET /historical-metrics` uses the same API and supports refresh, search, entity/status filters, sorting, pagination, bucket gap visualization, tooltips, and expandable details.

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

## History Gap Dashboard

Phase 7G adds a read-only history gap dashboard:

- `GET /api/history/gap-summary`
- `GET /api/history/gap-summary/{bucket}`

The API aggregates in-memory current target allocation, controlled shadow target allocation, candidate audit target allocation, and history snapshot entry summaries. It does not write temporary exports, write the history database, update `latest_index`, update `current_modules`, generate target allocations, or generate action plans.

Returned fields include summary counts, bucket actual/target/gap percentages, neutral gap status, alert status, timeline points, history entry summaries, and safety flags. Gap and alert states are display-only review states.

The page `GET /history/gap-dashboard` uses the same API and supports refresh, search, gap-status filtering, sorting, pagination, expandable details, and bucket gap evolution visualization.

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
