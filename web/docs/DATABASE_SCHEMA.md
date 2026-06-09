# Web Database Schema

This document freezes the Phase 5A SQLite read model used by the read-only Web layer. The database is a current-only cache generated from `research/latest_index.json` `modules` pointers. It is not a trading database.

Database file:

```text
temp/web_db/myinvest.sqlite
```

The SQLite file must stay under `temp/web_db/` and must not be committed to Git. `artifacts.path` stores repository-relative paths only. No table may store local absolute paths.

## Ratio-Only Boundary

All tables are ratio-only. Forbidden portfolio-sensitive fields and values must not enter any table, API response, export payload, test fixture, or documentation example. Examples of blocked concepts include total assets, monetary values, market value, share count, available quantity, trade amount, profit amount, full account identifiers, order records, fill records, and local absolute paths.

Blocked identifier examples include:

```text
total_asset, amount, market_value, shares, quantity, available_quantity,
trade_amount, profit_amount, account, full_account, order, fill
```

`raw_json` columns are allowed only when the payload is first passed through `RatioOnlyService.safe_json(...)`. A failed sanitizer check blocks ingest.

## Current Pointer Tables

`current_modules` is the database form of `latest_index.modules`: one current pointer per module. Historical `latest_index.files` entries are not current-state inputs.

### artifacts

| Field | Type | Nullable | Meaning | Ratio-only safe | Source JSON field |
|---|---|---:|---|---|---|
| id | INTEGER | no | Internal primary key. | yes | generated |
| module | VARCHAR | no | Module name from `latest_index.modules.<module>.module`. | yes | `module` |
| subject_code | VARCHAR | yes | Optional subject code from the module pointer. | yes | `code` |
| artifact_type | VARCHAR | yes | Import classification, usually the module name. | yes | module key |
| path | VARCHAR | no | Repository-relative artifact path. Absolute paths are forbidden. | yes | `path` |
| generated_at | VARCHAR | yes | Artifact generation timestamp. | yes | `generated_at` |
| basis_trade_date | VARCHAR | yes | Data basis date when available. | yes | `basis_trade_date` |
| sha256 | VARCHAR | yes | Artifact checksum from latest index. | yes | `sha256` |
| raw_json | TEXT | no | Sanitized metadata subset, not full sensitive source JSON. | yes, after sanitizer | sanitized module subset |
| is_current | BOOLEAN | no | Whether this artifact is a current module pointer. | yes | generated |

### current_modules

| Field | Type | Nullable | Meaning | Ratio-only safe | Source JSON field |
|---|---|---:|---|---|---|
| module | VARCHAR | no | Current module key. Primary key. | yes | `latest_index.modules` key |
| artifact_id | INTEGER | no | FK to `artifacts.id`. | yes | generated |
| updated_at | VARCHAR | no | Ingest timestamp. | yes | generated |

## Market Tables

### market_scores

| Field | Type | Nullable | Meaning | Ratio-only safe | Source JSON field |
|---|---|---:|---|---|---|
| id | INTEGER | no | Internal primary key. | yes | generated |
| score | FLOAT | yes | Market-position score. | yes | `summary.market_position_score` |
| state | VARCHAR | yes | Market state label. | yes | `summary.market_state` |
| basis_trade_date | VARCHAR | yes | Market-data basis date. | yes | `basis_trade_date` |
| generated_at | VARCHAR | yes | Source artifact timestamp. | yes | `generated_at` |
| equity_min_pct | FLOAT | yes | Recommended equity lower bound. | yes | parsed from `summary.equity_allocation_range` |
| equity_max_pct | FLOAT | yes | Recommended equity upper bound. | yes | parsed from `summary.equity_allocation_range` |
| cash_min_pct | FLOAT | yes | Recommended cash/short-duration lower bound. | yes | parsed from `summary.bond_cash_allocation_range` |
| cash_max_pct | FLOAT | yes | Recommended cash/short-duration upper bound. | yes | parsed from `summary.bond_cash_allocation_range` |
| raw_json | TEXT | no | Sanitized market-score subset. | yes, after sanitizer | sanitized summary subset |

### market_position_mappings

| Field | Type | Nullable | Meaning | Ratio-only safe | Source JSON field |
|---|---|---:|---|---|---|
| id | INTEGER | no | Internal primary key. | yes | generated |
| score_min | FLOAT | yes | Mapping score lower bound. | yes | `score_min` |
| score_max | FLOAT | yes | Mapping score upper bound. | yes | `score_max` |
| equity_min_pct | FLOAT | yes | Equity lower bound for the score band. | yes | `equity_min_pct` |
| equity_max_pct | FLOAT | yes | Equity upper bound for the score band. | yes | `equity_max_pct` |
| cash_min_pct | FLOAT | yes | Cash/short-duration lower bound. | yes | `cash_min_pct` |
| cash_max_pct | FLOAT | yes | Cash/short-duration upper bound. | yes | `cash_max_pct` |
| label | VARCHAR | yes | Human-readable score-band label. | yes | `label` |
| is_active | BOOLEAN | no | Whether this mapping is active. | yes | generated/default |

