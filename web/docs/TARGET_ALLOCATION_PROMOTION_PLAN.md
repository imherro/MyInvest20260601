# Target Allocation Promotion Plan

Phase 5E defines a controlled promotion plan for `TargetAllocationGenerationService`. It is a plan and safety design only. It does not replace `scripts/generate_target_allocation.py`.

## Current Status

The current Web service layer has:

- read-only SQLite current-state ingest
- current-only APIs based on `latest_index.modules`
- `MarketPositionService` baseline
- `TargetAllocationGenerationService` shadow mode
- controlled shadow export to `temp/web_exports/`
- multi-scenario shadow replay fixtures
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

Design only in this phase.

- Candidate exports would write only under `temp/candidate_exports/`.
- Filenames must include `candidate`.
- Candidate files must not enter `research/`.
- Candidate files must not become current.
- Candidate output must include compare results.
- Candidate mode is blocked by the Phase 5E helper.

### Stage 4: Official

Future only.

- Requires separate audit.
- Requires explicit manual approval.
- Requires current golden comparison, replay fixtures, controlled export scan, review package scan, and CI to pass.
- Requires no ResearchFirst or ratio-only violation.
- Requires no trading, QMT write, order, fill, share-count, or cash-amount behavior.
- Official mode is blocked by the Phase 5E helper.

## Feature Flag Design

Environment variable:

```text
MYINVEST_TARGET_ALLOCATION_MODE
```

Allowed values in Phase 5E:

- `reference`
- `shadow`
- `controlled_export`

Blocked values in Phase 5E:

- `candidate`
- `official`

Default value:

```text
shadow
```

Unknown values are blocked. The helper reports status only and does not alter production API behavior.

## Safety Gates

Any non-reference promotion path must pass:

- ratio-only sanitizer
- ResearchFirst gate
- allocation consistency check
- `project_check.py --current-only`
- current golden comparison
- multi-scenario replay fixtures
- controlled export scan
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
- Delete temporary candidate exports, if any.
- Do not touch `research/`.
- Do not touch `latest_index`.
- Do not touch action-plan artifacts.
- Keep old scripts as reference.

## Explicit Non-Goals

Phase 5E does not:

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
