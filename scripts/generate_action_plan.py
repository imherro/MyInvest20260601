#!/usr/bin/env python3
"""Generate a ratio-only action plan from latest research artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from project_utils import ROOT, abs_path, file_sha256, latest_for_module, load_latest_index, pct_range, read_json, rel_path, write_json


ACTION_DIR = ROOT / "research" / "actions"
DECISION_LOG = ROOT / "research" / "logs" / "decision_log.md"
ETF_REGISTRY = ROOT / "research" / "etfs" / "etf_registry.json"
STOCK_REGISTRY = ROOT / "research" / "stocks" / "stock_registry.json"
INTRADAY_WATCHLIST = ROOT / "research" / "config" / "intraday_watchlist.json"


def dep_record(module: str, path: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "module": module,
        "path": path,
        "generated_at": data.get("generated_at"),
        "basis_trade_date": data.get("basis_trade_date") or data.get("date"),
        "sha256": file_sha256(abs_path(path)),
    }


def load_latest(module: str, index: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    record = latest_for_module(module, index)
    if not record:
        raise RuntimeError(f"missing latest module: {module}")
    path = record["path"]
    return path, read_json(abs_path(path), {})


def pp_range(low: float, high: float) -> str:
    return f"{low:.1f}pp to {high:.1f}pp"


def find_bucket(overlay: dict[str, Any], key: str) -> dict[str, Any]:
    for item in overlay.get("buckets", []):
        if item.get("key") == key:
            return item
    return {"key": key, "label": key, "target_pct": 0.0, "actual_pct": 0.0, "gap_pct": 0.0}


def normalize_code(value: Any) -> str:
    code = str(value or "").strip().upper()
    if not code:
        return ""
    if "." in code:
        return code
    if code.startswith(("0", "3")):
        return f"{code}.SZ"
    if code.startswith(("5", "6", "9")):
        return f"{code}.SH"
    return code


def current_holding_codes(portfolio: dict[str, Any]) -> set[str]:
    codes: set[str] = set()
    for item in portfolio.get("holdings", []) or []:
        for key in ["code", "ts_code"]:
            code = normalize_code(item.get(key))
            if code:
                codes.add(code)
                codes.add(code.split(".", 1)[0])
    return codes


def explicit_watch_codes() -> set[str]:
    data = read_json(INTRADAY_WATCHLIST, {})
    codes: set[str] = set()
    for item in data.get("include_codes", []) or []:
        code = normalize_code(item.get("code") if isinstance(item, dict) else item)
        if code:
            codes.add(code)
            codes.add(code.split(".", 1)[0])
    return codes


def registry_research_first(portfolio: dict[str, Any]) -> list[dict[str, str]]:
    eligible_codes = current_holding_codes(portfolio) | explicit_watch_codes()
    rows: list[dict[str, str]] = []
    for path, list_key, subject_type in [
        (ETF_REGISTRY, "etfs", "ETF"),
        (STOCK_REGISTRY, "stocks", "stock"),
    ]:
        data = read_json(path, {})
        for item in data.get(list_key, []):
            status = str(item.get("status") or "").lower()
            if status in {"to_research", "researchfirst", "research_first", "pending"}:
                code = item.get("code") or ""
                normalized = normalize_code(code)
                raw = normalized.split(".", 1)[0] if normalized else str(code)
                if normalized not in eligible_codes and raw not in eligible_codes:
                    continue
                name = item.get("name") or ""
                rows.append(
                    {
                        "subject": f"{code} {name}".strip(),
                        "subject_type": subject_type,
                        "missing_content": "fresh profile / valuation / liquidity / theme binding",
                        "why_it_blocks_action": "ResearchFirst gate: no direct buy/add/reduce/sell action before profile completion.",
                        "next_step": f"Generate or refresh {subject_type} dossier, then rebuild registry and action plan.",
                    }
                )
    return rows


def build_plan(index: dict[str, Any], generated_at: str) -> dict[str, Any]:
    market_path, market = load_latest("market_score", index)
    theme_path, theme = load_latest("theme_review", index)
    portfolio_path, portfolio = load_latest("portfolio_snapshot", index)
    allocation_path, allocation = load_latest("target_allocation", index)
    intraday_path, intraday = load_latest("intraday_rules", index)

    market_summary = market.get("summary") or {}
    alloc_summary = allocation.get("summary") or {}
    overlay = allocation.get("actual_allocation_overlay") or {}
    equity_range = alloc_summary.get("recommended_equity_range") or market_summary.get("equity_allocation_range") or "0%-0%"
    cash_range = alloc_summary.get("recommended_bond_cash_range") or market_summary.get("bond_cash_allocation_range") or "0%-0%"
    equity_low, equity_high = pct_range(equity_range)
    equity_center = round((equity_low + equity_high) / 2, 2)
    cash_low, cash_high = pct_range(cash_range)
    cash_center = round((cash_low + cash_high) / 2, 2)
    equity_actual = float(overlay.get("actual_equity_pct") or (portfolio.get("summary") or {}).get("equity_weight_pct") or 0)
    cash_actual = float(overlay.get("actual_cash_short_pct") or (portfolio.get("summary") or {}).get("bond_cash_weight_pct") or 0)
    reduce_to_high = max(0.0, equity_actual - equity_high)
    reduce_to_center = max(0.0, equity_actual - equity_center)
    cash_to_low = max(0.0, cash_low - cash_actual)
    cash_to_center = max(0.0, cash_center - cash_actual)
    legacy = find_bucket(overlay, "legacy_watch")
    attack = find_bucket(overlay, "attack_mainline")
    defense = find_bucket(overlay, "defense")

    deps = [
        dep_record("market_score", market_path, market),
        dep_record("theme_review", theme_path, theme),
        dep_record("portfolio_snapshot", portfolio_path, portfolio),
        dep_record("target_allocation", allocation_path, allocation),
        dep_record("intraday_rules", intraday_path, intraday),
    ]

    actions: list[dict[str, Any]] = []
    if reduce_to_high > 0:
        actions.append(
            {
                "priority": "high",
                "action_type": "Reduce",
                "subject": {"code": "", "name": "overall equity exposure", "type": "portfolio"},
                "bucket_role": "portfolio",
                "current_position": f"{equity_actual:.2f}%",
                "suggested_change": f"reduce {pp_range(reduce_to_high, reduce_to_center)}",
                "target_position": equity_range,
                "recommendation_strength": "Normal",
                "needs_manual_confirmation": True,
                "evidence": [
                    f"market score {market_summary.get('market_position_score')} maps to equity {equity_range}",
                    "actual equity is above target upper bound",
                    "offensive add gate is not open",
                ],
                "trigger_conditions": ["manual confirmation and no newer upstream file"],
                "invalidation_conditions": ["new market score raises equity target above current exposure"],
                "risks": ["do not convert risk-reduction output into a single-name forced sell list without dossier checks"],
                "review_points": ["rebuild portfolio snapshot after execution"],
            }
        )
    if cash_to_low > 0:
        actions.append(
            {
                "priority": "high",
                "action_type": "Add",
                "subject": {"code": "511360", "name": "cash/short-duration bucket", "type": "bond_cash"},
                "bucket_role": "cash_short",
                "current_position": f"{cash_actual:.2f}%",
                "suggested_change": f"increase {pp_range(cash_to_low, cash_to_center)}",
                "target_position": cash_range,
                "recommendation_strength": "Normal",
                "needs_manual_confirmation": True,
                "evidence": [
                    f"cash/short-duration target is {cash_range}",
                    "this is risk-reduction parking, not equity add exposure",
                ],
                "trigger_conditions": ["paired with equity-risk reduction"],
                "invalidation_conditions": ["new target allocation lowers cash/short-duration target"],
                "risks": ["confirm liquidity and short-duration instrument boundary"],
                "review_points": ["cash/short-duration ratio returns to target range"],
            }
        )
    if float(legacy.get("actual_pct") or 0) > float(legacy.get("target_pct") or 0):
        actions.append(
            {
                "priority": "high",
                "action_type": "Reduce",
                "subject": {"code": "", "name": legacy.get("label") or "legacy/watch bucket", "type": "bucket"},
                "bucket_role": "legacy_watch",
                "current_position": f"{float(legacy.get('actual_pct') or 0):.2f}%",
                "suggested_change": "reduce in stages before considering core adds",
                "target_position": f"{float(legacy.get('target_pct') or 0):.2f}%",
                "recommendation_strength": "Normal",
                "needs_manual_confirmation": True,
                "evidence": ["legacy/watch target is zero or near zero in target allocation", "legacy/watch is a main source of equity deviation"],
                "trigger_conditions": ["profile/liquidity/manual review before single-name action"],
                "invalidation_conditions": ["bucket registry or theme registry explicitly promotes a holding to current core/attack/defense"],
                "risks": ["stage changes to avoid overreacting to short-term rebound"],
                "review_points": ["overall equity exposure after staged reduction"],
            }
        )

    no_action = [
        {
            "subject": "core_base bucket",
            "reason": "underweight is not an add signal while overall equity is above target",
            "watch_points": ["wait for market score or target range improvement"],
        },
        {
            "subject": "attack_mainline bucket",
            "reason": "offensive gate is controlled by market/theme status",
            "watch_points": [f"actual {float(attack.get('actual_pct') or 0):.2f}%", "no new attack exposure while pause_new"],
        },
        {
            "subject": "defense bucket",
            "reason": "defensive equity is still equity exposure",
            "watch_points": [f"actual {float(defense.get('actual_pct') or 0):.2f}%", "do not treat defense bucket as cash"],
        },
    ]

    quality = {"status": "ok", "warnings": []}
    for source in [portfolio, allocation, intraday]:
        q = source.get("quality") or {}
        for item in q.get("warnings", []):
            quality["warnings"].append(item.get("reason") if isinstance(item, dict) else str(item))
        staleness = source.get("staleness") or {}
        if staleness.get("status") in {"degraded", "stale", "blocked"}:
            quality["warnings"].append(f"{source.get('module', 'upstream')} staleness={staleness.get('status')}")
    if quality["warnings"]:
        quality["status"] = "warning"

    return {
        "module": "action_plan",
        "version": "ratio_only_v3_config_driven",
        "date": generated_at[:10],
        "generated_at": generated_at,
        "basis_trade_date": market.get("basis_trade_date"),
        "session": "latest_ratio_only",
        "privacy_policy": "ratio_only_no_monetary_values_no_unit_counts",
        "dependencies": {"required": deps, "policy": "Invalid if any required upstream is replaced by a newer file."},
        "source_files": {
            "market_position": market_path,
            "theme_registry": theme_path,
            "portfolio_analysis": portfolio_path,
            "target_allocation": allocation_path,
            "intraday_rules": intraday_path,
            "decision_log": rel_path(DECISION_LOG),
        },
        "summary": {
            "action_state": "actionable" if actions else "watch",
            "recommendation_strength": "Normal" if actions else "Watch",
            "one_line_conclusion": (
                f"Target equity is {equity_range}; actual equity is about {equity_actual:.2f}%. "
                f"Allowed actions are ratio-only risk reduction and cash/short-duration restoration; no direct single-name add is allowed without fresh dossiers."
            ),
        },
        "quality": quality,
        "staleness": {"status": "fresh", "checked_at": generated_at},
        "preconditions": {
            "market_position": {"conclusion": f"score {market_summary.get('market_position_score')} -> equity {equity_range}, cash {cash_range}", "impact": "risk reduction first"},
            "theme_rating": {"conclusion": "theme context read from latest theme_review", "impact": "no attack add unless theme and market gates recover"},
            "portfolio_deviation": {"conclusion": f"actual equity {equity_actual:.2f}%, cash/short-duration {cash_actual:.2f}%", "impact": "bucket deviations drive staged actions"},
            "hard_constraints": {"conclusion": "ratio-only and ResearchFirst profile/valuation/liquidity gates active", "impact": "unprofiled or liquidity-unverified holdings cannot receive direct actions"},
        },
        "actions": actions,
        "no_action_list": no_action,
        "research_first_list": registry_research_first(portfolio),
        "intraday_triggers": [
            {
                "subject": "all buy/add triggers",
                "trigger_condition": "disabled while intraday rules are degraded or market offensive gate is pause_new",
                "action_after_trigger": "rebuild market_score, target_allocation, intraday_rules, then regenerate action_plan",
            }
        ],
        "risks": [
            "Registry or valuation staleness can only loosen actions after refresh.",
            "This file is ratio-only and must not be translated into monetary or unit instructions.",
        ],
        "triggered_hard_constraints": [
            "No monetary-value fields.",
            "No unit-count fields.",
            "No direct buy/add/reduce/sell for ResearchFirst subjects.",
            "Single-security executable actions require profile, valuation and liquidity gate pass.",
            "Cash/short-duration actions require liquidity, duration-boundary and interest-rate/credit/liquidity risk checks.",
        ],
        "comparison_with_previous": {
            "main_changes": ["action plan now reads target ranges from target_allocation instead of hardcoded bands"],
            "change_reasons": ["ChatGPT review found stale fixed-band assumptions in generator scripts"],
        },
        "decision_log_entry": (
            f"{generated_at[:10]} 操作建议刷新：按最新target_allocation读取权益{equity_range}、现金/短融{cash_range}；"
            f"当前权益约{equity_actual:.2f}%，仅允许比例级风险收缩和ResearchFirst门禁。"
        ),
    }


def render_markdown(plan: dict[str, Any]) -> str:
    action_rows = [
        f"| {item['priority']} | {item['action_type']} | {item['subject']['name']} | {item['current_position']} | {item['suggested_change']} | {item['target_position']} |"
        for item in plan["actions"]
    ]
    no_action_rows = [f"| {item['subject']} | {item['reason']} | {'; '.join(item.get('watch_points', []))} |" for item in plan["no_action_list"]]
    research_rows = [
        f"| {item['subject']} | {item['missing_content']} | {item['why_it_blocks_action']} | {item['next_step']} |"
        for item in plan["research_first_list"]
    ]
    return f"""# Ratio-Only Action Plan

