# AGENTS.md - MyInvest Project Instructions

## Project nature

MyInvest is a local A-share investment research and risk-control system. It is not an automatic trading system.

## Current repository mode

This repository remains the canonical MyInvest research project.
Web/DB development may be added under web/, but must not break existing research scripts, JSON/Markdown outputs, review packages, ResearchFirst gate, ratio-only boundary, or current-only audit logic.

## Hard boundaries

1. Current-only default
- Current state means research/latest_index.json modules.
- Do not treat latest_index.files as current effective files.
- Do not hardcode action plan timestamps.

2. ResearchFirst
- No single-security buy/add/reduce/sell may be produced unless profile, valuation, and liquidity gates pass.
- Cash/short-duration instruments must also pass profile, valuation, liquidity, duration boundary, interest-rate risk disclosure, credit risk disclosure, and liquidity risk disclosure.

3. Ratio-only privacy
- Research outputs, Web API responses, database rows, review packages, and developer packages must not contain total assets, monetary amount, market value, share count, available quantity, trade amount, profit amount, full account, local absolute paths, order records, or fill records.
- Allowed fields include ratios, percentage points, target ranges, action types, gate status, basis dates, generated_at, relative paths, and research blocking reasons.

4. No automatic trading
- Do not add QMT write/trading/order placement features unless explicitly requested.
- Execution runtime must remain local-only and excluded from Git/review packages.

5. Safety
- .env, runtime, temp, caches, archives, databases, logs outside research, credentials, and local absolute paths must not be committed or included in packages.
- Web database files must live under temp/web_db/ or another ignored directory.

## Required validation

After relevant changes, run:
- python scripts/check_ratio_only.py --path <latest_index.modules.action_plan.path>
- python scripts/check_research_first_gate.py --path <latest_index.modules.action_plan.path>
- python scripts/check_cross_file_allocation_consistency.py
- python scripts/project_check.py --current-only
- pytest for Web tests if Web code is changed

Any ResearchFirst or ratio-only violation is a blocking failure.
