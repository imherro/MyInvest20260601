# Service Layer Plan

Phase 5A documents service boundaries for future migration. It does not migrate target allocation generation, action plan generation, trading execution, or QMT write access.

## Existing Read-Only Services

These services are available in the Web layer and must remain read-only:

- `CurrentStateService`: reads current SQLite state and current module sources.
- `RatioOnlyService`: sanitizes and rejects unsafe keys, text, and local absolute paths.
- `ResearchFirstGateService`: validates ResearchFirst gate status.
- `AllocationConsistencyService`: compares target allocation and intraday bucket rows.
- `ActionPlanService`: exposes action-plan read helpers.
- `PortfolioService`: exposes portfolio ratio snapshot read helpers.
- `SystemCheckService`: exposes current system-check summaries.
- `ReviewPackageExportService`: creates in-memory current-only review package exports.

These services may read the SQLite database and sanitized source payloads. They must not create orders, fills, share counts, or cash-amount instructions.

## Future Services Not Implemented In Phase 5A

The following services may be added later, but this phase does not implement them as generation replacements:

- `MarketPositionService`
- `TargetAllocationGenerationService`
- `ActionPlanGenerationService`
- `DecisionLogService`
- `ReviewExportService`

Future service names are planning boundaries only. They do not authorize trading or QMT write behavior.

## Migration Order

1. Migrate `market_position_mapping` reads into a dedicated service.
2. Migrate target allocation calculations.
3. Migrate action plan generation.
4. At each step, extend golden tests to compare old-script output with new-service output.
5. If any golden test differs, do not replace the old script.
6. Keep old scripts as reference implementations until migration is stable.

The old generation scripts include `generate_target_allocation.py` and `generate_action_plan.py`; Phase 5A does not modify their business rules.

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
