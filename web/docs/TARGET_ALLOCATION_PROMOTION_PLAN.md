# Target Allocation Promotion Plan

Phase 5E defines a controlled promotion plan for `TargetAllocationGenerationService`. Phase 5F adds simulation checks for candidate and official modes. Phase 5G adds a candidate audit bundle for promotion review. These phases do not replace `scripts/generate_target_allocation.py`.

## Current Status

The current Web service layer has:

- read-only SQLite current-state ingest
- current-only APIs based on `latest_index.modules`
- `MarketPositionService` baseline
- `TargetAllocationGenerationService` shadow mode
- controlled shadow export to `temp/web_exports/`
- multi-scenario shadow replay fixtures
- candidate promotion simulation export to `temp/candidate_exports/`
- candidate audit bundle export to `temp/candidate_exports/`
- official promotion blocked report
- `scripts/web_check.py` and GitHub Actions validation

The old `scripts/generate_target_allocation.py` remains the reference implementation and the only official generator for current target-allocation artifacts.

## Promotion Stages

### Stage 0: Reference

- Old script remains the only official source.
- Web service may read current SQLite state.
- No service-generated target allocation is treated as current.

### Stage 1: Shadow

- New service computes in memory only.
- It compares core fields with the current reference JSON.
- It does not write files.
- It does not update `latest_index`.
- It does not update `current_modules`.

### Stage 2: Controlled Export

- New service may export shadow artifacts for review.
- API export stays in memory.
- CLI export writes only under `temp/web_exports/`.
- Export must include compare results and safety metadata.
- Export must fail when core diffs exist.

### Stage 3: Candidate Export

Simulation only in Phase 5F.

- Candidate simulation exports write only under `temp/candidate_exports/`.
- Filenames must include `candidate`.
- Candidate files must not enter `research/`.
- Candidate files must not become current.
- Candidate output must include a golden comparison with shadow mode.
- Candidate mode is still blocked by the mode helper; the explicit simulation script is the only Phase 5F path that may write a temporary candidate file.
- Candidate simulation must not update `latest_index`, `current_modules`, `research/allocation`, or `research/actions`.

### Stage 4: Official

Future only.

- Requires separate audit.
- Requires explicit manual approval.
- Requires current golden comparison, replay fixtures, controlled export scan, review package scan, and CI to pass.
- Requires no ResearchFirst or ratio-only violation.
- Requires no trading, QMT write, order, fill, share-count, or cash-amount behavior.
- Official mode is blocked by the mode helper.
- Phase 5F official simulation returns a blocked report and must not write any file.

## Feature Flag Design

Environment variable:

```text
MYINVEST_TARGET_ALLOCATION_MODE
```

Allowed values in Phase 5E and Phase 5F:

- `reference`
- `shadow`
- `controlled_export`

Blocked values in Phase 5E and Phase 5F:

- `candidate`
- `official`

Default value:

```text
shadow
```

Unknown values are blocked. The helper reports status only and does not alter production API behavior.

## Phase 5F Simulation Checks

Phase 5F adds `TargetAllocationPromotionSimulationService` and `scripts/simulate_target_allocation_promotion.py`.

Candidate simulation:

- reads the current SQLite state
- converts the current state into explicit replay inputs
- calls `TargetAllocationGenerationService.generate_shadow_from_inputs(...)`
- writes only to `temp/candidate_exports/` when `--write` is passed
- requires the filename to contain `candidate`
- compares candidate output with current shadow output
- keeps the payload ratio-only and free of local absolute paths

Official simulation:

- returns `status = blocked`
- returns no output path
- writes no files
- does not affect current state

## Phase 5G Candidate Audit Bundle

Phase 5G adds `TargetAllocationCandidateAuditService` and `scripts/export_target_allocation_candidate_audit.py`.

Candidate audit bundle:

- combines candidate simulation output
- includes shadow-vs-reference comparison
- includes candidate-vs-shadow comparison
- includes replay fixture summary
- includes promotion mode status
- includes provenance and safety checks
- writes only to `temp/candidate_exports/` when the CLI is used
- uses filenames containing `candidate_audit`
- stays ratio-only and current-only

The candidate audit bundle is not official target allocation. It must not be copied to `research/allocation`, must not update `latest_index`, must not update `current_modules`, and must not generate action plans.

Official promotion remains hard blocked. If official mode is ever reported as allowed, Phase 5G validation must fail.

## Safety Gates

Any non-reference promotion path must pass:

- ratio-only sanitizer
- ResearchFirst gate
- allocation consistency check
- `project_check.py --current-only`
- current golden comparison
- multi-scenario replay fixtures
- controlled export scan
- candidate simulation scan
- candidate audit bundle scan
- official blocked scan
- no research mutation
- no `latest_index` mutation
- no action-plan mutation
- no forbidden fields
- no local absolute paths
- no trading or QMT write code

## Promotion Checklist

Before any future promotion beyond shadow:

- CI passes
- `scripts/web_check.py` passes with no FAIL
- current golden comparison matches
- replay fixtures pass
- controlled export matches
- review package export is safe
- no forbidden fields are present
- no local absolute paths are present
- no trading code is introduced
- manual review is complete
- a decision-log entry is prepared if official promotion is ever approved

## Rollback Plan

- Return `MYINVEST_TARGET_ALLOCATION_MODE` to `reference` or `shadow`.
- Delete temporary candidate exports from `temp/candidate_exports/`, if any.
- Do not touch `research/`.
- Do not touch `latest_index`.
- Do not touch action-plan artifacts.
- Keep old scripts as reference.

## Explicit Non-Goals

Phase 5E and Phase 5F do not:

- replace `scripts/generate_target_allocation.py`
- modify `scripts/generate_target_allocation.py`
- replace or modify `scripts/generate_action_plan.py`
- write official target-allocation artifacts
- write action-plan artifacts
- update `research/latest_index.json`
- update `current_modules`
- generate orders
- connect to QMT write interfaces
- calculate share counts or cash amounts
