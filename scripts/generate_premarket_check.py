#!/usr/bin/env python3
"""Generate a ratio-only premarket execution check."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import check_valuation_updates
from project_utils import ROOT, abs_path, latest_for_module, load_latest_index, read_json, rel_path, write_json


CHECK_DIR = ROOT / "research" / "checks"
DECISION_LOG = ROOT / "research" / "logs" / "decision_log.md"


def latest_path(module: str, required: bool = True) -> str:
    record = latest_for_module(module, load_latest_index())
    if not record:
        if required:
            raise RuntimeError(f"missing latest module: {module}")
        return ""
    return str(record["path"])


def load(path: str) -> dict[str, Any]:
    return read_json(abs_path(path), {}) if path else {}


def gate_pass(value: bool, note: str) -> dict[str, Any]:
    return {"pass": bool(value), "note": note}


def build_check(timestamp: str, basis_date: str | None, intraday_report: Path | None, stale_days: int) -> dict[str, Any]:
    market_path = latest_path("market_score")
    theme_path = latest_path("theme_review")
    portfolio_path = latest_path("portfolio_snapshot")
    action_path = latest_path("action_plan", required=False)
    intraday_rules_path = latest_path("intraday_rules")
    market = load(market_path)
    theme = load(theme_path)
    portfolio = load(portfolio_path)
    action = load(action_path)
    rules = load(intraday_rules_path)
    basis = basis_date or str(market.get("basis_trade_date") or check_valuation_updates.latest_complete_trade_date())
    valuation = check_valuation_updates.check_updates(basis, intraday_report if intraday_report and intraday_report.exists() else None, stale_days)

    market_summary = market.get("summary") or {}
    portfolio_summary = portfolio.get("summary") or {}
    action_summary = action.get("summary") or {}
    rules_staleness = (rules.get("staleness") or {}).get("status", "legacy_unknown")
    research_first_count = len(action.get("research_first_list", []) or [])
    valuation_blocked = bool(valuation.get("blocking_for_new_actions"))
    equity_actual = portfolio_summary.get("equity_weight_pct")
    equity_target = market_summary.get("equity_allocation_range")
    offensive_status = market_summary.get("offensive_bucket_status")

    action_exists = bool(action_path)
    action_ok = action_exists and research_first_count == 0 and not valuation_blocked
    market_allows_add = offensive_status not in {"pause_new", "risk_reduce_only"}
    if valuation_blocked or rules_staleness in {"stale", "blocked", "degraded", "legacy_unknown"}:
        status = "risk_reduce_only"
    elif action_ok and market_allows_add:
        status = "executable"
    elif action_exists:
        status = "risk_reduce_only"
    else:
        status = "blocked"

    return {
        "module": "PREMARKET_CHECK",
        "version": "v1.1",
        "date": timestamp[:10],
        "session": "premarket",
        "generated_at": timestamp,
        "status": status,
        "conclusion": (
            "盘前执行检查已完成；估值更新检查只作为数据质量门禁，不生成交易动作。"
            if not valuation_blocked
            else "存在估值缺失、过期或盘中跨区项；新增单标的动作前应先确认是否刷新估值报告。"
        ),
        "read_files": {
            "daily_process": "docs/DAILY_PROCESS.md",
            "market_position": market_path,
            "theme_review": theme_path,
            "portfolio_snapshot": portfolio_path,
            "action_plan": action_path or "not_found",
            "intraday_rules": intraday_rules_path,
            "valuation_update_check": "inline:scripts/check_valuation_updates.py",
        },
        "gates": {
            "market_position": gate_pass(bool(equity_target), f"target_equity={equity_target}; offensive={offensive_status}"),
            "portfolio": gate_pass(equity_actual is not None, f"actual_equity={equity_actual}%"),
            "action_plan": gate_pass(action_ok, f"exists={action_exists}; research_first={research_first_count}; state={action_summary.get('action_state')}"),
            "intraday_rules": gate_pass(rules_staleness == "fresh", f"staleness={rules_staleness}"),
            "valuation": gate_pass(not valuation_blocked, valuation.get("summary", "")),
        },
        "allowed_actions": [
            "只按最新 action_plan 和 intraday_rules 检查已定义条件。",
            "估值更新提示只作为数据质量门禁；未刷新前不得把旧估值状态当作当前结论。",
            "市场门禁未允许新增风险时，只允许风险收缩或观察。",
        ],
        "forbidden": [
            "不得使用金额、股数、总资产、市值或盈亏金额。",
            "不得临时改写市场仓位、主线评级或盘中触发条件。",
            "不得把估值缺失或过期标的转成直接买卖动作。",
        ],
        "intraday_monitoring": [
            {
                "subject": "valuation_update_check",
                "trigger_condition": "update_required_count > 0",
                "action_after_trigger": "ask whether to refresh valuation reports",
                "needs_manual_confirmation": True,
            },
            {
                "subject": "intraday_rules",
                "trigger_condition": "staleness is not fresh",
                "action_after_trigger": "blocked for buy/add; risk-reduction review only",
                "needs_manual_confirmation": True,
            },
        ],
        "research_first": action.get("research_first_list", []) or [],
        "valuation_update_check": valuation,
        "handoff": {
            "intraday": "Use research/alerts/intraday_rules.json plus valuation_update_check as a data-quality overlay.",
            "post_market": "Re-run valuation_update_check and record whether stale/missing/cross-zone items were refreshed.",
        },
        "decision_log_entry": (
            f"{timestamp} premarket_check: status={status}; valuation_updates={valuation.get('update_required_count')}; "
            "ratio-only; no single-security operation instruction."
        ),
    }


def render_markdown(data: dict[str, Any]) -> str:
    valuation_rows = [
        "| Code | Name | Severity | Reasons |",
        "| --- | --- | --- | --- |",
    ]
    for item in (data.get("valuation_update_check") or {}).get("items", []):
        valuation_rows.append(
            f"| {item.get('code')} | {item.get('name')} | {item.get('severity')} | {'; '.join(item.get('reasons', []))} |"
        )
    if len(valuation_rows) == 2:
        valuation_rows.append("| - | - | ok | 无 |")
    gate_rows = [
        "| Gate | Pass | Note |",
        "| --- | --- | --- |",
    ]
    for key, gate in data.get("gates", {}).items():
        gate_rows.append(f"| {key} | {gate.get('pass')} | {gate.get('note')} |")
    return f"""# Premarket Execution Check

