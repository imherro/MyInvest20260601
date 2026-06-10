# Decision Timeline

Phase 7I adds a read-only Decision Timeline / Review Timeline for Web review.

## Scope

The timeline combines current-only review events from:

- current action plan metadata loaded from `latest_index.modules.action_plan`
- current target allocation metadata loaded from `latest_index.modules.target_allocation`
- recent decision log entries imported into SQLite
- read-only history snapshot entries already exposed by `HistorySnapshotService`

It is a navigation and review page only. It does not generate action plans, generate target allocations, write research artifacts, write temporary exports, create trading instructions, or connect to QMT write interfaces.

## API

- `GET /api/decision-timeline`
- `GET /api/decision-timeline/{event_id}`

Each event includes neutral fields:

- `event_id`
- `event_type`
- `timestamp`
- `title`
- `summary`
- `status`
- `basis_trade_date`
- ratio-only `details`
- relative `review_links`

The API response includes `summary`, `events`, `source_modules`, and `safety`. The safety flags must keep `ratio_only`, `current_only`, `read_only`, and `uses_latest_index_modules` true, while `uses_latest_index_files`, generation flags, trading flags, and QMT write flags remain false.

## Page

`GET /decision-timeline` renders a Jinja2 first screen and then refreshes from `/api/decision-timeline` through static JS.

The page supports:

- refresh
- search
- event type filter
- status filter
- sorting
- pagination
- expandable details
- timeline visualization with tooltip text

## Validation

Run:

```bash
python scripts/ingest_current_state.py
python -m pytest web/backend/tests/test_decision_timeline.py
python -m pytest web/backend/tests
python scripts/web_check.py
python scripts/check_hidden_unicode.py
python scripts/project_check.py --current-only
```

The timeline must remain ratio-only, ResearchFirst-compatible, current-only, and read-only.
