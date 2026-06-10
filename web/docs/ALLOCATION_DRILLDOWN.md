# Allocation Drilldown

Phase 7H adds a read-only allocation drilldown view for bucket and subject review.

## Scope

- `GET /api/buckets/drilldown`
- `GET /api/buckets/drilldown?bucket=<bucket>&detail=full`
- `GET /api/subjects/drilldown`
- `GET /api/subjects/drilldown?subject=<code>&detail=full`
- `GET /buckets/drilldown`
- `GET /subjects/drilldown`

The service assembles current SQLite rows for target allocation, portfolio positions, subject gap, subject gate status, market position, and theme association summaries. It generates responses in memory only.

## Boundaries

Allocation drilldown is a Web visibility feature. It is not a generator, promotion path, execution adapter, or trading workflow.

It must not:

- update `research/latest_index.json`
- write `research/actions` or `research/allocation`
- generate action plans
- generate target-allocation artifacts
- create orders, fills, account records, cash amounts, share counts, or QMT write calls
- read `latest_index.files` as current state
- return local absolute paths

## Ratio-Only Fields

Allowed fields are limited to:

- bucket name
- subject code and name
- neutral gate/status labels
- percentage ratios
- percentage-point gaps
- timestamps
- relative Web review links
- repo-relative current module source metadata

All API responses pass `RatioOnlyService` through the shared `respond(...)` wrapper. The frontend refresh path also runs the static JS ratio-only check before rendering.

## Page Interaction

`/buckets/drilldown` shows bucket actual/target/gap rows, a bucket actual-vs-target chart, gap status filters, search, sorting, pagination, and expandable details.

`/subjects/drilldown` shows subject position ratio, bucket actual/target/gap, ResearchFirst status, neutral gate conclusion, theme count, filters, search, sorting, pagination, and expandable details.

Both pages are read-only and refresh from their matching API endpoints.

## Verification

Run:

```bash
python scripts/ingest_current_state.py
python -m pytest web/backend/tests/test_allocation_drilldown.py
python scripts/web_check.py
```

`scripts/web_check.py` verifies the Phase 7H files, API safety, target-allocation consistency, ResearchFirst-neutral status, 511360 cash-short display, frontend hooks, and current-only code paths.
