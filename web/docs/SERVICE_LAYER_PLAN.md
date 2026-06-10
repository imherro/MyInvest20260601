# Service Layer Plan

Phase 5A documented service boundaries for future migration. Phase 5C-1 added the read-only `MarketPositionService` baseline. Phase 5C-2 added `TargetAllocationGenerationService` in shadow mode only. Phase 5C-3 adds controlled shadow export. Phase 5D adds multi-scenario shadow replay fixtures. Phase 5E adds a controlled promotion plan and a read-only mode helper. Phase 5F adds candidate/official promotion simulation checks. Phase 5G adds a candidate audit bundle for promotion review. Phase 6 adds a read-only history snapshot for audit consolidation. Phase 7A adds a read-only subject status center for profile, valuation, liquidity, and ResearchFirst gate visibility. Phase 7B adds a read-only subject gap and freshness center. Phase 7D adds a read-only research dashboard landing page. Phase 7E adds a read-only theme research center. Phase 7F adds a read-only bucket explorer for allocation drilldown. These phases do not replace target allocation artifacts, migrate action plan generation, trading execution, or QMT write access.

## Existing Read-Only Services

These services are available in the Web layer and must remain read-only:

- `CurrentStateService`: reads current SQLite state and current module sources.
- `RatioOnlyService`: sanitizes and rejects unsafe keys, text, and local absolute paths.
- `ResearchFirstGateService`: validates ResearchFirst gate status.
- `AllocationConsistencyService`: compares target allocation and intraday bucket rows.
- `MarketPositionService`: reads active `market_position_mappings` from SQLite and maps a score to equity/cash percentage ranges.
- `TargetAllocationGenerationService`: computes an in-memory shadow target allocation and compares core fields with the current reference JSON.
- `TargetAllocationControlledExportService`: packages the shadow target allocation and compare result for in-memory API download or CLI export under `temp/web_exports/`.
- `TargetAllocationPromotionSimulationService`: simulates candidate and official promotion paths without updating current research state.
- `TargetAllocationCandidateAuditService`: packages candidate simulation, shadow comparison, replay summary, promotion mode status, provenance, and safety checks for audit.
- `HistorySnapshotService`: scans temporary shadow/candidate audit artifacts and packages a read-only history snapshot with live current safety summaries.
- `SubjectGapService`: reads current subject, portfolio-position, target-allocation, and artifact freshness rows from SQLite for Web display.
- `SubjectStatusService`: reads current subject, profile, valuation, liquidity, and ResearchFirst rows from SQLite and returns neutral gate status for Web display.
- `DashboardService`: aggregates existing read-only services into the Research Dashboard API and page summary.
- `ThemeStatusService`: reads current theme/leader/ETF/stock artifact payloads and returns neutral theme research status for Web display.
- `BucketExplorerService`: joins current target-allocation buckets, portfolio positions, subject gate status, and subject freshness for Web allocation drilldown.
- `target_allocation_mode`: reads `MYINVEST_TARGET_ALLOCATION_MODE` and reports whether the requested mode is allowed or blocked.
- `ActionPlanService`: exposes action-plan read helpers.
- `PortfolioService`: exposes portfolio ratio snapshot read helpers.
- `SystemCheckService`: exposes current system-check summaries.
- `ReviewPackageExportService`: creates in-memory current-only review package exports.

These services may read the SQLite database and sanitized source payloads. They must not create orders, fills, share counts, or cash-amount instructions.

## Future Services Not Implemented In Phase 5C-2

The following services may be added later, but this phase does not implement them as generation replacements:

- `ActionPlanGenerationService`
- `DecisionLogService`
- `ReviewExportService`

Future service names are planning boundaries only. They do not authorize trading or QMT write behavior.

## Migration Order

1. Migrate `market_position_mapping` reads into a dedicated service. Completed in Phase 5C-1 as a read-only baseline.
2. Migrate target allocation calculations in shadow mode. Completed in Phase 5C-2 as in-memory compare-only output.
3. Add controlled shadow export to `temp/web_exports/` only. Completed in Phase 5C-3.
4. Harden target-allocation shadow mode with multi-scenario replay fixtures. Completed in Phase 5D.
5. Document controlled target-allocation promotion stages and block candidate/official execution in code. Completed in Phase 5E.
6. Simulate candidate temp export and official blocking without current-state mutation. Completed in Phase 5F.
7. Package candidate audit bundles for promotion review. Completed in Phase 5G.
8. Consolidate temporary shadow/candidate/controlled export audit artifacts into a history snapshot. Completed in Phase 6.
9. Add a read-only subject status center before action-plan generation migration. Completed in Phase 7A.
10. Add subject gap and freshness reads for Web visibility. Completed in Phase 7B.
11. Add a research dashboard landing page that aggregates existing read-only service outputs. Completed in Phase 7D.
12. Add a theme research center that aggregates current theme registry state. Completed in Phase 7E.
13. Add a bucket explorer that drills from allocation buckets into subject gate and freshness status. Completed in Phase 7F.
14. Migrate action plan generation in a future phase only after target allocation promotion remains stable.
15. At each step, extend golden tests to compare old-script output with new-service output.
16. If any golden test differs, do not replace the old script.
17. Keep old scripts as reference implementations until migration is stable.

