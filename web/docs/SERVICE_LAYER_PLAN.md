# Service Layer Plan

Phase 5A documented service boundaries for future migration. Phase 5C-1 added the read-only `MarketPositionService` baseline. Phase 5C-2 added `TargetAllocationGenerationService` in shadow mode only. Phase 5C-3 adds controlled shadow export. It does not replace target allocation artifacts, migrate action plan generation, trading execution, or QMT write access.

## Existing Read-Only Services

These services are available in the Web layer and must remain read-only:

- `CurrentStateService`: reads current SQLite state and current module sources.
- `RatioOnlyService`: sanitizes and rejects unsafe keys, text, and local absolute paths.
- `ResearchFirstGateService`: validates ResearchFirst gate status.
- `AllocationConsistencyService`: compares target allocation and intraday bucket rows.
- `MarketPositionService`: reads active `market_position_mappings` from SQLite and maps a score to equity/cash percentage ranges.
- `TargetAllocationGenerationService`: computes an in-memory shadow target allocation and compares core fields with the current reference JSON.
- `TargetAllocationControlledExportService`: packages the shadow target allocation and compare result for in-memory API download or CLI export under `temp/web_exports/`.
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
4. Migrate action plan generation.
5. At each step, extend golden tests to compare old-script output with new-service output.
6. If any golden test differs, do not replace the old script.
7. Keep old scripts as reference implementations until migration is stable.

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
