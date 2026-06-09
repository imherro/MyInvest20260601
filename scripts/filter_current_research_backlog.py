#!/usr/bin/env python3
"""Filter ResearchFirst backlog by the latest real holdings snapshot."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from project_utils import ROOT, abs_path, latest_for_module, load_latest_index, read_json, rel_path, write_json


PORTFOLIO_DIR = ROOT / "research" / "portfolio"
STOCK_REGISTRY = ROOT / "research" / "stocks" / "stock_registry.json"
ETF_REGISTRY = ROOT / "research" / "etfs" / "etf_registry.json"
DECISION_LOG = ROOT / "research" / "logs" / "decision_log.md"


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


def latest_path(module: str, explicit: str | None) -> Path:
    if explicit:
        return abs_path(explicit)
    record = latest_for_module(module, load_latest_index())
    if not record:
        raise RuntimeError(f"missing latest module: {module}")
    return abs_path(record["path"])


def held_code_sets(snapshot: dict[str, Any]) -> tuple[set[str], set[str]]:
    full: set[str] = set()
    raw: set[str] = set()
    for item in snapshot.get("holdings", []) or []:
        for key in ["code", "ts_code"]:
            code = normalize_code(item.get(key))
            if code:
                full.add(code)
                raw.add(code.split(".", 1)[0])
    return full, raw


def registry_by_code(path: Path, list_key: str) -> dict[str, dict[str, Any]]:
    data = read_json(path, {})
    rows: dict[str, dict[str, Any]] = {}
    for item in data.get(list_key, []) or []:
        code = normalize_code(item.get("code"))
        if code:
            rows[code] = item
            rows[code.split(".", 1)[0]] = item
    return rows


def mark_non_current_stocks(codes: set[str], snapshot_path: Path, timestamp: str) -> None:
    if not codes:
        return
    registry = read_json(STOCK_REGISTRY, {})
    for item in registry.get("stocks", []) or []:
        raw = normalize_code(item.get("code")).split(".", 1)[0]
        if raw not in codes:
            continue
        item["status"] = "not_current_holding_skip_research"
        item["current_weight_pct"] = None
        item["bucket_role"] = "not_current_holding"
        item["related_theme"] = item.get("related_theme") if item.get("related_theme") not in {"", "pending"} else "not_current_holding"
        item["rating"] = item.get("rating") if item.get("rating") not in {"", "pending"} else "not_applicable"
        item["action_rating"] = "Watch"
        item["target_position_range"] = "0%; not current holding, no ResearchFirst work unless re-added to holdings/watchlist."
        item["reason"] = "Not present in latest portfolio snapshot; non-holdings are excluded from active ResearchFirst work."
        item["last_checked_snapshot"] = rel_path(snapshot_path)
        item["last_status_change"] = timestamp
    registry["last_updated"] = timestamp[:10]
    registry.setdefault("change_log", []).append(
        {
            "date": timestamp[:10],
            "timestamp": timestamp,
            "change": "Filtered non-current holdings out of active ResearchFirst work.",
            "codes": sorted(codes),
            "basis_snapshot": rel_path(snapshot_path),
        }
    )
    write_json(STOCK_REGISTRY, registry)


def render_markdown(data: dict[str, Any]) -> str:
    def rows(items: list[dict[str, Any]], status: str) -> str:
        if not items:
            return "| - | - | - | - | none | - |"
        rendered = []
        for idx, item in enumerate(items, start=1):
            reason = item.get("skip_reason") or item.get("completion_source") or item.get("next_step") or ""
            rendered.append(
                f"| {idx} | `{item.get('ts_code') or item.get('code') or ''}` | {item.get('name') or ''} | "
                f"{item.get('subject_type') or ''} | {status} | {reason} |"
            )
        return "\n".join(rendered)

    summary = data["summary"]
    return f"""# ResearchFirst Current-Holdings Filter: {data['generated_at']}

Filtered by the latest real portfolio snapshot. Non-current holdings are not active ResearchFirst work.

- Previous backlog: `{data['previous_backlog']}`
- Portfolio snapshot: `{data['basis_portfolio_snapshot']}`
- Active research items: {summary['active_research_items']}
- Completed current holdings: {summary['completed_current_holdings']}
- Skipped non-current holdings: {summary['skipped_not_current_holdings']}
- Boundary: research queue only; no buy/sell/add/reduce instruction.

## Active Research

| Rank | Code | Name | Type | Status | Reason |
|---:|---|---|---|---|---|
{rows(data['items'], 'active')}

