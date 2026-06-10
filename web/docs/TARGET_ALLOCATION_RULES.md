# Target Allocation Rules

Phase 5D documents the rules used by `TargetAllocationGenerationService` shadow replay. These rules are validation scaffolding for service migration. They do not replace `scripts/generate_target_allocation.py`.

## Inputs

- `market_score.score`: numeric score from 0 to 100.
- `market_position_mapping`: score ranges with equity and cash-short percentage ranges.
- `portfolio_bucket_actual`: current bucket percentages from a fixture or current portfolio aggregation.
- `bucket_registry`: labels and visual metadata for known buckets.

Current production reads still come from SQLite current state created from `research/latest_index.json` `modules`. Replay fixtures live under `web/backend/tests/fixtures/target_allocation_scenarios/` and must never be treated as current state.

## Score Mapping

The service maps `market_score.score` to the first active mapping row where:

```text
score_min <= score <= score_max
```

Boundary scores are inclusive. The Phase 5D fixtures cover score 30, score 31, and score 100 to prevent off-by-one changes.

## Range Centers

The selected mapping row defines:

- `equity_range.min_pct`
- `equity_range.max_pct`
- `cash_short_range.min_pct`
- `cash_short_range.max_pct`

The target centers are:

```text
target_equity_pct = (equity_min_pct + equity_max_pct) / 2
target_cash_short_pct = (cash_min_pct + cash_max_pct) / 2
```

Centers are rounded to two decimal places.

## Bucket Targets

Bucket target percentages are computed from the center values:

```text
cash_short = target_cash_short_pct
core_base = target_equity_pct * 57%
attack_mainline = target_equity_pct * 14%
defense = target_equity_pct - core_base - attack_mainline
legacy_watch = 0
```

`core_base`, `attack_mainline`, `defense`, and `cash_short` targets are rounded to two decimal places. `legacy_watch` always has target `0`.

## Actuals And Gaps

Actual bucket percentages come from `portfolio_bucket_actual` in replay fixtures or current portfolio aggregation in production shadow mode.

For each bucket:

```text
gap_pct = actual_pct - target_pct
```

The service reports allocation gaps only. It does not generate action plans, order intent, share counts, cash amounts, or execution instructions.

## Missing Bucket Actuals

Phase 5D uses this explicit rule for replay fixtures:

- Missing bucket actuals are treated as `0` percentage points.
- The shadow output includes a warning with `code = missing_bucket_actual`.
- Missing bucket handling is validation-only and must remain visible in replay results.

The service must not silently guess a missing bucket from other fields.

## Safety Boundaries

The service must not:

- write `research/allocation`
- update `research/latest_index.json`
- update `current_modules` or `artifacts`
- generate an action plan
- connect to QMT write interfaces
- output monetary amounts, share counts, account identifiers, order records, fill records, or local absolute paths
- use `latest_index.files` as a current-state resolver

## Promotion Criteria

Future replacement of `scripts/generate_target_allocation.py` is allowed only after explicit manual approval and all of these conditions are true:

- current golden comparison passes
- Phase 5D replay fixtures pass
- `scripts/web_check.py` passes with no FAIL
- review package export remains ratio-only and current-only
- controlled export has no core diffs
- `MYINVEST_TARGET_ALLOCATION_MODE` promotion stage is explicitly reviewed
- no ResearchFirst or ratio-only violation exists
- no trading, QMT write, order, fill, share-count, or cash-amount behavior is introduced

Phase 5E keeps `candidate` and `official` blocked. It documents future stages but does not authorize current-state replacement.