## Subject And Gate Tables

### subjects

| Field | Type | Nullable | Meaning | Ratio-only safe | Source JSON field |
|---|---|---:|---|---|---|
| id | INTEGER | no | Internal primary key. | yes | generated |
| code | VARCHAR | yes | Security or bucket code. | yes | `code`, `ts_code` |
| name | VARCHAR | yes | Sanitized display name. | yes | `name` |
| subject_type | VARCHAR | yes | ETF, stock, bucket, or instrument type. | yes | `type` |
| exchange | VARCHAR | yes | Exchange suffix parsed from code. | yes | parsed |
| bucket | VARCHAR | yes | Ratio bucket role. | yes | `bucket_role`, `allocation_bucket`, `category` |
| status | VARCHAR | yes | Profile/research status label. | yes | `status` |

### profiles

| Field | Type | Nullable | Meaning | Ratio-only safe | Source JSON field |
|---|---|---:|---|---|---|
| id | INTEGER | no | Internal primary key. | yes | generated |
| subject_id | INTEGER | yes | FK to `subjects.id`. | yes | generated |
| status | VARCHAR | yes | Profile status. | yes | registry `status` |
| source_artifact_id | INTEGER | yes | FK to profile artifact. | yes | generated |
| generated_at | VARCHAR | yes | Profile generation timestamp. | yes | profile `generated_at` |
| basis_date | VARCHAR | yes | Profile basis date. | yes | `basis_trade_date`, `basis_date`, `date` |
| raw_json | TEXT | no | Sanitized profile subset. | yes, after sanitizer | sanitized profile metadata |

### valuations

| Field | Type | Nullable | Meaning | Ratio-only safe | Source JSON field |
|---|---|---:|---|---|---|
| id | INTEGER | no | Internal primary key. | yes | generated |
| subject_id | INTEGER | yes | FK to `subjects.id`. | yes | generated |
| valuation_status | VARCHAR | yes | Valuation gate status. | yes | liquidity registry `valuation_status` |
| valuation_source_artifact_id | INTEGER | yes | FK to valuation artifact. | yes | generated |
| generated_at | VARCHAR | yes | Valuation artifact timestamp. | yes | valuation `generated_at` |
| basis_date | VARCHAR | yes | Valuation basis date. | yes | `basis_trade_date`, `basis_date`, `date` |
| raw_json | TEXT | no | Sanitized valuation subset. | yes, after sanitizer | sanitized valuation metadata |

### liquidity_gates

| Field | Type | Nullable | Meaning | Ratio-only safe | Source JSON field |
|---|---|---:|---|---|---|
| id | INTEGER | no | Internal primary key. | yes | generated |
| subject_id | INTEGER | yes | FK to `subjects.id`. | yes | generated |
| liquidity_status | VARCHAR | yes | Liquidity gate status. | yes | `liquidity_status` |
| duration_boundary_confirmed | BOOLEAN | no | Cash/short-duration boundary gate. | yes | `duration_boundary_confirmed` |
| valuation_status | VARCHAR | yes | Valuation gate status. | yes | `valuation_status` |
| interest_rate_risk_disclosed | BOOLEAN | no | Rate-risk disclosure gate. | yes | `interest_rate_risk_disclosed` |
| credit_risk_disclosed | BOOLEAN | no | Credit-risk disclosure gate. | yes | `credit_risk_disclosed` |
| liquidity_risk_disclosed | BOOLEAN | no | Liquidity-risk disclosure gate. | yes | `liquidity_risk_disclosed` |
| source_profile_artifact_id | INTEGER | yes | FK to source profile artifact. | yes | `source_profile` |
| source_valuation_artifact_id | INTEGER | yes | FK to source valuation artifact. | yes | `valuation_source` |
| generated_at | VARCHAR | yes | Registry generation timestamp. | yes | registry `generated_at` |

## Portfolio Tables

### portfolio_snapshots

| Field | Type | Nullable | Meaning | Ratio-only safe | Source JSON field |
|---|---|---:|---|---|---|
| id | INTEGER | no | Internal primary key. | yes | generated |
| generated_at | VARCHAR | yes | Snapshot timestamp. | yes | `generated_at` |
| basis_trade_date | VARCHAR | yes | Snapshot date. | yes | `date` |
| privacy_policy | TEXT | yes | Ratio-only persistence note. | yes | generated |
| equity_pct | FLOAT | yes | Equity ratio. | yes | `summary.equity_weight_pct` |
| cash_short_pct | FLOAT | yes | Cash/short-duration ratio. | yes | `summary.bond_cash_weight_pct` |
| raw_json | TEXT | no | Sanitized ratio summary. | yes, after sanitizer | sanitized summary subset |

