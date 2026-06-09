#!/usr/bin/env python3
"""Generate a post-market review scaffold from latest local research artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import check_valuation_updates
from project_utils import ROOT, abs_path, latest_for_module, load_latest_index, read_json, rel_path, write_json


OUTPUT_DIR = ROOT / "research" / "reviews"
DECISION_LOG = ROOT / "research" / "logs" / "decision_log.md"
RUNTIME_INTRADAY_ONCE = ROOT / "temp" / "runtime" / "alerts" / "intraday_once.json"


def latest_path(module: str, required: bool = True) -> str:
    record = latest_for_module(module, load_latest_index())
    if not record:
        if required:
            raise RuntimeError(f"missing latest module: {module}")
        return ""
    return str(record["path"])


def latest_intraday_alerts_for(date: str) -> list[str]:
    alert_dir = ROOT / "research" / "alerts"
    paths = sorted(alert_dir.glob(f"intraday_alert_{date}_*.json"), key=lambda p: p.stat().st_mtime)
    return [rel_path(path) for path in paths]


def load(path: str) -> dict[str, Any]:
    return read_json(abs_path(path), {}) if path else {}


def valuation_check_payload(basis_date: str, intraday_report: Path | None) -> dict[str, Any]:
    try:
        return check_valuation_updates.check_updates(basis_date, intraday_report, stale_days=1)
    except Exception as exc:  # noqa: BLE001
        return {
            "module": "valuation_update_check",
            "generated_at": datetime.now().strftime("%Y-%m-%d_%H%M%S"),
            "basis_date": basis_date,
            "scope": "latest_portfolio_and_intraday_rules",
            "update_required_count": None,
            "items": [],
            "summary": f"估值更新检查失败：{exc}",
            "error": str(exc),
        }


def action_reviews(action_plan: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for action in action_plan.get("actions", []):
        subject = action.get("subject") or {}
        rows.append(
            {
                "subject": subject.get("name") or subject.get("code") or "-",
                "premarket_suggestion": f"{action.get('action_type')} {action.get('suggested_change')}",
                "trigger_condition": "；".join(action.get("trigger_conditions", [])),
                "triggered": None,
                "executed": None,
                "result": "等待用户提供实际执行信息；未提供前不能假设已执行。",
                "bias": "execution_information_missing",
            }
        )
    return rows


def intraday_alert_reviews(alert_paths: list[str]) -> list[dict[str, Any]]:
    rows = []
    for path in alert_paths:
        alert = load(path)
        for item in alert.get("alerts", [])[:20]:
            subject = item.get("subject") or {}
            rows.append(
                {
                    "alert": f"{subject.get('code', '')} {subject.get('name', '')} {item.get('alert_type', '')}",
                    "trigger_state": item.get("current_state", ""),
                    "suggested_action": item.get("suggested_action", ""),
                    "actual_handling": "not_provided",
                    "was_useful": "partial",
                    "note": "盘后需由用户确认是否处理；脚本不假设执行结果。",
                }
            )
    return rows


def render_markdown(data: dict[str, Any]) -> str:
    action_rows = [
        "| {subject} | {suggestion} | {triggered} | {executed} | {result} |".format(
            subject=item["subject"],
            suggestion=item["premarket_suggestion"],
            triggered=item["trigger_condition"] or "-",
            executed=item["executed"],
            result=item["result"],
        )
        for item in data.get("action_plan_review", [])
    ]
    research_rows = [
        f"| {item['module_or_file']} | {item['needs_update']} | {item['priority']} | {item['reason']} |"
        for item in data.get("research_updates_needed", [])
    ]
    valuation_rows = [
        f"| {item.get('code')} | {item.get('name')} | {item.get('severity')} | {'；'.join(item.get('reasons', []))} |"
        for item in (data.get("valuation_update_check") or {}).get("items", [])
    ]
    return f"""# 盘后复盘

日期：{data['date']}
生成时间：{data['generated_at']}
类型：{data['review_type']}

## 1. 结论

{data['summary']['one_line_conclusion']}

| 项目 | 状态 |
| --- | --- |
| 复盘结论 | {data['summary']['review_conclusion']} |
| 是否需要研究更新 | {data['summary']['needs_research_update']} |
| 是否需要规则修正 | {data['summary']['needs_rule_revision']} |

