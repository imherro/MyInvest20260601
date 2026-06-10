# Bucket Explorer

Phase 7F adds a read-only Bucket Explorer for allocation drilldown.

## Scope

The explorer reads current SQLite state loaded from `research/latest_index.json` `modules`:

- current target allocation bucket rows
- current portfolio ratio snapshot
- current subject profile, valuation, liquidity, and ResearchFirst gate status
- current subject gap and freshness status

It must not read `latest_index.files` as a current resolver.

## API

- `GET /api/buckets/status`
- `GET /api/buckets/status/{bucket}`

Responses include:

- `summary`
- `buckets`
- per-bucket actual, target, and gap percentages
- neutral `gap_status`
- risk notes
- per-subject ResearchFirst gate status
- repo-relative source metadata

Gap status is presentation-only:

- `near_target`
- `overweight`
- `underweight`
- `zero_target_nonzero_actual`
- `unknown`

A legacy watch bucket with nonzero actual allocation and zero target allocation is displayed as `zero_target_nonzero_actual`. This is a review state, not an action.

## Page

- `GET /buckets`

The page supports:

- refresh
- search
- bucket and gate filters
- sorting
- pagination
- expandable details

The page uses the shared static JavaScript sanitizer before rendering refreshed API data.

## Boundaries

Bucket Explorer is not a trading page, generator, or promotion mechanism. It must not:

- write research files
- update `latest_index`
- update `current_modules`
- generate target allocation
- generate action plans
- add trading, execution, or QMT write behavior
- expose local absolute paths
- expose sensitive account, execution, cash, or share data

Bucket and subject states must not become buy/add/reduce/sell actions. Any subject missing profile, valuation, liquidity, or theme-binding evidence remains under ResearchFirst review or blocked status.

## Validation

Run:

```bash
python scripts/ingest_current_state.py
python -m pytest web/backend/tests/test_bucket_explorer.py
python scripts/web_check.py
```