Generated at: {data['generated_at']}
Status: {data['status']}

{data['conclusion']}

## Gates

{chr(10).join(gate_rows)}

## Valuation Update Check

{data['valuation_update_check']['summary']}

{chr(10).join(valuation_rows)}

## Allowed

{chr(10).join(f"- {item}" for item in data['allowed_actions'])}

## Forbidden

{chr(10).join(f"- {item}" for item in data['forbidden'])}

## Boundary

Ratio-only execution gate only. No buy, sell, add, or reduce instruction is generated here.
"""


def append_decision_log(data: dict[str, Any], md_path: Path, json_path: Path) -> None:
    DECISION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DECISION_LOG.open("a", encoding="utf-8") as handle:
        handle.write(
            "\n"
            + data["decision_log_entry"]
            + f"\n- Markdown: `{rel_path(md_path)}`\n- JSON: `{rel_path(json_path)}`\n"
        )


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    parser.add_argument("--basis-date")
    parser.add_argument("--intraday-report", type=Path)
    parser.add_argument("--stale-days", type=int, default=1)
    parser.add_argument("--no-log", action="store_true")
    args = parser.parse_args(argv)
    data = build_check(args.timestamp, args.basis_date, args.intraday_report, args.stale_days)
    json_path = CHECK_DIR / f"premarket_check_{args.timestamp}.json"
    md_path = CHECK_DIR / f"premarket_check_{args.timestamp}.md"
    write_json(json_path, data)
    md_path.write_text(render_markdown(data), encoding="utf-8")
    if not args.no_log:
        append_decision_log(data, md_path, json_path)
    print(json.dumps({"created": [rel_path(md_path), rel_path(json_path)], "status": data["status"], "valuation_updates": data["valuation_update_check"].get("update_required_count")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
