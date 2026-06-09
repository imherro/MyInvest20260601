# MyInvest Web Runbook

## Scope

This Web MVP is read-only. It reads current research state from `research/latest_index.json` through `latest_index.modules`, ingests a ratio-only subset into SQLite, and serves local browser views through FastAPI.

## Initialize Database

```bash
python scripts/ingest_current_state_to_web_db.py
```

The database is written to `temp/web_db/myinvest_web.sqlite`. This path is ignored by Git.

## Start Backend

```bash
python -m uvicorn web.backend.app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`.

## Run Tests

```bash
pytest web/backend/tests
```

## Validation

The ingest command runs:

- `python scripts/check_ratio_only.py --path <latest_index.modules.action_plan.path>`
- `python scripts/check_research_first_gate.py --path <latest_index.modules.action_plan.path>`
- `python scripts/check_cross_file_allocation_consistency.py`
- `python scripts/project_check.py --current-only`

Any failure blocks ingest.
