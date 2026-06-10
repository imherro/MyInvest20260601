# Theme Research Center

Phase 7E adds a read-only Theme Research Center for Web review.

## Scope

The center reads current SQLite artifact payloads loaded from `research/latest_index.json` `modules`:

- `theme_registry`
- `theme_leaders`
- `etf_registry`
- `stock_registry`

It may join subject gate status from the current SQLite read model. It must not read `latest_index.files` as a current resolver.

## Boundaries

The Theme Research Center is not a trading page. Theme states are research visibility states only:

- `confirmed`
- `watch`
- `research_first`
- `stale`
- `conflict`
- `unknown`

These states must not become buy/add/reduce/sell actions. Missing profile, valuation, or liquidity evidence for associated subjects remains a ResearchFirst concern.

## API

- `GET /api/themes/status`
- `GET /api/themes/status/{theme_name}`

Responses are current-only and ratio-only. They include summary counts, theme rows, associated ETF/stock gate summaries, leaders, conflicts, and safety flags.

## Page

- `GET /themes`

The page supports refresh, search, status/rating/stage filters, sorting, pagination, and expandable details. It uses the shared frontend sanitizer before rendering refreshed API data.

## Safety

The center must not:

- write research files
- update `latest_index`
- update `current_modules`
- generate target allocation
- generate action plans
- add trading, execution, or QMT write behavior
- expose local absolute paths
- expose account, order, fill, cash, or share data

## Validation

Run:

```bash
python scripts/ingest_current_state.py
python -m pytest web/backend/tests/test_theme_status.py
python scripts/web_check.py
```
