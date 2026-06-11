#!/usr/bin/env python3
"""Generate target allocation from latest market/theme/portfolio inputs."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SCRIPT_ROOT / "scripts"
for candidate in (SCRIPT_ROOT, SCRIPTS_DIR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from project_utils import (
    ROOT,
    abs_path,
    build_latest_index,
    format_pct_range,
    latest_for_module,
    market_position_for_score,
    path_record,
    pct_range,
    read_json,
    rel_path,
    write_json,
)


OUTPUT_DIR = ROOT / "research" / "allocation"
ALERT_RULES = ROOT / "research" / "alerts" / "intraday_rules.json"

BUCKET_ORDER = ["cash_short", "core_base", "attack_mainline", "defense", "legacy_watch"]
BUCKET_LABELS = {
    "cash_short": "现金/短融",
    "core_base": "宽基底仓",
    "attack_mainline": "进攻主线仓",
    "defense": "防御仓",
    "legacy_watch": "其他/待清理",
}
BUCKET_COLORS = {
    "cash_short": "#5b6b7a",
    "core_base": "#2f6fbd",
    "attack_mainline": "#8b5cf6",
    "defense": "#0f8b6f",
    "legacy_watch": "#9a6700",
}


def dependency(path: str, index: dict[str, Any]) -> dict[str, Any]:
    record = path_record(path, index) or {}
    return {
        "module": record.get("module", "unknown"),
        "path": path,
        "generated_at": record.get("generated_at"),
        "basis_trade_date": record.get("basis_trade_date"),
        "sha256": record.get("sha256"),
    }


def actual_by_bucket(snapshot: dict[str, Any]) -> dict[str, float]:
    result = {key: 0.0 for key in BUCKET_ORDER}
    for item in snapshot.get("holdings", []):
        key = item.get("allocation_bucket") or "legacy_watch"
        if key not in result:
            key = "legacy_watch"
        result[key] += float(item.get("weight_pct") or 0)
    result["cash_short"] += float((snapshot.get("summary") or {}).get("cash_uninvested_pct") or 0)
    return {key: round(value, 4) for key, value in result.items()}


def build_segments(equity_center: float, cash_center: float) -> list[dict[str, Any]]:
    core = round(equity_center * 0.57, 2)
    attack = round(equity_center * 0.14, 2)
    defense = round(equity_center - core - attack, 2)
    targets = {
        "cash_short": round(cash_center, 2),
        "core_base": core,
        "attack_mainline": attack,
        "defense": defense,
        "legacy_watch": 0.0,
    }
    basis = {
        "cash_short": "Risk-off anchor from market-position mapping.",
        "core_base": "Keep core equity exposure, but do not add while total equity is above target.",
        "attack_mainline": "Pause new offensive exposure until market and theme gates recover.",
        "defense": "Defensive equity remains equity exposure and cannot replace cash/short-duration anchors.",
        "legacy_watch": "No ideal target; this bucket is a deviation cleanup candidate.",
    }
    return [
        {
            "key": key,
            "label": BUCKET_LABELS[key],
            "target_pct": targets[key],
            "color": BUCKET_COLORS[key],
            "basis": basis[key],
        }
        for key in BUCKET_ORDER
    ]


def build_overlay(segments: list[dict[str, Any]], actual: dict[str, float]) -> list[dict[str, Any]]:
    target_by_key = {item["key"]: float(item.get("target_pct") or 0) for item in segments}
    rows = []
    for key in BUCKET_ORDER:
        target = target_by_key.get(key, 0.0)
        current = float(actual.get(key, 0.0))
        if target == 0 and current == 0:
            continue
        rows.append(
            {
                "key": key,
                "label": BUCKET_LABELS[key],
                "color": BUCKET_COLORS[key],
                "target_pct": round(target, 4),
                "actual_pct": round(current, 4),
                "gap_pct": round(current - target, 4),
            }
        )
    return rows


def transition_targets(overlay: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in overlay:
        gap = float(item.get("gap_pct") or 0)
        if item["key"] == "legacy_watch" and gap > 0:
            priority = "P0"
        elif item["key"] in {"attack_mainline", "defense"} and gap > 1:
            priority = "P1"
        elif item["key"] == "cash_short" and gap < -1:
            priority = "P0"
        else:
            priority = "Observe"
        rows.append(
            {
                "key": item["key"],
                "label": item["label"],
                "actual_pct": item["actual_pct"],
                "target_pct": item["target_pct"],
                "gap_pct": item["gap_pct"],
                "priority": priority,
            }
        )
    return rows


def quality_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    warnings = []
    quality = snapshot.get("quality") or {}
    for item in quality.get("warnings", []):
        warnings.append(item.get("reason") if isinstance(item, dict) else str(item))
    return {"status": "warning" if warnings else "ok", "warnings": warnings}


def build_target_allocation(index: dict[str, Any], timestamp: str) -> dict[str, Any]:
    market_ref = latest_for_module("market_score", index)
    theme_ref = latest_for_module("theme_review", index)
    snapshot_ref = latest_for_module("portfolio_snapshot", index)
    if not market_ref or not theme_ref or not snapshot_ref:
        raise RuntimeError("Missing latest market_score, theme_review, or portfolio_snapshot")

    market = read_json(abs_path(market_ref["path"]), {})
    snapshot = read_json(abs_path(snapshot_ref["path"]), {})
    market_summary = market.get("summary") or {}
    score = market_summary.get("market_position_score")
    mapping = market_position_for_score(score) or {}
    equity_range = mapping.get("equity_allocation_range") or market_summary.get("equity_allocation_range") or "0%-0%"
    cash_range = mapping.get("bond_cash_allocation_range") or market_summary.get("bond_cash_allocation_range") or "0%-0%"
    equity_low, equity_high = pct_range(equity_range)
    cash_low, cash_high = pct_range(cash_range)
    equity_center = round((equity_low + equity_high) / 2, 2)
    cash_center = round((cash_low + cash_high) / 2, 2)
    segments = build_segments(equity_center, cash_center)
    actual = actual_by_bucket(snapshot)
    overlay = build_overlay(segments, actual)
    actual_equity = round(sum(actual.get(key, 0.0) for key in ["core_base", "attack_mainline", "defense", "legacy_watch"]), 4)
    actual_cash = round(actual.get("cash_short", 0.0), 4)
    quality = quality_from_snapshot(snapshot)

    return {
        "module": "target_allocation",
        "version": "2.1",
        "date": timestamp[:10],
        "generated_at": timestamp,
        "basis_trade_date": market.get("basis_trade_date"),
        "session": "from_latest_inputs",
        "privacy_policy": "ratio_only_no_monetary_values_no_unit_counts",
        "dependencies": {
            "required": [
                dependency(market_ref["path"], index),
                dependency(theme_ref["path"], index),
                dependency(snapshot_ref["path"], index),
                dependency("research/config/market_position_mapping.json", index),
                dependency("research/config/bucket_registry.json", index),
            ],
            "policy": "Invalid if any required upstream file is replaced by a newer file.",
        },
        "data_sources": [
            market_ref["path"],
            theme_ref["path"],
            snapshot_ref["path"],
            "research/config/market_position_mapping.json",
            "research/config/bucket_registry.json",
        ],
        "summary": {
            "market_state": mapping.get("market_state") or market_summary.get("market_state"),
            "market_position_score": score,
            "recommended_equity_center": f"{equity_center:g}%",
            "recommended_equity_range": equity_range,
            "recommended_bond_cash_center": f"{cash_center:g}%",
            "recommended_bond_cash_range": cash_range,
            "offensive_bucket_status": mapping.get("offensive_bucket_status") or market_summary.get("offensive_bucket_status"),
            "one_line_conclusion": (
                f"Market score {score} maps to equity {equity_range} and cash/short-duration {cash_range}; "
                f"actual equity is about {actual_equity:.2f}%, so downstream action plans may only reduce risk unless upstream gates improve."
            ),
        },
        "target_allocation": {
            "groups": [
                {
                    "group": item["label"],
                    "target_center_pct": item["target_pct"],
                    "target_range": "see ideal_allocation_map",
                    "role": "target_bucket",
                    "principle": item["basis"],
                }
                for item in segments
            ],
            "total_target_pct_sum": round(sum(float(item["target_pct"]) for item in segments), 4),
        },
        "ideal_allocation_map": {
            "basis": "market_position_mapping_and_latest_theme_context",
            "target_equity_pct": equity_center,
            "target_cash_short_pct": cash_center,
            "segments": segments,
        },
        "actual_allocation_overlay": {
            "source": snapshot_ref["path"],
            "actual_equity_pct": actual_equity,
            "actual_cash_short_pct": actual_cash,
            "buckets": overlay,
            "quality": quality,
        },
        "transition_targets": transition_targets(overlay),
        "quality": quality,
        "constraints": [
            "This module does not generate buy/sell instructions.",
            "Core underweight does not justify adding while total equity is above target.",
            "Offensive add actions are blocked when offensive_bucket_status is pause_new.",
        ],
        "decision_log_entry": (
            f"{timestamp[:10]} 目标仓位刷新：市场分数{score}按统一配置映射到权益{equity_range}、"
            f"现金/短融{cash_range}；真实权益约{actual_equity:.2f}%，交由ACTION_PLAN处理风险收缩。"
        ),
    }


def render_markdown(data: dict[str, Any]) -> str:
    overlay_rows = [
        f"| {item['label']} | {item['target_pct']:.2f}% | {item['actual_pct']:.2f}% | {item['gap_pct']:+.2f}pp |"
        for item in data["actual_allocation_overlay"]["buckets"]
    ]
    transition_rows = [
        f"| {item['label']} | {item['actual_pct']:.2f}% | {item['target_pct']:.2f}% | {item['priority']} |"
        for item in data["transition_targets"]
    ]
    return f"""# Target Allocation

