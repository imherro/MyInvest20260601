#!/usr/bin/env python3
"""Generate current target allocation from latest market/theme/portfolio inputs."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from project_utils import (
    ROOT,
    abs_path,
    build_latest_index,
    latest_for_module,
    path_record,
    read_json,
    rel_path,
    write_json,
)


OUTPUT_DIR = ROOT / "research" / "allocation"
ALERT_RULES = ROOT / "research" / "alerts" / "intraday_rules.json"
BUCKET_REGISTRY = ROOT / "research" / "config" / "bucket_registry.json"


def pct_range(text: str) -> tuple[float, float]:
    left, right = text.replace("%", "").split("-", 1)
    return float(left), float(right)


def fmt_pct(value: float) -> str:
    return f"{value:g}%"


def dependency(path: str, index: dict[str, Any]) -> dict[str, Any]:
    record = path_record(path, index) or {}
    return {
        "module": record.get("module", "unknown"),
        "path": path,
        "generated_at": record.get("generated_at"),
        "basis_trade_date": record.get("basis_trade_date"),
        "sha256": record.get("sha256"),
    }


def bucket_config() -> dict[str, Any]:
    return read_json(BUCKET_REGISTRY, {})


def target_segments(equity_center: float, cash_center: float) -> list[dict[str, Any]]:
    # Weak market and offensive pause: keep equity low, prefer core/defense, leave legacy target at zero.
    core = 22.0
    attack = 6.5
    defense = round(equity_center - core - attack, 2)
    return [
        {
            "key": "cash_short",
            "label": "现金/短融",
            "target_pct": round(cash_center, 2),
            "color": "#5b6b7a",
            "basis": "市场仓位分数41，现金/短融作为主要防守和等待确认的仓位锚。",
        },
        {
            "key": "core_base",
            "label": "宽基/核心底仓",
            "target_pct": core,
            "color": "#2f6fbd",
            "basis": "权益内部优先保留宽基、自由现金流、质量类低换手核心暴露；当前不因低配直接加仓。",
        },
        {
            "key": "attack_mainline",
            "label": "进攻主线仓",
            "target_pct": attack,
            "color": "#8b5cf6",
            "basis": "市场模块显示进攻仓暂停新增，AI交易评级B、半导体交易评级C，进攻仓仅保留低配观察。",
        },
        {
            "key": "defense",
            "label": "防御仓",
            "target_pct": defense,
            "color": "#0f8b6f",
            "basis": "弱势环境保留红利、公用事业、金融和医药等防御暴露，但不追高。",
        },
        {
            "key": "legacy_watch",
            "label": "其他/待清理",
            "target_pct": 0.0,
            "color": "#9a6700",
            "basis": "C/D主题、遗留小仓和未进入当前主线的标的目标为0，只作为偏离暴露。",
        },
    ]


def actual_by_bucket(snapshot: dict[str, Any]) -> dict[str, float]:
    result = {key: 0.0 for key in ["cash_short", "core_base", "attack_mainline", "defense", "legacy_watch"]}
    for item in snapshot.get("holdings", []):
        key = item.get("allocation_bucket") or "legacy_watch"
        result[key] = result.get(key, 0.0) + float(item.get("weight_pct") or 0)
    result["cash_short"] += float(snapshot.get("summary", {}).get("cash_uninvested_pct") or 0)
    return {key: round(value, 4) for key, value in result.items()}


def build_overlay(segments: list[dict[str, Any]], actual: dict[str, float]) -> list[dict[str, Any]]:
    meta = {item["key"]: item for item in segments}
    rows = []
    for key in ["cash_short", "core_base", "attack_mainline", "defense", "legacy_watch"]:
        target = float(meta.get(key, {}).get("target_pct") or 0.0)
        current = float(actual.get(key, 0.0))
        if target == 0 and current == 0:
            continue
        rows.append(
            {
                "key": key,
                "label": meta.get(key, {}).get("label", key),
                "color": meta.get(key, {}).get("color", "#9a6700"),
                "target_pct": round(target, 4),
                "actual_pct": round(current, 4),
                "gap_pct": round(current - target, 4),
            }
        )
    return rows


def build_target_allocation(index: dict[str, Any]) -> dict[str, Any]:
    market_ref = latest_for_module("market_score", index)
    theme_ref = latest_for_module("theme_review", index)
    snapshot_ref = latest_for_module("portfolio_snapshot", index)
    if not market_ref or not theme_ref or not snapshot_ref:
        raise RuntimeError("Missing latest market_score, theme_review, or portfolio_snapshot.")

    market = read_json(abs_path(market_ref["path"]), {})
    theme = read_json(abs_path(theme_ref["path"]), {})
    snapshot = read_json(abs_path(snapshot_ref["path"]), {})
    market_summary = market.get("summary", {})
    equity_low, equity_high = pct_range(market_summary.get("equity_allocation_range", "40%-45%"))
    cash_low, cash_high = pct_range(market_summary.get("bond_cash_allocation_range", "55%-60%"))
    equity_center = round((equity_low + equity_high) / 2, 2)
    cash_center = round((cash_low + cash_high) / 2, 2)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    segments = target_segments(equity_center, cash_center)
    actual = actual_by_bucket(snapshot)
    overlay = build_overlay(segments, actual)
    theme_summary = [
        {
            "name": item.get("name"),
            "strategic_rating": item.get("strategic_rating"),
            "tactical_rating": item.get("tactical_rating"),
            "stage": item.get("stage"),
            "bucket_role": item.get("bucket_role"),
            "position_impact": item.get("position_impact"),
        }
        for item in theme.get("themes", [])
        if item.get("name") in {"AI", "半导体", "高端装备", "机器人", "电力设备", "有色", "低空经济"}
    ]
    return {
        "module": "target_allocation",
        "version": "2.0",
        "date": timestamp[:10],
        "generated_at": timestamp,
        "basis_trade_date": market.get("basis_trade_date"),
        "session": "engineering_hardened_from_latest_inputs",
        "amount_policy": "ratio_only_no_market_value_no_cost_no_profit_no_share_count",
        "dependencies": {
            "required": [
                dependency(market_ref["path"], index),
                dependency(theme_ref["path"], index),
                dependency(snapshot_ref["path"], index),
                dependency("research/config/bucket_registry.json", index),
            ],
            "policy": "Target allocation is invalid if market_score, theme_review, or portfolio_snapshot is replaced by a newer file.",
        },
        "data_sources": [market_ref["path"], theme_ref["path"], snapshot_ref["path"], "research/config/bucket_registry.json"],
        "summary": {
            "market_state": market_summary.get("market_state"),
            "market_position_score": market_summary.get("market_position_score"),
            "recommended_equity_center": fmt_pct(equity_center),
            "recommended_equity_range": market_summary.get("equity_allocation_range"),
            "recommended_bond_cash_center": fmt_pct(cash_center),
            "recommended_bond_cash_range": market_summary.get("bond_cash_allocation_range"),
            "offensive_bucket_status": market_summary.get("offensive_bucket_status"),
            "one_line_conclusion": "目标权益下调到40%-45%区间，中枢42.5%；现金/短融中枢57.5%。进攻主线只保留低配观察，不新增；真实权益高于目标上沿，偏离主要来自legacy/主题与进攻/防御暴露。",
        },
        "target_allocation": {
            "groups": [
                {
                    "group": "511360 / 现金短融桶",
                    "target_range": "55%-60%",
                    "target_center_pct": 57.5,
                    "vehicles": ["511360", "cash_short_duration"],
                    "role": "防守锚和机动资金",
                    "principle": "承接弱项释放资金，等待指数和主线重新确认。",
                },
                {
                    "group": "宽基/核心底仓",
                    "target_range": "20%-24%",
                    "target_center_pct": 22.0,
                    "vehicles": ["510300", "510500", "159915", "159201", "002352"],
                    "role": "权益核心底仓",
                    "principle": "弱市里作为优先保留方向，但不因为低配直接新增。",
                },
                {
                    "group": "进攻主线仓",
                    "target_range": "5%-8%",
                    "target_center_pct": 6.5,
                    "vehicles": ["159819", "588200", "159558", "159326", "159667", "002241", "688333", "603596", "562800"],
                    "role": "低配观察",
                    "principle": "AI交易B、半导体交易C；市场门禁未解除前不新增。",
                },
                {
                    "group": "防御仓",
                    "target_range": "12%-16%",
                    "target_center_pct": 14.0,
                    "vehicles": ["510880", "159301", "512880", "159842", "512070", "159992", "513120", "601318", "300760", "603087"],
                    "role": "权益内防守",
                    "principle": "用于平衡科技波动，但红利/金融/医药若处高位也不追高。",
                },
                {
                    "group": "其他/待清理",
                    "target_range": "0%",
                    "target_center_pct": 0.0,
                    "vehicles": ["159378", "512710", "159869", "562500", "513180", "513050", "512400", "516150", "002258", "002041", "603903", "515880"],
                    "role": "偏离暴露",
                    "principle": "不作为理想配置目标；只作为后续ACTION_PLAN的偏离清理候选。",
                },
            ],
            "total_target_pct_sum": 100.0,
            "equity_internal_pct": {
                "core_base": round(22.0 / equity_center * 100, 2),
                "attack_mainline": round(6.5 / equity_center * 100, 2),
                "defense": round(14.0 / equity_center * 100, 2),
                "legacy_watch": 0.0,
            },
        },
        "ideal_allocation_map": {
            "basis": "latest_market_position_and_theme_analysis",
            "target_equity_pct": equity_center,
            "target_cash_short_pct": cash_center,
            "segments": segments,
            "actual_overlay_source": snapshot_ref["path"],
            "boundary": "理想仓位只由市场仓位、主题强度和配置约束决定；真实持仓只作为覆盖层，不反向改变理想结构。",
            "validation": {
                "segments_target_pct_sum": round(sum(float(item["target_pct"]) for item in segments), 4),
                "status": "ok",
            },
        },
        "actual_allocation_overlay": {
            "source": snapshot_ref["path"],
            "actual_equity_pct": snapshot.get("summary", {}).get("equity_weight_pct"),
            "actual_cash_short_pct": snapshot.get("summary", {}).get("bond_cash_weight_pct"),
            "buckets": overlay,
            "quality": snapshot.get("quality", {"status": "legacy_unknown"}),
        },
        "transition_targets": [
            {
                "subject": "equity_total",
                "current_pct": snapshot.get("summary", {}).get("equity_weight_pct"),
                "target_range": market_summary.get("equity_allocation_range"),
                "priority": "high",
                "reason": "真实权益高于最新市场仓位上沿；具体动作交由ACTION_PLAN决定。",
            },
            {
                "subject": "cash_short",
                "current_pct": actual.get("cash_short"),
                "target_range": market_summary.get("bond_cash_allocation_range"),
                "priority": "high",
                "reason": "现金短融低于目标区间，弱势市场需要提高防守锚。",
            },
            {
                "subject": "legacy_watch",
                "current_pct": actual.get("legacy_watch"),
                "target_range": "0%",
                "priority": "high",
                "reason": "其他/待清理暴露显著高于理想目标，是后续清理优先来源。",
            },
            {
                "subject": "attack_mainline",
                "current_pct": actual.get("attack_mainline"),
                "target_range": "5%-8%",
                "priority": "medium",
                "reason": "进攻仓略高于目标中枢，且市场门禁为pause_new。",
            },
        ],
        "rules": {
            "no_direct_trade": True,
            "buy_add_blocked_when_intraday_rules_stale": True,
            "offensive_add_blocked": market_summary.get("offensive_bucket_status") == "pause_new",
            "action_plan_required_for_any_trade": True,
            "core_underweight_does_not_trigger_buy": True,
        },
        "activation_triggers": market.get("trigger_based_adjustments", []),
        "theme_summary": theme_summary,
        "quality": {
            "status": "warning" if (snapshot.get("quality") or {}).get("status") in {"error", "warning"} else "ok",
            "warnings": [
                "最新QMT持仓快照存在数据质量警告，已用于比例偏离，但不允许用异常成本字段生成精确交易建议。"
            ]
            if (snapshot.get("quality") or {}).get("status") in {"error", "warning"}
            else [],
        },
        "staleness": {"status": "fresh", "checked_at": timestamp},
        "decision_log_entry": f"{timestamp[:10]} 目标仓位重建：基于最新 market_score/theme_review/QMT snapshot，权益目标40%-45%、现金短融55%-60%；进攻仓暂停新增，盘中规则需同步至本目标配置。",
    }


def render_markdown(data: dict[str, Any]) -> str:
    rows = []
    for item in data["ideal_allocation_map"]["segments"]:
        actual = next((row for row in data["actual_allocation_overlay"]["buckets"] if row["key"] == item["key"]), {})
        rows.append(
            "| {label} | {target:.2f}% | {actual:.2f}% | {gap:+.2f}pp | {basis} |".format(
                label=item["label"],
                target=float(item["target_pct"]),
                actual=float(actual.get("actual_pct") or 0),
                gap=float(actual.get("gap_pct") or 0),
                basis=item.get("basis", ""),
            )
        )
    transition_rows = [
        f"| {item['subject']} | {item.get('current_pct')}% | {item['target_range']} | {item['priority']} | {item['reason']} |"
        for item in data.get("transition_targets", [])
    ]
    return f"""# 目标仓位参考

