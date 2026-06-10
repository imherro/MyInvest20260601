# Service Layer Plan

Phase 5A documented service boundaries for future migration. Phase 5C-1 added the read-only `MarketPositionService` baseline. Phase 5C-2 added `TargetAllocationGenerationService` in shadow mode only. Phase 5C-3 adds controlled shadow export. Phase 5D adds multi-scenario shadow replay fixtures. Phase 5E adds a controlled promotion plan and a read-only mode helper. Phase 5F adds candidate/official promotion simulation checks. Phase 5G adds a candidate audit bundle for promotion review. Phase 6 adds a read-only history snapshot for audit consolidation. These phases do not replace target allocation artifacts, migrate action plan generation, trading execution, or QMT write access.

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
9. Migrate action plan generation in a future phase only after target allocation promotion remains stable.
10. At each step, extend golden tests to compare old-script output with new-service output.
11. If any golden test differs, do not replace the old script.
12. Keep old scripts as reference implementations until migration is stable.

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