The old generation scripts include `generate_target_allocation.py` and `generate_action_plan.py`; Phase 5C-2 does not modify their business rules. `scripts/generate_target_allocation.py` remains the target allocation reference implementation. `scripts/project_utils.py::market_position_for_score` remains the reference implementation for score-to-range behavior.

## Shadow Mode Rules

`TargetAllocationGenerationService` must:

- read current state from SQLite and `latest_index.modules` current paths only
- call `MarketPositionService` for score-to-range mapping
- return only in-memory shadow output
- compare core fields with the current target allocation JSON
- leave `research/latest_index.json`, `current_modules`, `artifacts`, and `research/allocation` unchanged
- report `unsupported_fields` explicitly instead of guessing or hard-coding unsupported rules

## Controlled Export Rules

`TargetAllocationControlledExportService` must:

- export only the shadow target allocation and compare result
- keep API exports in memory
- write CLI exports only under `temp/web_exports/`
- leave `research/latest_index.json`, `current_modules`, `artifacts`, `research/allocation`, and `research/actions` unchanged
- fail export when core shadow comparison has diffs
- keep all payloads ratio-only and current-only
- package ZIP files with only `manifest.json`, `shadow_target_allocation.json`, `compare_result.json`, `provenance.json`, and `system_checks.json`

## Phase 5D Replay Rules

Replay fixtures under `web/backend/tests/fixtures/target_allocation_scenarios/` must:

- provide explicit market score, market-position mapping, portfolio bucket actuals, bucket registry, and expected shadow output
- remain ratio-only and free of local absolute paths
- stay outside current-state resolution and production API reads
- never write `research/allocation`, `research/actions`, `research/latest_index.json`, `current_modules`, or `artifacts`
- cover score boundaries, risk-off, neutral, risk-on, max-score, overweight, underweight, and missing-bucket scenarios

`TargetAllocationGenerationService.generate_shadow_from_inputs(...)` exists for fixture replay and future migration validation. It does not change production API behavior, and it must not be used to treat fixtures as current state.

## Phase 5E Promotion Rules

`MYINVEST_TARGET_ALLOCATION_MODE` is a planning and safety flag. Phase 5E allows only:

- `reference`
- `shadow`
- `controlled_export`

The helper blocks:

- `candidate`
- `official`
- unknown values

Candidate promotion remains non-current and simulation-only. Official promotion remains future-only and requires a separate audit and explicit manual approval. The helper does not alter production API behavior and does not authorize writing `research/`, updating `latest_index`, or replacing old scripts.

## Phase 5F Promotion Simulation Rules

`TargetAllocationPromotionSimulationService` must:

- read current SQLite state and current module sources only
- build candidate output by passing explicit current inputs into `TargetAllocationGenerationService.generate_shadow_from_inputs(...)`
- write candidate simulation files only under `temp/candidate_exports/`
- require candidate filenames to include `candidate`
- compare candidate output with current shadow output
- return an official blocked report instead of writing official output
- leave `research/latest_index.json`, `current_modules`, `artifacts`, `research/allocation`, and `research/actions` unchanged
- keep all reports and temporary exports ratio-only

`scripts/simulate_target_allocation_promotion.py` is a local verification helper only. It is not a Web API write path and does not authorize candidate or official current-state replacement.

## Phase 5G Candidate Audit Rules

`TargetAllocationCandidateAuditService` must:

- build audit payloads in memory for API use
- write CLI exports only under `temp/candidate_exports/`
- require filenames to include `candidate_audit`
- include candidate output, compare result, replay summary, promotion mode status, safety checks, and provenance
- fail export when compare is not matched, unsupported fields are present, replay failed is greater than zero, or official mode is allowed
- leave `research/latest_index.json`, `current_modules`, `artifacts`, `research/allocation`, and `research/actions` unchanged
- keep JSON and ZIP payloads ratio-only and free of local absolute paths

Candidate audit bundles are review artifacts. They are not official target-allocation artifacts and must not become current.

## Phase 6 History Snapshot Rules

`HistorySnapshotService` must:

- scan temporary controlled shadow, candidate simulation, and candidate audit exports for audit summaries
- build a live current summary from SQLite-backed services
- generate API exports in memory
- write CLI exports only under ignored temporary export folders
- write the optional local history database only under ignored runtime storage
- package ZIP files with only `manifest.json`, `history_snapshot.json`, `history_entries.json`, `live_current_summary.json`, and `safety_checks.json`
- fail export when shadow compare is not matched, candidate audit compare is not matched, replay failures are nonzero, or official mode is allowed
- keep exported JSON and ZIP payloads ratio-only and free of runtime paths
- leave `research/latest_index.json`, `current_modules`, `artifacts`, `research/allocation`, and `research/actions` unchanged