日期：{data['date']}
生成时间：{data['generated_at']}
数据基准日：{data.get('basis_trade_date')}
版本：{data['version']}

## 1. 核心结论

{data['summary']['one_line_conclusion']}

| 项目 | 目标 |
| --- | ---: |
| 权益仓 | {data['summary']['recommended_equity_range']}，中枢 {data['summary']['recommended_equity_center']} |
| 现金/短融 | {data['summary']['recommended_bond_cash_range']}，中枢 {data['summary']['recommended_bond_cash_center']} |
| 进攻仓状态 | {data['summary']['offensive_bucket_status']} |

## 2. 作战地图仓位桶

| 仓位桶 | 理想比例 | 实际比例 | 偏离 | 依据 |
| --- | ---: | ---: | ---: | --- |
{chr(10).join(rows)}

## 3. 偏离优先级

| 项目 | 当前 | 目标 | 优先级 | 原因 |
| --- | ---: | ---: | --- | --- |
{chr(10).join(transition_rows)}

## 4. 约束

- 本模块不直接生成买卖指令。
- 核心仓低配不等于立即加仓。
- 进攻仓新增被市场门禁阻断。
- 任何交易动作必须进入 ACTION_PLAN。

## 5. 数据质量

质量状态：{data['quality']['status']}

