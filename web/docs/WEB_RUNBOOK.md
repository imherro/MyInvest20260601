# MyInvest Web Runbook

## Scope

This Web MVP is read-only. It reads current research state from `research/latest_index.json` through `latest_index.modules`, ingests a ratio-only subset into SQLite, and serves local browser views through FastAPI.

## Initialize Database

```bash
python scripts/ingest_current_state.py
```

The database is written to `temp/web_db/myinvest.sqlite`. This path is ignored by Git. The ingest reads only `research/latest_index.json` `modules` pointers; it does not treat `latest_index.files` as current.

The lower-level implementation remains available at:

```bash
python scripts/ingest_current_state_to_web_db.py
```

## Start Backend

```bash
python -m uvicorn web.backend.app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`.

The Web UI is FastAPI + Jinja2 with a small static refresh script. There is no React build step in this phase.

## Run Tests

```bash
pytest web/backend/tests
```

## Phase 3 Milestone Check

Phase 3 is frozen as a read-only Web milestone. It is not a trading system and does not expose order, execution, or QMT write interfaces.

Run the one-command gate before committing Web milestone changes:

```bash
python scripts/web_check.py
```

The check runs:

- `python scripts/ingest_current_state.py`
- `python -m pytest web/backend/tests`
- `python scripts/check_ratio_only.py --path <latest_index.modules.action_plan.path>`
- `python scripts/check_research_first_gate.py --path <latest_index.modules.action_plan.path>`
- `python scripts/check_cross_file_allocation_consistency.py`
- `python scripts/project_check.py --current-only`
- API and export forbidden-field scans
- export ZIP/JSON current-only and ratio-only scans
- page interaction hook checks for refresh, search, sort, pagination, expandable rows, Dashboard status cards, and the frontend ratio-only sanitizer
- Git scope checks for forbidden runtime or sensitive files

Output statuses:

- `PASS`: safe to prepare a commit.
- `WARN`: command passed, but a non-blocking warning needs review.
- `FAIL`: blocks commit; fix the listed file/reason and rerun the check.

The script prints a suggested commit message and the files that belong in the commit. Do not commit `temp/`, SQLite/DB files, `runtime/`, caches, `node_modules/`, build/dist outputs, `.env`, ZIP, or log artifacts.

The same gate runs in GitHub Actions via `.github/workflows/web_check.yml` on push and pull request.

## API and Page Smoke Check

```bash
python scripts/ingest_current_state.py
python -m uvicorn web.backend.app.main:app --host 127.0.0.1 --port 8000
```

Then open:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/api/current`
- `http://127.0.0.1:8000/api/modules/current`
- `http://127.0.0.1:8000/api/export/review_package?format=json`

## Page Interactions

- `Refresh` reloads the current page data from the matching `/api/.../current` endpoint.
- Pages also refresh automatically every 60 seconds.
- Table headers with sort markers can be clicked to sort.
- Search boxes filter the current table; `Clear` resets the filter.
- Tables page rows client-side; use `Prev` and `Next` below the table.
- Click a table row to expand or collapse ratio-only detail text.
- Dashboard shows bucket allocation gaps as a centered bar chart and highlights ResearchFirst and intraday status.

Every frontend refresh performs a lightweight forbidden-field scan before rendering. Server responses are also checked by `RatioOnlyService`.

## Export Current Review Package

JSON snapshot:

```bash
curl "http://127.0.0.1:8000/api/export/review_package?format=json"
```

ZIP package:

```bash
curl -o myinvest_current_review_package.zip "http://127.0.0.1:8000/api/export/review_package"
```

The export is current-only and includes the current action plan, target allocation, intraday rules, portfolio ratio snapshot, market-position mapping, bucket registry, liquidity gate registry, decision log entries, and system checks. The export is generated in memory and does not write ZIP files into the repository.

## Validation

The ingest command runs:

- `python scripts/check_ratio_only.py --path <latest_index.modules.action_plan.path>`
- `python scripts/check_research_first_gate.py --path <latest_index.modules.action_plan.path>`
- `python scripts/check_cross_file_allocation_consistency.py`
- `python scripts/project_check.py --current-only`

Any failure blocks ingest.

The System Checks page also displays the sanitizer summary and table counts from the SQLite read model.
