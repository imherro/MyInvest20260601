# History Gap Dashboard

Phase 7G adds a read-only History Gap Dashboard for Web review.

## Scope

The dashboard aggregates in-memory current and audit snapshot data:

- current target allocation bucket rows
- controlled shadow target-allocation snapshot
- candidate audit target-allocation snapshot
- history snapshot entry summaries

It reads current SQLite state produced from `research/latest_index.json` `modules`. It must not read `latest_index.files` as a current resolver.

## API

- `GET /api/history/gap-summary`
- `GET /api/history/gap-summary/{bucket}`

Responses include:

- summary counts
- bucket actual, target, and gap percentages
- neutral gap status
- alert status
- per-bucket timeline points
- history entry summaries
- safety flags

Gap status and alert status are display-only review states. They are not action-plan instructions.

## Page

- `GET /history/gap-dashboard`

The page supports:

- refresh
- search
- gap-status filter
- sorting
- pagination
- expandable details
- bucket gap evolution visualization with tooltip text

The shared frontend sanitizer checks refreshed payloads before rendering.

## Boundaries

The History Gap Dashboard is not a trading page, generator, promotion mechanism, or export writer. It must not:

- write research files
- update `latest_index`
- update `current_modules`
- generate target allocation
- generate action plans
- add trading, execution, or QMT write behavior
- expose local absolute paths
- expose sensitive account, execution, cash, or share data

## Validation

Run:

```bash
python scripts/ingest_current_state.py
python -m pytest web/backend/tests/test_history_gap_dashboard.py
python scripts/web_check.py
```
