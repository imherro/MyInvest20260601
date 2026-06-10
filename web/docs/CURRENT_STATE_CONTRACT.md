# Current State Contract

Phase 5A freezes how the Web read model resolves current research state. The Web layer is read-only and current-only. It does not generate trades, orders, fills, share counts, or cash amounts.

## Resolver Rule

Current state starts at:

```text
research/latest_index.json
```

Only `latest_index.modules` is a valid current-state resolver. `latest_index.files` is historical inventory and must not be used to decide current Web state.

Every module path must be:

- repository-relative
- inside the repository root
- present on disk
- read with UTF-8 tolerant handling
- sanitized through the ratio-only boundary before storage or response

If a module pointer is missing, invalid, absolute, or escapes the repository root, ingest must fail.

## Module To Table Mapping

| Module | Source | Tables populated |
|---|---|---|
| `action_plan` | current action plan JSON | `artifacts`, `current_modules`, `action_plans`, `action_items`, `research_first_items`, `subjects`, `system_check_results` |
| `target_allocation` | current target allocation JSON | `artifacts`, `current_modules`, `target_allocations`, `bucket_allocations` |
| `intraday_rules` | current intraday rules JSON | `artifacts`, `current_modules`, `intraday_rules`, `intraday_bucket_rules` |
| `portfolio_snapshot` | current ratio-only snapshot JSON | `artifacts`, `current_modules`, `portfolio_snapshots`, `portfolio_positions`, `subjects` |
| `market_score` | current market score JSON | `artifacts`, `current_modules`, `market_scores` |
| `market_position_mapping` | current mapping config JSON | `artifacts`, `current_modules`, `market_position_mappings` |
| `bucket_registry` | current bucket registry JSON | `artifacts`, `current_modules`; exported as sanitized current source JSON |
| `liquidity_gate_registry` | current gate registry JSON | `artifacts`, `current_modules`, `liquidity_gates`, `profiles`, `valuations`, `subjects` |
| `etf_registry` | current ETF registry JSON | `artifacts`, `current_modules`; supports 511360 profile/valuation lookup |
| `decision_log.md` | durable decision log | `decision_log_entries` |

Other modules in `latest_index.modules` are stored in `artifacts` and `current_modules` as current pointers but do not necessarily populate a specialized table.

## Action Plan Split

The `action_plan` module is split as follows:

- `action_plans`: one current plan row with `generated_at`, `basis_trade_date`, market status, and sanitized summary.
- `action_items`: one row per `actions[]` item. Only ratios, target ranges, percentage-point changes, action type, bucket, reason, and manual-confirmation flag are persisted.
- `research_first_items`: one row per `research_first_list[]` item. The row captures missing profile, valuation, liquidity, theme-binding flags, allowed conclusion, and blocking reason.
- `subjects`: one row per referenced subject code/name/type/bucket.

No amount, share count, account, order, fill, or local absolute path may be persisted.

## Target Allocation Split

The `target_allocation` module is split as follows:

- `target_allocations`: one current allocation row with `generated_at`, `basis_trade_date`, market-score FK, equity range, and cash/short-duration range.
- `bucket_allocations`: one row per `actual_allocation_overlay.buckets[]` item, storing bucket key, `actual_pct`, `target_pct`, and `gap_pct`.

The bucket rows are the golden source for Dashboard gap visualization and intraday consistency checks.

## Intraday Rules Split

The `intraday_rules` module is split as follows:

- `intraday_rules`: one current rules row with generated time, staleness status, stale/degraded flags, and global risk mode.
- `intraday_bucket_rules`: one row per `allocation_map.buckets[]` item, storing bucket key, `actual_pct`, `target_pct`, and `gap_pct`.

Target allocation bucket rows and intraday bucket rows must match within the accepted rounding tolerance. If they do not match, ingest must fail through the allocation-consistency gate.

## Portfolio Snapshot Split

The `portfolio_snapshot` module remains ratio-only:

- `portfolio_snapshots`: stores only generated time, basis date, equity ratio, cash/short-duration ratio, and sanitized summary metadata.
- `portfolio_positions`: stores subject reference, bucket, ratio, and `reference_only_flag`.

The source snapshot may contain fields excluded from Web storage. The Web database must store only sanitized ratio fields.

## Liquidity Gate Registry Mapping

The current `liquidity_gate_registry` module maps instrument gates into `liquidity_gates`.

For 511360 cash/short-duration handling, the DB contract requires:

- `liquidity_status = pass`
- `valuation_status = pass`
- source profile artifact present
- source valuation artifact present
- duration boundary confirmed
- interest-rate risk disclosed
- credit risk disclosed
- liquidity risk disclosed

The source profile and valuation references are stored as repository-relative artifacts.

## Decision Log Mapping

`research/logs/decision_log.md` is parsed into recent `decision_log_entries`. The importer stores sanitized heading/snippet text only. Full logs, local paths, and sensitive runtime content must not be stored.

## Blocking Failures

Ingest must fail when any of the following occur:

- forbidden fields or forbidden text appear after sanitizer checks
- a source path is absolute or escapes the repository
- `latest_index.modules` lacks a required current module
- ResearchFirst gate fails
- target allocation and intraday bucket actual/target/gap values diverge beyond tolerance
- database verification finds unsafe `raw_json` or `raw_markdown`

The Web API and export package must also fail rather than return unsafe data.