### portfolio_positions

| Field | Type | Nullable | Meaning | Ratio-only safe | Source JSON field |
|---|---|---:|---|---|---|
| id | INTEGER | no | Internal primary key. | yes | generated |
| snapshot_id | INTEGER | no | FK to `portfolio_snapshots.id`. | yes | generated |
| subject_id | INTEGER | yes | FK to `subjects.id`. | yes | generated |
| bucket | VARCHAR | yes | Bucket/category role. | yes | `allocation_bucket`, `category` |
| position_pct | FLOAT | yes | Position ratio. | yes | `weight_pct` |
| reference_only_flag | BOOLEAN | no | Marks snapshot as read-only reference. | yes | generated |

## Allocation Tables

### target_allocations

| Field | Type | Nullable | Meaning | Ratio-only safe | Source JSON field |
|---|---|---:|---|---|---|
| id | INTEGER | no | Internal primary key. | yes | generated |
| generated_at | VARCHAR | yes | Target allocation timestamp. | yes | `generated_at` |
| basis_trade_date | VARCHAR | yes | Basis date. | yes | `basis_trade_date` |
| market_score_id | INTEGER | yes | FK to `market_scores.id`. | yes | generated |
| equity_min_pct | FLOAT | yes | Recommended equity lower bound. | yes | parsed from `summary.recommended_equity_range` |
| equity_max_pct | FLOAT | yes | Recommended equity upper bound. | yes | parsed from `summary.recommended_equity_range` |
| cash_min_pct | FLOAT | yes | Recommended cash lower bound. | yes | parsed from `summary.recommended_bond_cash_range` |
| cash_max_pct | FLOAT | yes | Recommended cash upper bound. | yes | parsed from `summary.recommended_bond_cash_range` |
| raw_json | TEXT | no | Sanitized target allocation subset. | yes, after sanitizer | sanitized summary subset |

### bucket_allocations

| Field | Type | Nullable | Meaning | Ratio-only safe | Source JSON field |
|---|---|---:|---|---|---|
| id | INTEGER | no | Internal primary key. | yes | generated |
| target_allocation_id | INTEGER | no | FK to `target_allocations.id`. | yes | generated |
| bucket | VARCHAR | no | Bucket key. | yes | `actual_allocation_overlay.buckets[].key` |
| actual_pct | FLOAT | yes | Actual bucket ratio. | yes | `actual_pct` |
| target_pct | FLOAT | yes | Target bucket ratio. | yes | `target_pct` |
| gap_pct | FLOAT | yes | Actual minus target, in percentage points. | yes | `gap_pct` |

## Action Plan Tables

### action_plans

| Field | Type | Nullable | Meaning | Ratio-only safe | Source JSON field |
|---|---|---:|---|---|---|
| id | INTEGER | no | Internal primary key. | yes | generated |
| generated_at | VARCHAR | yes | Action plan timestamp. | yes | `generated_at` |
| basis_trade_date | VARCHAR | yes | Basis date. | yes | `basis_trade_date` |
| privacy_policy | TEXT | yes | Ratio-only persistence note. | yes | generated |
| market_state | VARCHAR | yes | Market state from preconditions when available. | yes | `preconditions.market_position.state` |
| status | VARCHAR | yes | Action plan status/recommendation strength. | yes | `summary.action_state` |
| raw_json | TEXT | no | Sanitized action-plan subset. | yes, after sanitizer | sanitized summary subset |

### action_items

| Field | Type | Nullable | Meaning | Ratio-only safe | Source JSON field |
|---|---|---:|---|---|---|
| id | INTEGER | no | Internal primary key. | yes | generated |
| action_plan_id | INTEGER | no | FK to `action_plans.id`. | yes | generated |
| sequence | INTEGER | no | Action sequence. | yes | generated |
| action_type | VARCHAR | yes | Ratio-only action type. | yes | `actions[].action_type` |
| subject_id | INTEGER | yes | FK to `subjects.id`. | yes | generated |
| bucket | VARCHAR | yes | Bucket role. | yes | `actions[].bucket_role` |
| current_position_pct | FLOAT | yes | Current ratio. | yes | parsed from `actions[].current_position` |
| target_range_min_pct | FLOAT | yes | Target range lower bound. | yes | parsed from `actions[].target_position` |
| target_range_max_pct | FLOAT | yes | Target range upper bound. | yes | parsed from `actions[].target_position` |
| suggested_change_min_pp | FLOAT | yes | Suggested ratio change lower bound. | yes | parsed from `actions[].suggested_change` |
| suggested_change_max_pp | FLOAT | yes | Suggested ratio change upper bound. | yes | parsed from `actions[].suggested_change` |
| reason | TEXT | yes | Sanitized evidence text. | yes | `actions[].evidence` |
| requires_manual_confirmation | BOOLEAN | no | Manual confirmation gate. | yes | `actions[].requires_manual_confirmation` |

