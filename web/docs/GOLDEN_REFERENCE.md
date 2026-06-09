# Golden Reference

Phase 5A introduces a golden reference baseline for the current Web read model. The baseline compares current research JSON, resolved only through `research/latest_index.json` `modules`, with the SQLite read model.

The goal is to make later service migration measurable. Future code that generates target allocation or action plans from the database must match the old artifact-driven reference before it can replace old scripts.

## Rules

- Resolve every source path from `latest_index.modules`.
- Do not read `latest_index.files` for current state.
- Do not hard-code action plan timestamps or file names.
- Compare only ratio-only fields.
- Do not compare or introduce cash amounts, share counts, account identifiers, order records, fill records, or local absolute paths.
- Any mismatch is a blocking test failure.

## Golden Fields

The baseline covers:

- market-position mapping JSON vs SQLite rows
- market-position service output vs `scripts/project_utils.py::market_position_for_score`
- market-position boundary scores: `0`, `25`, `30`, `31`, `45`, `46`, `60`, `61`, `75`, `76`, `85`, `86`, `100`
- target-allocation shadow output vs current `latest_index.modules.target_allocation` JSON
- current action plan path
- action plan `generated_at`
- action count
- ResearchFirst item count
- market target equity range
- cash/short-duration target, actual, and gap
- `core_base` target, actual, and gap
- `attack_mainline` target, actual, and gap
- `defense` target, actual, and gap
- `legacy_watch` target, actual, and gap
- target-allocation shadow no-mutation checks for `latest_index`, `current_modules`, `artifacts`, and `research/allocation`
- intraday rules status
- ResearchFirst gate status
- 511360 liquidity status, valuation status, duration boundary, and risk disclosure gates

Bucket values are compared from current target-allocation JSON to SQLite `bucket_allocations`. Intraday bucket consistency is already checked separately against `intraday_bucket_rules`.

## Test

Run the golden baseline directly:

```bash
python -m pytest web/backend/tests/test_golden_current_state.py
```

Run the Phase 5C-1 market-position baseline directly:

```bash
python -m pytest web/backend/tests/test_market_position_service.py
```

Run the Phase 5C-2 target-allocation shadow baseline directly:

```bash
python -m pytest web/backend/tests/test_target_allocation_generation_shadow.py
```

The test performs a fresh ingest through the shared test fixture, reads current JSON through `latest_index.modules`, then reads the same facts from `temp/web_db/myinvest.sqlite`.

## Migration Policy

When a future service replaces part of the old generation flow:

1. Keep the old script as the reference implementation.
2. Generate the old artifact and new service output from the same current inputs.
3. Extend the golden test to compare the relevant ratio-only fields.
4. Do not switch callers to the service if the golden test differs.

Target allocation is now in Phase 5C-2 shadow mode. The shadow service may compute in-memory target allocation fields and compare them with the current reference, but it must not replace old outputs, update `latest_index`, or write files under `research/allocation`. Future replacement requires the golden comparison to remain clean over multiple runs.