## Completed Current Holdings

| Rank | Code | Name | Type | Status | Source |
|---:|---|---|---|---|---|
{rows(data['completed_current_holdings'], 'completed_current_holding')}

## Skipped Non-Current Holdings

| Rank | Code | Name | Type | Status | Reason |
|---:|---|---|---|---|---|
{rows(data['skipped_not_current_holdings'], 'skipped_not_current_holding')}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", help="Portfolio snapshot path. Defaults to latest_index portfolio_snapshot.")
    parser.add_argument("--backlog", help="Research backlog path. Defaults to latest_index research_backlog.")
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    parser.add_argument("--no-log", action="store_true")
    args = parser.parse_args()

    snapshot_path = latest_path("portfolio_snapshot", args.snapshot)
    backlog_path = latest_path("research_backlog", args.backlog)
    snapshot = read_json(snapshot_path, {})
    backlog = read_json(backlog_path, {})
    held_full, held_raw = held_code_sets(snapshot)
    etfs = registry_by_code(ETF_REGISTRY, "etfs")
    stocks = registry_by_code(STOCK_REGISTRY, "stocks")

    active: list[dict[str, Any]] = []
    completed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    skipped_stock_codes: set[str] = set()

    for item in backlog.get("items", []) or []:
        code = normalize_code(item.get("ts_code") or item.get("code"))
        raw = code.split(".", 1)[0] if code else str(item.get("code") or "")
        normalized = dict(item)
        if code not in held_full and raw not in held_raw:
            normalized["queue_status"] = "skipped_not_current_holding"
            normalized["skip_reason"] = "Not present in latest portfolio snapshot."
            skipped.append(normalized)
            if str(item.get("subject_type") or "").lower() == "stock":
                skipped_stock_codes.add(raw)
            continue

        registry_item = etfs.get(code) or etfs.get(raw) or stocks.get(code) or stocks.get(raw) or {}
        status = str(registry_item.get("status") or "").lower()
        if status in {"to_research", "researchfirst", "research_first", "pending"}:
            active.append(normalized)
        else:
            normalized["queue_status"] = "completed_current_holding"
            normalized["completion_source"] = registry_item.get("last_profile_json") or registry_item.get("last_profile_file") or ""
            completed.append(normalized)

    mark_non_current_stocks(skipped_stock_codes, snapshot_path, args.timestamp)

    output = {
        "module": "portfolio_research_backlog",
        "version": "current_holdings_filtered_v1",
        "generated_at": args.timestamp,
        "basis_trade_date": snapshot.get("basis_trade_date") or snapshot.get("date"),
        "basis_portfolio_snapshot": rel_path(snapshot_path),
        "previous_backlog": rel_path(backlog_path),
        "boundary": "Research queue only; no buy/sell/reduce/add instruction.",
        "privacy_policy": "ratio_only_no_monetary_values_no_unit_counts",
        "summary": {
            "active_research_items": len(active),
            "completed_current_holdings": len(completed),
            "skipped_not_current_holdings": len(skipped),
            "note": "Filtered by latest portfolio snapshot; non-current holdings are removed from active ResearchFirst work.",
        },
        "items": active,
        "completed_current_holdings": completed,
        "skipped_not_current_holdings": skipped,
        "decision_log_entry": (
            f"{args.timestamp} ResearchFirst current-holdings filter: active={len(active)}, "
            f"completed_current={len(completed)}, skipped_not_current={len(skipped)}."
        ),
    }

    json_path = PORTFOLIO_DIR / f"research_backlog_{args.timestamp}.json"
    md_path = PORTFOLIO_DIR / f"research_backlog_{args.timestamp}.md"
    write_json(json_path, output)
    md_path.write_text(render_markdown(output), encoding="utf-8")

    if not args.no_log:
        DECISION_LOG.open("a", encoding="utf-8").write(
            "\n"
            f"## {output['decision_log_entry']}\n"
            f"- Markdown: `{rel_path(md_path)}`\n"
            f"- JSON: `{rel_path(json_path)}`\n"
            f"- Basis snapshot: `{rel_path(snapshot_path)}`\n"
            "- Conclusion: non-current holdings are excluded from active ResearchFirst work unless re-added to holdings/watchlist.\n"
        )

    print(json.dumps({"created": [rel_path(md_path), rel_path(json_path)], "active": len(active), "completed": len(completed), "skipped": len(skipped)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
