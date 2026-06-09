# Service Layer Plan

Phase 5A documented service boundaries for future migration. Phase 5C-1 adds the read-only `MarketPositionService` baseline. It does not migrate target allocation generation, action plan generation, trading execution, or QMT write access.

## Existing Read-Only Services

These services are available in the Web layer and must remain read-only:

- `CurrentStateService`: reads current SQLite state and current module sources.
- `RatioOnlyService`: sanitizes and rejects unsafe keys, text, and local absolute paths.
- `ResearchFirstGateService`: validates ResearchFirst gate status.
- `AllocationConsistencyService`: compares target allocation and intraday bucket rows.
- `MarketPositionService`: reads active `market_position_mappings` from SQLite and maps a score to equity/cash percentage ranges.
- `ActionPlanService`: exposes action-plan read helpers.
- `PortfolioService`: exposes portfolio ratio snapshot read helpers.
- `SystemCheckService`: exposes current system-check summaries.
- `ReviewPackageExportService`: creates in-memory current-only review package exports.

These services may read the SQLite database and sanitized source payloads. They must not create orders, fills, share counts, or cash-amount instructions.

## Future Services Not Implemented In Phase 5C-1

The following services may be added later, but this phase does not implement them as generation replacements:

- `TargetAllocationGenerationService`
- `ActionPlanGenerationService`
- `DecisionLogService`
- `ReviewExportService`

Future service names are planning boundaries only. They do not authorize trading or QMT write behavior.

## Migration Order

1. Migrate `market_position_mapping` reads into a dedicated service. Completed in Phase 5C-1 as a read-only baseline.
2. Migrate target allocation calculations in shadow mode.
3. Migrate action plan generation.
4. At each step, extend golden tests to compare old-script output with new-service output.
5. If any golden test differs, do not replace the old script.
6. Keep old scripts as reference implementations until migration is stable.

The old generation scripts include `generate_target_allocation.py` and `generate_action_plan.py`; Phase 5C-1 does not modify their business rules. `scripts/project_utils.py::market_position_for_score` remains the reference implementation for score-to-range behavior.

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