Generated at: {data['generated_at']}
Basis trade date: {data.get('basis_trade_date')}

## Summary

{data['summary']['one_line_conclusion']}

| Item | Target |
| --- | ---: |
| Equity | {data['summary']['recommended_equity_range']}, center {data['summary']['recommended_equity_center']} |
| Cash/short-duration | {data['summary']['recommended_bond_cash_range']}, center {data['summary']['recommended_bond_cash_center']} |
| Offensive bucket | {data['summary']['offensive_bucket_status']} |

## Bucket Overlay

| Bucket | Target | Actual | Gap |
| --- | ---: | ---: | ---: |
{chr(10).join(overlay_rows)}

## Transition Priority

| Bucket | Actual | Target | Priority |
| --- | ---: | ---: | --- |
{chr(10).join(transition_rows)}

## Constraints

{chr(10).join(f"- {item}" for item in data['constraints'])}

## Quality

Status: {data['quality']['status']}

{chr(10).join(f"- {item}" for item in data['quality'].get('warnings', [])) or "- no major warning"}
"""


def write_report(data: dict[str, Any]) -> tuple[Path, Path]:
    timestamp = data["generated_at"]
    json_path = OUTPUT_DIR / f"target_allocation_{timestamp}.json"
    md_path = OUTPUT_DIR / f"target_allocation_{timestamp}.md"
    write_json(json_path, data)
    md_path.write_text(render_markdown(data), encoding="utf-8")
    return md_path, json_path


def ingest_generated_target_allocation(db_path: str | Path | None, json_path: Path) -> dict[str, Any] | None:
    from myinvest.db.dual_write import ingest_generated_json

    return ingest_generated_json(db_path, [json_path])


def sync_intraday_rules(allocation: dict[str, Any], allocation_path: Path, index: dict[str, Any]) -> bool:
    if not ALERT_RULES.exists():
        return False
    rules = read_json(ALERT_RULES, {})
    snapshot_path = allocation["actual_allocation_overlay"]["source"]
    buckets = allocation["actual_allocation_overlay"]["buckets"]
    segments = allocation["ideal_allocation_map"]["segments"]
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
        "ideal_segments": segments,
        "actual_overlay": [
            {"key": item["key"], "label": item["label"], "color": item["color"], "actual_pct": item["actual_pct"], "gap_pct": item["gap_pct"]}
            for item in buckets
            if item["actual_pct"] > 0
        ],
        "buckets": buckets,
        "quality": allocation["quality"],
    }
    required_paths = [item["path"] for item in allocation["dependencies"]["required"] if item.get("path")]
    valuation_paths = [
        item
        for item in rules.get("data_sources", [])
        if isinstance(item, str) and item.startswith("research/valuations/") and item.endswith(".json")
    ]
    rules["data_sources"] = ["docs/modules/INTRADAY_ALERTS.md", "docs/modules/VALUATION_RESEARCH.md"] + required_paths + valuation_paths
    rules["dependencies"] = {
        "required": [dependency(path, index) for path in required_paths + valuation_paths],
        "policy": "If any required upstream is replaced by a newer file, intraday_rules must be marked stale/degraded and cannot emit buy/add alerts.",
    }
    rules["staleness"] = {
        "status": "degraded" if allocation["quality"]["status"] != "ok" else "fresh",
        "checked_at": allocation["generated_at"],
        "reason": "Synced with latest target allocation; quality warnings block buy/add use.",
        "findings": allocation["quality"].get("warnings", []),
    }
    write_json(ALERT_RULES, rules)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    parser.add_argument("--sync-intraday-rules", action="store_true")
    parser.add_argument("--db", type=Path, help="Also ingest the generated JSON artifact into the history SQLite database.")
    args = parser.parse_args(argv)
    index = build_latest_index()
    data = build_target_allocation(index, args.timestamp)
    md_path, json_path = write_report(data)
    db_ingest = ingest_generated_target_allocation(args.db, json_path)
    synced = sync_intraday_rules(data, json_path, index) if args.sync_intraday_rules else False
    result = {"created": [rel_path(md_path), rel_path(json_path)], "synced_intraday_rules": synced}
    if db_ingest is not None:
        result["db_ingest"] = db_ingest
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
