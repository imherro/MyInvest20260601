#!/usr/bin/env python3
"""Generate a ratio-only review for P2 large current holdings."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from project_utils import ROOT, abs_path, latest_for_module, load_latest_index, read_json, rel_path, write_json


PORTFOLIO_DIR = ROOT / "research" / "portfolio"
DECISION_LOG = ROOT / "research" / "logs" / "decision_log.md"


def bucket_focus(bucket: str, category: str) -> str:
    if bucket == "cash_short":
        return "现金/短融承接工具，重点复核是否仍匹配目标现金短融比例、流动性和久期边界。"
    if bucket == "defense":
        return "防御权益仓，重点复核是否被误当作现金，以及是否挤占目标权益仓空间。"
    if bucket == "attack_mainline":
        return "进攻或主题权益仓，重点复核是否仍有主线/估值/趋势支持。"
    if bucket == "legacy_watch":
        return "遗留观察仓，重点复核是否仍有保留理由，不能自动转为新增配置。"
    if category in {"medicine", "financial", "resources"}:
        return "行业/主题暴露，重点复核集中度和与当前主线的相关性。"
    return "大仓位或相对重要持仓，重点复核其组合角色是否仍成立。"


def review_status(item: dict[str, Any]) -> str:
    bucket = str(item.get("allocation_bucket") or "")
    theme = str(item.get("theme") or "")
    category = str(item.get("category") or "")
    if bucket == "cash_short":
        return "cash_short_anchor_review"
    if bucket == "legacy_watch":
        return "legacy_position_review"
    if category in {"medicine", "financial", "resources"}:
        return "industry_concentration_review"
    if "不适用" in theme or "防御" in theme or bucket == "defense":
        return "defensive_or_quality_review"
    return "theme_concentration_review"


def build_review(timestamp: str) -> dict[str, Any]:
    index = load_latest_index()
    audit_ref = latest_for_module("research_quality_audit", index)
    action_ref = latest_for_module("action_plan", index)
    allocation_ref = latest_for_module("target_allocation", index)
    if not audit_ref:
        raise RuntimeError("missing latest research_quality_audit")
    audit = read_json(abs_path(audit_ref["path"]), {})
    rows = []
    for item in audit.get("items", []) or []:
        if item.get("priority") != "P2_review_large_current":
            continue
        rows.append(
            {
                "code": item.get("code"),
                "name": item.get("name"),
                "type": item.get("type"),
                "weight_pct": item.get("weight_pct"),
                "allocation_bucket": item.get("allocation_bucket"),
                "category": item.get("category"),
                "theme": item.get("theme"),
                "valuation_source": item.get("valuation_source"),
                "profile_source": item.get("profile_source"),
                "review_status": review_status(item),
                "review_focus": bucket_focus(str(item.get("allocation_bucket") or ""), str(item.get("category") or "")),
                "operation_boundary": "Review only; no single-security buy/sell/add/reduce instruction.",
            }
        )

    return {
        "module": "portfolio_cleanup_review",
        "version": "p2_large_position_review_ratio_only_v1",
        "generated_at": timestamp,
        "basis_research_quality_audit": audit_ref["path"],
        "basis_action_plan": action_ref["path"] if action_ref else None,
        "basis_target_allocation": allocation_ref["path"] if allocation_ref else None,
        "privacy_policy": "ratio_only_no_monetary_values_no_unit_counts",
        "summary": {
            "p2_count": len(rows),
            "one_line_conclusion": "P2 items have passed ResearchFirst blocking checks but require large-position role review before any single-security decision.",
        },
        "items": rows,
        "boundary": "This review is ratio-only and does not generate buy, sell, add, or reduce instructions.",
    }


def render_markdown(data: dict[str, Any]) -> str:
    rows = [
        "| Code | Name | Weight | Bucket | Review status | Focus |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for item in data["items"]:
        rows.append(
            f"| {item['code']} | {item['name']} | {float(item['weight_pct']):.4f}% | {item['allocation_bucket']} | {item['review_status']} | {item['review_focus']} |"
        )
    return f"""# P2 Large Position Review

Generated at: {data['generated_at']}

## Summary

{data['summary']['one_line_conclusion']}

P2 count: {data['summary']['p2_count']}

## Items

{chr(10).join(rows)}

## Boundary

{data['boundary']}
"""


def append_decision_log(data: dict[str, Any], md_path: Path, json_path: Path) -> None:
    lines = [
        "",
        f"## {data['generated_at']} P2 large position review: {data['summary']['p2_count']} items.",
        f"- Markdown: `{rel_path(md_path)}`",
        f"- JSON: `{rel_path(json_path)}`",
        f"- Basis audit: `{data['basis_research_quality_audit']}`",
        "- Boundary: ratio-only review; no single-security operation instruction.",
    ]
    DECISION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DECISION_LOG.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    parser.add_argument("--no-log", action="store_true")
    args = parser.parse_args(argv)
    review = build_review(args.timestamp)
    json_path = PORTFOLIO_DIR / f"portfolio_cleanup_{args.timestamp}.json"
    md_path = PORTFOLIO_DIR / f"portfolio_cleanup_{args.timestamp}.md"
    write_json(json_path, review)
    md_path.write_text(render_markdown(review), encoding="utf-8")
    if not args.no_log:
        append_decision_log(review, md_path, json_path)
    print(json.dumps({"created": [rel_path(md_path), rel_path(json_path)], "summary": review["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