Generated at: {plan['generated_at']}
Basis trade date: {plan.get('basis_trade_date')}

## Summary

{plan['summary']['one_line_conclusion']}

## Actions

| Priority | Action | Subject | Current | Suggested change | Target |
| --- | --- | --- | ---: | ---: | ---: |
{chr(10).join(action_rows) if action_rows else '| - | Watch | No direct action | - | - | - |'}

## No Action

| Subject | Reason | Watch points |
| --- | --- | --- |
{chr(10).join(no_action_rows)}

## ResearchFirst

| Subject | Missing content | Why blocked | Next step |
| --- | --- | --- | --- |
{chr(10).join(research_rows) if research_rows else '| - | none | no pending registry item | - |'}

## Hard Constraints

{chr(10).join(f"- {item}" for item in plan['triggered_hard_constraints'])}

## Risks

{chr(10).join(f"- {item}" for item in plan['risks'])}

## Sources

{chr(10).join(f"- `{item['path']}`" for item in plan['dependencies']['required'])}
"""


def write_plan(plan: dict[str, Any]) -> tuple[Path, Path]:
    timestamp = plan["generated_at"]
    json_path = ACTION_DIR / f"action_plan_{timestamp}_latest_ratio_only.json"
    md_path = ACTION_DIR / f"action_plan_{timestamp}_latest_ratio_only.md"
    write_json(json_path, plan)
    md_path.write_text(render_markdown(plan), encoding="utf-8")
    return md_path, json_path


def append_decision_log(entry: str, md_path: Path, json_path: Path, deps: list[dict[str, Any]]) -> None:
    lines = [
        "",
        f"## {entry}",
        f"- Markdown: `{rel_path(md_path)}`",
        f"- JSON: `{rel_path(json_path)}`",
        "- Dependencies:",
    ]
    lines.extend(f"  - `{item['path']}` generated_at={item.get('generated_at')} basis={item.get('basis_trade_date')}" for item in deps)
    DECISION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DECISION_LOG.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    parser.add_argument("--no-log", action="store_true", help="Do not append decision_log.md.")
    args = parser.parse_args(argv)
    index = load_latest_index()
    plan = build_plan(index, args.timestamp)
    md_path, json_path = write_plan(plan)
    if not args.no_log:
        append_decision_log(plan["decision_log_entry"], md_path, json_path, plan["dependencies"]["required"])
    print(json.dumps({"created": [rel_path(md_path), rel_path(json_path)], "logged": not args.no_log}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
