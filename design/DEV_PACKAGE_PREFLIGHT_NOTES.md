# MyInvest Developer Package Preflight Notes

Package: `MyInvest_dev_web_seed_2026-06-09_165947.zip`
Extracted directory: `/mnt/data/MyInvest_dev_web_seed_2026-06-09_165947_unzip`

## Summary

This developer seed package is sufficient for preparing Web requirements and architecture documents.
Before handing it to Codex for Web MVP implementation, fix the blocking package hygiene issues below.

## Observed current action plan

`research/latest_index.json` points to:

```text
research/actions/action_plan_2026-06-09_160249_latest_ratio_only.json
```

Do not hardcode `142000`; Web must always resolve current artifacts from `latest_index.modules`.

## Checks run in this environment

### Ratio-only

Command:

```bash
python scripts/check_ratio_only.py --path research/actions/action_plan_2026-06-09_160249_latest_ratio_only.json
```

Output:

```text
Ratio-only check: OK
File: research/actions/action_plan_2026-06-09_160249_latest_ratio_only.json
```

### ResearchFirst gate

Command:

```bash
python scripts/check_research_first_gate.py --path research/actions/action_plan_2026-06-09_160249_latest_ratio_only.json
```

Output:

```text
ResearchFirst gate: FAIL
File: research/actions/action_plan_2026-06-09_160249_latest_ratio_only.json
[FAIL] actions[1] add 511360 cash/short-duration bucket: cash-equivalent valuation source missing from registry
```

### Allocation consistency

Command:

```bash
python scripts/check_cross_file_allocation_consistency.py
```

Output:

```text
Allocation consistency: OK
{
  "target_allocation": "research/allocation/target_allocation_2026-06-09_150300.json",
  "intraday_rules": "research/alerts/intraday_rules.json"
}
```

### Project check

Command:

```bash
python scripts/project_check.py --current-only
```

Output:

```text
MyInvest project check
Root: /mnt/data/MyInvest_dev_web_seed_2026-06-09_165947_unzip
Result: 2 FAIL, 5 WARN
[FAIL] .env.example is missing
[WARN] Python package baostock is not installed; run python -m pip install -r requirements.txt
[WARN] Python package fredapi is not installed; run python -m pip install -r requirements.txt
[WARN] Python package tushare is not installed; run python -m pip install -r requirements.txt
[WARN] Python package yfinance is not installed; run python -m pip install -r requirements.txt
[FAIL] ResearchFirst gate failed: ResearchFirst gate: FAIL; File: research/actions/action_plan_2026-06-09_160249_latest_ratio_only.json; [FAIL] actions[1] add 511360 cash/short-duration bucket: cash-equivalent valuation source missing from registry
[WARN] research/alerts/intraday_rules.json is stale/degraded; run scripts/check_staleness.py and rebuild downstream rules before buy/add use
```

## Blocking issues to fix before Codex Web MVP

### 1. `liquidity_gate_registry.json` valuation source points to a missing file

Current registry points to:

```text
research/valuations/valuation_511360_SH_短融ETF海富通_2026-06-05_103909.json
```

This file is not present in the package.

Package contains:

```text
research/valuations/valuation_511360_SH_短融ETF海富通_2026-06-09_153822.json
research/valuations/valuation_511360_SH_短融ETF海富通_2026-06-09_163552.json
```

Fix either by:

- updating `valuation_source` to an included valuation file, or
- adding the missing `2026-06-05_103909` valuation file to the developer package.

### 2. `DEV_PACKAGE_MANIFEST.md` still emphasizes `142000` action plan

`latest_index.modules.action_plan.path` points to `research/actions/action_plan_2026-06-09_160249_latest_ratio_only.json`, but manifest required evidence still mentions `142000`.

Fix by making manifest say:

```text
Current action plan is resolved from research/latest_index.json modules.action_plan.path.
```

### 3. `.env.example` is missing

`project_check.py --current-only` fails with:

```text
.env.example is missing
```

Developer package should contain `.env.example` with empty placeholders only.

## Non-blocking observations

- No local absolute path hits were found in text scan.
- No `.env`, `runtime/`, `temp/`, `*.zip`, `*.db`, `*.sqlite`, `*.log`, `__pycache__/`, `.pytest_cache/` were found inside the package.
- `latest_index.generated_at` is not earlier than current module pointers.