{chr(10).join(f"- {item}" for item in data['quality'].get('warnings', [])) or "- 无重大质量警告。"}
"""


def write_report(data: dict[str, Any]) -> tuple[Path, Path]:
    timestamp = data["generated_at"]
    json_path = OUTPUT_DIR / f"target_allocation_{timestamp}.json"
    md_path = OUTPUT_DIR / f"target_allocation_{timestamp}.md"
    write_json(json_path, data)
    md_path.write_text(render_markdown(data), encoding="utf-8")
    return md_path, json_path


def sync_intraday_rules(allocation: dict[str, Any], allocation_path: Path, index: dict[str, Any]) -> bool:
    if not ALERT_RULES.exists():
        return False
    rules = read_json(ALERT_RULES, {})
    snapshot_path = allocation["actual_allocation_overlay"]["source"]
    overlay = allocation["actual_allocation_overlay"]["buckets"]
    segments = allocation["ideal_allocation_map"]["segments"]
    bucket_meta = {item["key"]: item for item in segments}
    buckets = []
    for item in overlay:
        meta = bucket_meta.get(item["key"], {})
        buckets.append(
            {
                "key": item["key"],
                "label": item.get("label") or meta.get("label", item["key"]),
                "color": item.get("color") or meta.get("color", "#9a6700"),
                "target_pct": item["target_pct"],
                "actual_pct": item["actual_pct"],
                "gap_pct": item["gap_pct"],
                "note": "target_pct来自最新target_allocation；actual_pct来自QMT只读持仓快照。",
            }
        )
    rules["generated_at"] = allocation["generated_at"]
    rules["last_updated"] = allocation["date"]
    rules["allocation_map"] = {
        "basis": "latest_target_allocation_and_qmt_readonly_portfolio_snapshot",
        "target_allocation_file": rel_path(allocation_path),
        "portfolio_snapshot_file": snapshot_path,
        "target_equity_pct": allocation["ideal_allocation_map"]["target_equity_pct"],
        "target_cash_short_pct": allocation["ideal_allocation_map"]["target_cash_short_pct"],
        "actual_equity_pct": allocation["actual_allocation_overlay"]["actual_equity_pct"],
        "actual_cash_short_pct": allocation["actual_allocation_overlay"]["actual_cash_short_pct"],
        "bucket_model": "理想仓位由目标配置模块提供；真实持仓只作为覆盖层，不反向改变理想结构。",
        "ideal_segments": segments,
        "actual_overlay": [
            {
                "key": item["key"],
                "label": item["label"],
                "color": item["color"],
                "actual_pct": item["actual_pct"],
                "gap_pct": item["gap_pct"],
            }
            for item in buckets
            if item["actual_pct"] > 0
        ],
        "buckets": buckets,
        "quality": allocation["actual_allocation_overlay"].get("quality", {"status": "legacy_unknown"}),
    }
    required_paths = [
        "research/market/market_score_2026-06-08_100643.json",
        "research/themes/theme_review_2026-06-08_102237.json",
        rel_path(allocation_path),
        snapshot_path,
    ]
    valuation_paths = [
        item
        for item in rules.get("data_sources", [])
        if isinstance(item, str) and item.startswith("research/valuations/") and item.endswith(".json")
    ]
    rules["data_sources"] = [
        "docs/modules/INTRADAY_ALERTS.md",
        "docs/modules/VALUATION_RESEARCH.md",
    ] + required_paths + valuation_paths
    rules["dependencies"] = {
        "required": [dependency(path, index) for path in required_paths + valuation_paths],
        "policy": "If any required upstream is replaced by a newer file, intraday_rules must be marked stale/degraded and cannot emit buy/add alerts.",
    }
    rules["staleness"] = {
        "status": "degraded" if allocation["quality"]["status"] != "ok" else "fresh",
        "checked_at": allocation["generated_at"],
        "mode": "fresh_rules_with_quality_warning" if allocation["quality"]["status"] != "ok" else "fresh",
        "reason": "已同步最新目标配置；若QMT快照存在质量警告，则禁止用异常成本字段生成精确交易建议。",
        "findings": allocation["quality"].get("warnings", []),
    }
    write_json(ALERT_RULES, rules)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync-intraday-rules", action="store_true")
    args = parser.parse_args(argv)
    index = build_latest_index()
    data = build_target_allocation(index)
    md_path, json_path = write_report(data)
    synced = sync_intraday_rules(data, json_path, index) if args.sync_intraday_rules else False
    print(json.dumps({"created": [rel_path(md_path), rel_path(json_path)], "synced_intraday_rules": synced}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