## 2. 市场判断复盘

- 盘前判断：{data['market_review']['premarket_judgment']}
- 收盘表现：{data['market_review']['close_performance']}
- 偏差评估：{data['market_review']['bias_assessment']}
- 原因：{data['market_review']['reason']}

## 3. 操作计划复盘

| 对象 | 事前建议 | 条件触发 | 是否执行 | 结果 |
| --- | --- | --- | --- | --- |
{chr(10).join(action_rows) if action_rows else '| 无 | 无 | - | - | - |'}

## 4. 组合风险变化

- 权益仓变化：{data['portfolio_risk_changes']['equity_allocation_change']}
- 主题/行业集中：{data['portfolio_risk_changes']['theme_industry_concentration_change']}
- 单标的风险：{data['portfolio_risk_changes']['single_security_risk_change']}

## 5. 估值更新检查

检查命令：`{data['valuation_update_check']['command']}`

| 代码 | 名称 | 状态 | 原因 |
| --- | --- | --- | --- |
{chr(10).join(valuation_rows) if valuation_rows else '| 无 | 无 | ok | 无应更新项 |'}

## 6. 需要更新的研究

| 模块/文件 | 是否需要 | 优先级 | 原因 |
| --- | --- | --- | --- |
{chr(10).join(research_rows) if research_rows else '| 无 | false | low | 无 |'}

## 7. 明日观察

{chr(10).join(f"- {item}" for item in data.get('next_day_watch_points', []))}

## 8. 决策日志条目

