#!/usr/bin/env python3
"""Audit current holdings for ResearchFirst readiness.

The audit is ratio-only: it reads holding weights but never writes amounts,
unit counts, account identifiers, or raw PnL amounts.
"""

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
    latest_for_module,
    load_latest_index,
    read_json,
    rel_path,
    write_json,
)


PORTFOLIO_DIR = ROOT / "research" / "portfolio"
DECISION_LOG = ROOT / "research" / "logs" / "decision_log.md"
ETF_REGISTRY = ROOT / "research" / "etfs" / "etf_registry.json"
STOCK_REGISTRY = ROOT / "research" / "stocks" / "stock_registry.json"


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


def registry_by_code(path: Path, key: str) -> dict[str, dict[str, Any]]:
    data = read_json(path, {})
    rows: dict[str, dict[str, Any]] = {}
    for item in data.get(key, []) or []:
        code = normalize_code(item.get("code"))
        if code:
            rows[code] = item
            rows[code.split(".", 1)[0]] = item
    return rows


def latest_valuation_by_code(index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for record in index.get("files", []) or []:
        if record.get("module") != "valuation_report":
            continue
        code = normalize_code(record.get("code"))
        if not code:
            continue
        previous = rows.get(code)
        if previous is None or str(record.get("generated_at") or "") > str(previous.get("generated_at") or ""):
            rows[code] = record
            rows[code.split(".", 1)[0]] = record
    return rows


def valuation_status(record: dict[str, Any] | None, minimum_basis: str) -> tuple[str, str | None, str | None]:
    if not record:
        return "missing", None, None
    basis = str(record.get("basis_trade_date") or record.get("basis_date") or record.get("date") or "")
    if minimum_basis and basis and basis < minimum_basis:
        return "stale", record.get("path"), basis
    if minimum_basis and not basis:
        return "stale", record.get("path"), basis
    return "ok", record.get("path"), basis


def profile_status(registry_item: dict[str, Any] | None) -> tuple[str, str | None]:
    if not registry_item:
        return "missing", None
    status = str(registry_item.get("status") or "").lower()
    profile = registry_item.get("last_profile_json") or registry_item.get("last_profile_file")
    if status not in {"profile_generated", "ok", "available"} or not profile:
        return "missing", profile
    return "ok", profile


def theme_status(registry_item: dict[str, Any] | None) -> tuple[str, str, str]:
    if not registry_item:
        return "missing", "", ""
    theme = str(registry_item.get("related_theme") or "").strip()
    binding = str(registry_item.get("theme_binding_status") or "").strip()
    if not theme:
        return "missing", "", binding
    return "ok", theme, binding


def build_item(
    holding: dict[str, Any],
    registry_item: dict[str, Any] | None,
    valuation_record: dict[str, Any] | None,
    minimum_basis: str,
    large_position_threshold: float,
) -> dict[str, Any]:
    code = normalize_code(holding.get("ts_code") or holding.get("code"))
    weight = round(float(holding.get("weight_pct") or 0), 4)
    prof_status, prof_source = profile_status(registry_item)
    val_status, val_source, val_basis = valuation_status(valuation_record, minimum_basis)
    th_status, theme, binding = theme_status(registry_item)

    issues: list[str] = []
    if prof_status != "ok":
        issues.append("profile_missing")
    if val_status != "ok":
        issues.append("valuation_stale" if val_status == "stale" else "valuation_missing")
    if th_status != "ok":
        issues.append("theme_missing")

    if any(issue in issues for issue in ["profile_missing", "valuation_missing", "valuation_stale"]):
        priority = "P0"
    elif issues:
        priority = "P1"
    elif weight >= large_position_threshold:
        priority = "P2_review_large_current"
    else:
        priority = "OK"

    return {
        "priority": priority,
        "code": code,
        "name": holding.get("name") or (registry_item or {}).get("name") or "",
        "type": holding.get("type") or ("ETF" if code.startswith("5") or code.startswith("1") else "stock"),
        "weight_pct": weight,
        "allocation_bucket": holding.get("allocation_bucket") or (registry_item or {}).get("bucket_role") or "",
        "category": holding.get("category") or "",
        "profile_status": prof_status,
        "profile_source": prof_source,
        "valuation_status": val_status,
        "valuation_source": val_source,
        "valuation_basis": val_basis,
        "theme_status": th_status,
        "theme": theme,
        "theme_binding_status": binding,
        "issues": issues,
        "next_step": "No immediate research needed." if not issues else "Refresh profile/valuation/theme binding before any single-name operation.",
    }


def render_markdown(data: dict[str, Any]) -> str:
    rows = [
        "| Priority | Code | Name | Weight | Issues | Next step |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for item in data["items"]:
        issues = ", ".join(item.get("issues") or []) or "-"
        rows.append(
            f"| {item['priority']} | {item['code']} | {item['name']} | {item['weight_pct']:.4f}% | {issues} | {item['next_step']} |"
        )
    summary = data["summary"]
    return f"""# Current Holding Research Quality Audit

Generated at: {data['generated_at']}
Basis portfolio snapshot: `{data['basis_portfolio_snapshot']}`
Minimum valuation basis trade date: {data['minimum_valuation_basis_trade_date']}

## Summary

- Total holdings: {summary['total_holdings']}
- P0: {summary['p0']}
- P1: {summary['p1']}
- P2 review large current: {summary['p2_review_large_current']}
- OK: {summary['ok']}

## Items

{chr(10).join(rows)}

## Boundary

This audit is ratio-only. It does not generate buy, sell, add, or reduce instructions.
"""


def append_decision_log(data: dict[str, Any], md_path: Path, json_path: Path) -> None:
    summary = data["summary"]
    lines = [
        "",
        (
            f"## {data['generated_at']} current holding research quality audit: "
            f"P0={summary['p0']}, P1={summary['p1']}, P2={summary['p2_review_large_current']}, OK={summary['ok']}."
        ),
        f"- Markdown: `{rel_path(md_path)}`",
        f"- JSON: `{rel_path(json_path)}`",
        f"- Basis snapshot: `{data['basis_portfolio_snapshot']}`",
        "- Boundary: current holdings only; ratio-only; no single-security operation instruction.",
    ]
    DECISION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DECISION_LOG.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def build_audit(timestamp: str, minimum_basis: str, large_position_threshold: float) -> dict[str, Any]:
    index = load_latest_index()
    portfolio_ref = latest_for_module("portfolio_snapshot", index)
    if not portfolio_ref:
        raise RuntimeError("missing latest portfolio_snapshot")
    portfolio = read_json(abs_path(portfolio_ref["path"]), {})
    etf_registry = registry_by_code(ETF_REGISTRY, "etfs")
    stock_registry = registry_by_code(STOCK_REGISTRY, "stocks")
    valuations = latest_valuation_by_code(index)

    items: list[dict[str, Any]] = []
    for holding in portfolio.get("holdings", []) or []:
        code = normalize_code(holding.get("ts_code") or holding.get("code"))
        registry_item = etf_registry.get(code) or stock_registry.get(code) or etf_registry.get(code.split(".", 1)[0]) or stock_registry.get(code.split(".", 1)[0])
        items.append(build_item(holding, registry_item, valuations.get(code), minimum_basis, large_position_threshold))

    order = {"P0": 0, "P1": 1, "P2_review_large_current": 2, "OK": 3}
    items.sort(key=lambda item: (order.get(item["priority"], 99), -float(item.get("weight_pct") or 0), item["code"]))
    summary = {
        "total_holdings": len(items),
        "p0": sum(1 for item in items if item["priority"] == "P0"),
        "p1": sum(1 for item in items if item["priority"] == "P1"),
        "p2_review_large_current": sum(1 for item in items if item["priority"] == "P2_review_large_current"),
        "ok": sum(1 for item in items if item["priority"] == "OK"),
    }
    return {
        "module": "current_holding_research_quality_audit",
        "version": "ratio_only_v2",
        "generated_at": timestamp,
        "basis_portfolio_snapshot": portfolio_ref["path"],
        "minimum_valuation_basis_trade_date": minimum_basis,
        "large_position_threshold_pct": large_position_threshold,
        "privacy_policy": "ratio_only_no_monetary_values_no_unit_counts",
        "summary": summary,
        "items": items,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    parser.add_argument("--minimum-valuation-basis-date", default="")
    parser.add_argument("--large-position-threshold", type=float, default=2.0)
    parser.add_argument("--no-log", action="store_true")
    args = parser.parse_args(argv)

    minimum_basis = args.minimum_valuation_basis_date
    if not minimum_basis:
        index = load_latest_index()
        market_ref = latest_for_module("market_score", index)
        market = read_json(abs_path(market_ref["path"]), {}) if market_ref else {}
        minimum_basis = str(market.get("basis_trade_date") or "")

    audit = build_audit(args.timestamp, minimum_basis, args.large_position_threshold)
    json_path = PORTFOLIO_DIR / f"research_quality_audit_{args.timestamp}.json"
    md_path = PORTFOLIO_DIR / f"research_quality_audit_{args.timestamp}.md"
    write_json(json_path, audit)
    md_path.write_text(render_markdown(audit), encoding="utf-8")
    if not args.no_log:
        append_decision_log(audit, md_path, json_path)
    print(json.dumps({"created": [rel_path(md_path), rel_path(json_path)], "summary": audit["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