### research_first_items

| Field | Type | Nullable | Meaning | Ratio-only safe | Source JSON field |
|---|---|---:|---|---|---|
| id | INTEGER | no | Internal primary key. | yes | generated |
| action_plan_id | INTEGER | yes | FK to `action_plans.id`. | yes | generated |
| subject_id | INTEGER | yes | FK to `subjects.id`. | yes | generated |
| missing_profile | BOOLEAN | no | Missing profile blocker. | yes | derived from `research_first_list[].blocking_reason` |
| missing_valuation | BOOLEAN | no | Missing valuation blocker. | yes | derived from blocker text |
| missing_liquidity | BOOLEAN | no | Missing liquidity blocker. | yes | derived from blocker text |
| missing_theme_binding | BOOLEAN | no | Missing theme-binding blocker. | yes | derived from blocker text |
| allowed_conclusion | VARCHAR | yes | Allowed conclusion, normally research-first only. | yes | generated |
| blocking_reason | TEXT | yes | Sanitized blocking reason. | yes | `research_first_list[].blocking_reason` |

## Intraday Tables

### intraday_rules

| Field | Type | Nullable | Meaning | Ratio-only safe | Source JSON field |
|---|---|---:|---|---|---|
| id | INTEGER | no | Internal primary key. | yes | generated |
| generated_at | VARCHAR | yes | Intraday rules timestamp. | yes | `generated_at` |
| basis_trade_date | VARCHAR | yes | Basis date when available. | yes | `basis_trade_date` |
| status | VARCHAR | yes | Staleness status. | yes | `staleness.status` |
| stale_flag | BOOLEAN | no | True when stale/blocked. | yes | derived |
| degraded_flag | BOOLEAN | no | True when degraded. | yes | derived |
| risk_mode | VARCHAR | yes | Global gate mode. | yes | `global_gate.default_market_gate` |
| raw_json | TEXT | no | Sanitized intraday subset and disabled triggers. | yes, after sanitizer | sanitized subset |

### intraday_bucket_rules

| Field | Type | Nullable | Meaning | Ratio-only safe | Source JSON field |
|---|---|---:|---|---|---|
| id | INTEGER | no | Internal primary key. | yes | generated |
| intraday_rules_id | INTEGER | no | FK to `intraday_rules.id`. | yes | generated |
| bucket | VARCHAR | no | Bucket key. | yes | `allocation_map.buckets[].key` |
| actual_pct | FLOAT | yes | Actual bucket ratio. | yes | `actual_pct` |
| target_pct | FLOAT | yes | Target bucket ratio. | yes | `target_pct` |
| gap_pct | FLOAT | yes | Actual minus target, in percentage points. | yes | `gap_pct` |

## Logs And Checks

### decision_log_entries

| Field | Type | Nullable | Meaning | Ratio-only safe | Source JSON field |
|---|---|---:|---|---|---|
| id | INTEGER | no | Internal primary key. | yes | generated |
| entry_time | VARCHAR | yes | Parsed entry date/time prefix. | yes | `research/logs/decision_log.md` line |
| entry_type | VARCHAR | yes | Entry type label. | yes | generated |
| related_action_plan_id | INTEGER | yes | FK to current action plan. | yes | generated |
| summary | TEXT | yes | Sanitized summary snippet. | yes | decision-log heading text |
| reason | TEXT | yes | Ingest reason. | yes | generated |
| ratio_only_text | TEXT | yes | Sanitized display text. | yes | decision-log heading text |
| raw_markdown | TEXT | yes | Sanitized heading snippet only. | yes | decision-log heading text |

### system_check_results

| Field | Type | Nullable | Meaning | Ratio-only safe | Source JSON field |
|---|---|---:|---|---|---|
| id | INTEGER | no | Internal primary key. | yes | generated |
| check_name | VARCHAR | no | Check identifier. | yes | generated |
| status | VARCHAR | no | `ok` or `fail`. | yes | check result |
| message | TEXT | yes | Sanitized check output snippet. | yes | check output |
| generated_at | VARCHAR | no | Ingest/check timestamp. | yes | generated |

## Shadow Services

Phase 5C-2 `TargetAllocationGenerationService` does not add tables. Its shadow output is computed in memory from the existing current SQLite read model and current module source paths. It must not insert rows, update `current_modules`, update `artifacts`, or write files under `research/allocation`.