```text
{data['decision_log_entry']}
```
"""


def build_review(review_type: str, execution_records: str, basis_date: str | None, intraday_report: Path | None) -> dict[str, Any]:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    date = timestamp[:10]
    market_path = latest_path("market_score")
    theme_path = latest_path("theme_review")
    action_path = latest_path("action_plan")
    portfolio_path = latest_path("portfolio_snapshot")
    premarket_path = latest_path("premarket_check", required=False) or "not_found"
    alert_paths = latest_intraday_alerts_for(date)
    market = load(market_path)
    theme = load(theme_path)
    action_plan = load(action_path)
    portfolio = load(portfolio_path)
    basis = basis_date or str(market.get("basis_trade_date") or date.replace("-", ""))
    valuation = valuation_check_payload(basis, intraday_report if intraday_report and intraday_report.exists() else None)
    valuation["command"] = "python scripts/check_valuation_updates.py --intraday-report temp/runtime/alerts/intraday_once.json"

    needs_valuation_update = bool(valuation.get("update_required_count"))
    needs_research_update = needs_valuation_update or execution_records == "not_provided"
    action_summary = (action_plan.get("summary") or {}).get("one_line_conclusion", "")
    portfolio_summary = portfolio.get("summary") or {}
    market_summary = market.get("summary") or {}
    theme_items = theme.get("themes", [])[:8]
    data = {
        "module": "post_market_review",
        "version": "1.1",
        "date": date,
        "generated_at": timestamp,
        "review_type": review_type,
        "ratio_only_policy": "no_sensitive_position_fields",
        "data_sources": {
            "market_position": market_path,
            "theme_research": theme_path,
            "action_plan": action_path,
            "intraday_alerts": alert_paths,
            "valuation_update_check": "inline_check_valuation_updates",
            "execution_records": execution_records,
            "portfolio_snapshot": portfolio_path,
            "premarket_check": premarket_path,
        },
        "summary": {
            "review_conclusion": "insufficient_information" if execution_records == "not_provided" else "partially_correct",
            "needs_research_update": needs_research_update,
            "needs_rule_revision": False,
            "one_line_conclusion": "已自动生成盘后复盘底稿；缺少实际执行记录时只做计划/规则/风险复盘，不假设已执行。",
        },
        "market_review": {
            "premarket_judgment": f"{market_summary.get('market_state', '')}; 权益目标 {market_summary.get('equity_allocation_range', '')}; {action_summary}",
            "close_performance": "未接入收盘行情自动拉取；本脚本只引用已落盘市场报告和盘中提醒。",
            "bias_assessment": "cannot_judge_close_bias_without_close_data",
            "reason": "需要盘后市场数据或用户确认后再判断市场预判偏差。",
        },
        "theme_review": [
            {
                "theme": item.get("name"),
                "premarket_rating": f"战略{item.get('strategic_rating')} / 交易{item.get('tactical_rating')} / {item.get('stage')}",
                "daily_performance": "not_loaded",
                "matched_expectation": "partial",
                "needs_update": False,
                "note": "未接入收盘主线表现前，不因单日主观印象修改评级。",
            }
            for item in theme_items
        ],
        "action_plan_review": action_reviews(action_plan),
        "intraday_alert_review": intraday_alert_reviews(alert_paths),
        "execution_review": {
            "actual_actions": [],
            "followed_plan": None,
            "execution_deviation": "未提供执行记录。",
            "improvement_needed": "盘后补充实际买卖和未执行原因后再做执行偏差判断。",
        },
        "portfolio_risk_changes": {
            "equity_allocation_change": f"最新快照权益约 {portfolio_summary.get('equity_weight_pct', '-')}%，目标由 action_plan/target_allocation 约束。",
            "theme_industry_concentration_change": "未生成盘后新持仓快照前，只能沿用最新快照。",
            "single_security_risk_change": "未发现自动化脚本可确认的新增单标的超限。",
            "hard_constraints_triggered": action_plan.get("triggered_hard_constraints", []),
        },
        "biases": [
            {
                "type": "missing_research" if execution_records == "not_provided" else "no_issue",
                "exists": execution_records == "not_provided",
                "description": "缺少实际执行记录，不能评价执行偏差。" if execution_records == "not_provided" else "未发现自动化可确认的问题。",
                "follow_up": "补充执行记录或刷新QMT快照。",
            }
        ],
        "research_updates_needed": [
            {
                "module_or_file": "valuation_report",
                "needs_update": needs_valuation_update,
                "reason": valuation.get("summary", ""),
                "priority": "high" if needs_valuation_update else "low",
            },
            {
                "module_or_file": "portfolio_snapshot",
                "needs_update": execution_records != "not_provided",
                "reason": "若今日有实际执行，应刷新QMT只读持仓快照。",
                "priority": "high" if execution_records != "not_provided" else "medium",
            },
        ],
        "valuation_update_check": valuation,
        "next_day_watch_points": [
            "权益仓是否仍高于45%。",
            "现金/短融是否回到55%-60%。",
            "legacy_watch 是否按操作建议进入第一阶段清理。",
            "市场门禁是否从 verify_only/risk_reduce_only 改善到允许新增风险。",
        ],
        "rule_revision_suggestion": {
            "suggested": False,
            "reason": "本次为自动底稿，不因单日结果修改规则。",
            "files_to_update": [],
        },
    }
    data["decision_log_entry"] = (
        f"{date} 盘后复盘自动底稿：生成 post_market_review_{timestamp}.md/json；"
        f"读取最新 market/theme/action/portfolio/alerts，并运行估值更新检查；缺少执行记录时不判断已执行。"
    )
    return data


def write_review(data: dict[str, Any], append_log: bool) -> tuple[Path, Path]:
    timestamp = data["generated_at"]
    json_path = OUTPUT_DIR / f"post_market_review_{timestamp}.json"
    md_path = OUTPUT_DIR / f"post_market_review_{timestamp}.md"
    write_json(json_path, data)
    md_path.write_text(render_markdown(data), encoding="utf-8")
    if append_log:
        DECISION_LOG.parent.mkdir(parents=True, exist_ok=True)
        with DECISION_LOG.open("a", encoding="utf-8") as handle:
            handle.write("\n" + data["decision_log_entry"] + "\n")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-type", default="daily_brief", choices=["daily_brief", "full_daily", "weekly", "event_driven", "rule_review"])
    parser.add_argument("--execution-records", default="not_provided")
    parser.add_argument("--basis-date", help="Valuation check basis date in YYYYMMDD.")
    parser.add_argument("--intraday-report", type=Path, default=RUNTIME_INTRADAY_ONCE)
    parser.add_argument("--no-log", action="store_true")
    args = parser.parse_args(argv)
    data = build_review(args.review_type, args.execution_records, args.basis_date, args.intraday_report)
    md_path, json_path = write_review(data, append_log=not args.no_log)
    print(json.dumps({"created": [rel_path(md_path), rel_path(json_path)], "valuation_updates": data["valuation_update_check"].get("update_required_count")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
