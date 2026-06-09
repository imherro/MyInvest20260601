# Web Database Schema

The Web database is a read-only current-state cache generated from repository research artifacts.

Location:

```text
temp/web_db/myinvest_web.sqlite
```

Core tables:

- `artifacts`
- `current_modules`
- `market_scores`
- `market_position_mappings`
- `subjects`
- `profiles`
- `valuations`
- `liquidity_gates`
- `portfolio_snapshots`
- `portfolio_positions`
- `target_allocations`
- `bucket_allocations`
- `action_plans`
- `action_items`
- `research_first_items`
- `intraday_rules`
- `intraday_bucket_rules`
- `decision_log_entries`
- `system_check_results`

`raw_json` columns contain sanitized current-state subsets, not full source JSON.
