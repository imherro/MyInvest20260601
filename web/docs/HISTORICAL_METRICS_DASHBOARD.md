# Historical Metrics Dashboard

Phase 8 adds a read-only Historical Metrics dashboard for review analytics.

## Scope

The dashboard aggregates current-only and read-only history summaries from:

- target allocation bucket gaps exposed by the history gap dashboard
- subject gap and ResearchFirst status
- theme status summaries
- decision timeline event types
- current market-score context

It is a visibility and review page only. It does not generate target allocations, generate action plans, write research artifacts, write temporary exports, create trading instructions, or connect to QMT write interfaces.

## API

- `GET /api/historical-metrics`
- `GET /api/historical-metrics/{entity_id}`

The API returns:

- `summary`
- `series`
- `aggregations`
- `entities`
- `source_modules`
- `safety`

Entity rows use neutral fields such as `entity_id`, `entity_type`, `label`, `status`, percentage ratios, percentage-point gaps, timestamps, counts, trend indicators, and relative review links.

## Page

`GET /historical-metrics` renders a Jinja2 first screen and refreshes from `/api/historical-metrics` through static JS.

The page supports:

- refresh
- search
- entity type filter
- status filter
- sorting
- pagination
- expandable details
- bucket gap visualization with tooltip text

## Validation

Run:

```bash
python scripts/ingest_current_state.py
python -m pytest web/backend/tests/test_historical_metrics.py
python -m pytest web/backend/tests
python scripts/web_check.py
python scripts/check_hidden_unicode.py
python scripts/project_check.py --current-only
```

The dashboard must remain ratio-only, ResearchFirst-compatible, current-only, and read-only.