History snapshots are audit artifacts. They are not current research state and must not become official target-allocation or action-plan artifacts.

## Phase 7A Subject Status Rules

`SubjectStatusService` must:

- read SQLite current-state rows produced from `research/latest_index.json` `modules`
- join subjects with profile, valuation, liquidity, ResearchFirst, portfolio bucket, and source artifact metadata
- return repo-relative source paths only
- normalize cash-equivalent display buckets without mutating the database or research files
- keep gate conclusions neutral: `eligible_for_review`, `research_first`, `watch`, `hold`, `no_action`, `unknown`, or `blocked`
- block buy/add/reduce/sell conclusions from the subject status API
- return 404 for missing subject codes without leaking traceback or local paths
- keep `/subjects` as a read-only page with refresh, search, sorting, pagination, and expandable details
- leave `research/latest_index.json`, `current_modules`, `artifacts`, `research/allocation`, and `research/actions` unchanged

Subject status is a visibility center. It is not a research generator, target-allocation generator, action-plan generator, or execution adapter.

## Phase 7B Subject Gap Rules

`SubjectGapService` must:

- read current SQLite state produced from `research/latest_index.json` `modules`
- join subjects with current portfolio-position rows and target-allocation bucket rows
- return subject position percentages plus bucket-level actual/target/gap percentages
- keep bucket actual/target/gap values aligned with current target-allocation bucket rows
- report freshness metadata from current portfolio, target-allocation, and subject artifact timestamps
- generate API responses in memory only
- keep `/subjects/gap` as a read-only page with refresh, search, sorting, pagination, and expandable details
- leave `research/latest_index.json`, `current_modules`, `artifacts`, `research/allocation`, and `research/actions` unchanged

Subject gap is a visibility center. It is not a target-allocation generator, action-plan generator, promotion mechanism, or execution adapter.

## Phase 7D Dashboard Rules

`DashboardService` must:

- read current SQLite state produced from `research/latest_index.json` `modules`
- call existing read-only services for system status, market position, action plan summary, allocation summary, subject status, and subject gap
- return counts, statuses, timestamps, percentage ratios, percentage-point gaps, and local Web quick links only
- keep `/api/dashboard/current`, `/`, and `/dashboard` read-only
- pass every response through `RatioOnlyService`
- keep `scripts/run_web.py` as a local Web starter with default host `0.0.0.0` and host override support
- leave `research/latest_index.json`, `current_modules`, `artifacts`, `research/allocation`, and `research/actions` unchanged

The dashboard is a landing page and review helper. It is not a research generator, target-allocation generator, action-plan generator, promotion mechanism, or execution adapter.

## Phase 7E Theme Research Rules

`ThemeStatusService` must:

- read current SQLite artifact payloads produced from `research/latest_index.json` `modules`
- use current `theme_registry`, `theme_leaders`, `etf_registry`, and `stock_registry` data only
- avoid `latest_index.files` as a current resolver
- return neutral theme states only: `confirmed`, `watch`, `research_first`, `stale`, `conflict`, or `unknown`
- keep associated ETF/stock gate conclusions neutral and block buy/add/reduce/sell conclusions
- keep `/api/themes/status`, `/api/themes/status/{theme_name}`, and `/themes` read-only
- pass every API response through `RatioOnlyService`
- leave `research/latest_index.json`, `current_modules`, `artifacts`, `research/allocation`, and `research/actions` unchanged

The theme center is a research visibility page. It is not a trading page, action-plan generator, target-allocation generator, promotion mechanism, or execution adapter.

## Phase 7F Bucket Explorer Rules

`BucketExplorerService` must:

- read current SQLite state produced from `research/latest_index.json` `modules`
- reuse current-state, subject-status, and subject-gap services instead of resolving `latest_index.files`
- join bucket actual/target/gap rows with current portfolio-position subject rows
- return per-bucket counts, neutral gap status, risk notes, and per-subject ResearchFirst gate status
- keep gap status neutral: `near_target`, `overweight`, `underweight`, `zero_target_nonzero_actual`, or `unknown`
- show a nonzero legacy watch bucket with zero target as `zero_target_nonzero_actual`, not as an action
- block buy/add/reduce/sell conclusions from bucket and subject display payloads
- keep `/api/buckets/status`, `/api/buckets/status/{bucket}`, and `/buckets` read-only
- pass every API response through `RatioOnlyService`
- leave `research/latest_index.json`, `current_modules`, `artifacts`, `research/allocation`, and `research/actions` unchanged

The bucket explorer is an allocation visibility page. It is not a target-allocation generator, action-plan generator, promotion mechanism, trading page, or execution adapter.

## Hard Service Boundaries

Services must not:

- bypass ResearchFirst gates
- output cash amounts or share counts
- generate order/fill records
- connect to QMT write interfaces
- treat `latest_index.files` as current state
- return local absolute paths
- write SQLite, runtime, temp, cache, ZIP, log, or build artifacts into Git scope

Any future write-like behavior must be proposed as a separate phase with explicit review. It is out of scope for the read-only Web milestone.
