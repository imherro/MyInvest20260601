#!/usr/bin/env python3
"""Check whether held or monitored securities need valuation refresh.

This script is a data-quality gate. It does not generate buy, sell, add, or
reduce instructions.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from project_utils import ROOT, abs_path, latest_for_module, load_latest_index, read_json, rel_path, write_json


PORTFOLIO_DIR = ROOT / "research" / "portfolio"
VALUATION_DIR = ROOT / "research" / "valuations"
ALERT_RULES = ROOT / "research" / "alerts" / "intraday_rules.json"
CHECK_DIR = ROOT / "research" / "checks"


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def latest_complete_trade_date(now: datetime | None = None) -> str:
    now = now or datetime.now()
    fallback = now.strftime("%Y%m%d")
    try:
        import tushare as ts  # type: ignore
    except Exception:
        return fallback

    load_env()
    token = os.environ.get("TUSHARE_TOKEN")
    if not token:
        return fallback
    try:
        pro = ts.pro_api(token)
        end = now.strftime("%Y%m%d")
        start = (now - timedelta(days=14)).strftime("%Y%m%d")
        cal = pro.trade_cal(exchange="", start_date=start, end_date=end)
    except Exception:
        return fallback
    if cal.empty:
        return fallback
    open_days = sorted(str(item) for item in cal[cal["is_open"] == 1]["cal_date"].tolist())
    if not open_days:
        return fallback
    today = now.strftime("%Y%m%d")
    if now.hour < 16 and today in open_days:
        previous = [day for day in open_days if day < today]
        return previous[-1] if previous else open_days[-1]
    return open_days[-1]


def plain_code(code: Any) -> str:
    return re.sub(r"\D", "", str(code or ""))[:6]


def suffix_for_code(code: Any) -> str:
    raw = plain_code(code)
    if not raw:
        return ""
    if raw.startswith(("5", "6", "9")):
        return f"{raw}.SH"
    return f"{raw}.SZ"


def latest_file_by_timestamp(directory: Path, pattern: str) -> Path | None:
    files = sorted(directory.glob(pattern))
    return files[-1] if files else None


def latest_portfolio() -> tuple[dict[str, Any], Path | None]:
    index = load_latest_index()
    ref = latest_for_module("portfolio_snapshot", index)
    if ref:
        path = abs_path(ref["path"])
        return read_json(path, {}), path
    path = latest_file_by_timestamp(PORTFOLIO_DIR, "portfolio_snapshot_*.json")
    return (read_json(path, {}), path) if path else ({}, None)


def load_subjects() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rules = read_json(ALERT_RULES, {})
    return rules, rules.get("subjects", []) or []


def add_target(targets: dict[str, dict[str, Any]], code: str, name: str, source: str, source_file: str | None = None) -> None:
    ts_code = suffix_for_code(code)
    if not ts_code:
        return
    targets.setdefault(ts_code, {"code": ts_code, "name": name or "", "sources": [], "source_files": []})
    if name and not targets[ts_code].get("name"):
        targets[ts_code]["name"] = name
    targets[ts_code]["sources"].append(source)
    if source_file:
        targets[ts_code]["source_files"].append(source_file)


def collect_targets() -> dict[str, dict[str, Any]]:
    targets: dict[str, dict[str, Any]] = {}
    portfolio, portfolio_path = latest_portfolio()
    portfolio_file = rel_path(portfolio_path) if portfolio_path else None
    for item in portfolio.get("holdings", []) or []:
        add_target(targets, item.get("ts_code") or item.get("code"), item.get("name", ""), "portfolio", portfolio_file)

    _rules, subjects = load_subjects()
    for subject in subjects:
        add_target(targets, subject.get("code"), subject.get("name", ""), "intraday_rules", rel_path(ALERT_RULES))
    for target in targets.values():
        target["sources"] = sorted(set(target.get("sources", [])))
        target["source_files"] = sorted(set(target.get("source_files", [])))
    return targets


def latest_valuation_for(code: str) -> tuple[dict[str, Any], Path | None]:
    code_key = suffix_for_code(code).replace(".", "_")
    path = latest_file_by_timestamp(VALUATION_DIR, f"valuation_{code_key}_*.json")
    if not path:
        return {}, None
    return read_json(path, {}), path


def read_json_tolerant(path: Path, default: Any) -> Any:
    for encoding in ("utf-8-sig", "utf-16", "utf-8"):
        try:
            return json.loads(path.read_text(encoding=encoding))
        except (UnicodeError, json.JSONDecodeError):
            continue
    return default


def intraday_quotes_by_code(report_path: Path | None) -> dict[str, dict[str, Any]]:
    if not report_path or not report_path.exists():
        return {}
    report = read_json_tolerant(report_path, {})
    quotes = report.get("monitored_quotes", []) or []
    result: dict[str, dict[str, Any]] = {}
    for item in quotes:
        code = suffix_for_code(item.get("code"))
        if code:
            result[code] = item
    return result


def date_age_days(date_text: Any, basis_date: str) -> int | None:
    if not date_text:
        return None
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            left = datetime.strptime(str(date_text), fmt)
            right = datetime.strptime(basis_date, "%Y%m%d")
            return (right - left).days
        except ValueError:
            continue
    return None


def severity_rank(value: str) -> int:
    return {"ok": 0, "watch": 1, "update": 2, "missing": 3}.get(value, 0)


def valuation_price_date(valuation: dict[str, Any]) -> Any:
    return (
        (valuation.get("reference_metrics") or {}).get("price_date")
        or valuation.get("basis_trade_date")
        or valuation.get("basis_date")
        or valuation.get("date")
    )


def check_updates(basis_date: str, intraday_report: Path | None = None, stale_days: int = 1) -> dict[str, Any]:
    targets = collect_targets()
    intraday_quotes = intraday_quotes_by_code(intraday_report)
    items: list[dict[str, Any]] = []

    for code, target in sorted(targets.items()):
        valuation, valuation_path = latest_valuation_for(code)
        quote = intraday_quotes.get(code, {})
        reasons: list[str] = []
        severity = "ok"
        price_date = None
        age_days = None

        if not valuation_path:
            severity = "missing"
            reasons.append("缺少估值报告")
        else:
            price_date = valuation_price_date(valuation)
            age_days = date_age_days(price_date, basis_date)
            if age_days is None:
                severity = "update"
                reasons.append("估值报告缺少可解析的基准日")
            elif age_days > stale_days:
                severity = "update"
                reasons.append(f"估值基准日 {price_date} 距离检查基准日 {basis_date} 已超过 {stale_days} 天")

        if quote.get("valuation_zone_changed") and quote.get("allocation_bucket") != "cash_short":
            report_zone = (quote.get("valuation_report_zone") or {}).get("label")
            live_zone = (quote.get("realtime_valuation_zone") or {}).get("label")
            reasons.append(f"实时价格已跨估值区：报告={report_zone or '-'}，实时={live_zone or '-'}")
            severity = "update" if severity_rank(severity) < severity_rank("update") else severity

        if reasons:
            items.append(
                {
                    "code": code,
                    "name": target.get("name", ""),
                    "sources": target.get("sources", []),
                    "source_files": target.get("source_files", []),
                    "severity": severity,
                    "reasons": reasons,
                    "latest_valuation": rel_path(valuation_path) if valuation_path else None,
                    "valuation_price_date": price_date,
                    "age_days": age_days,
                    "suggested_next_step": f"先确认是否刷新 {code} {target.get('name', '')} 的估值报告；未刷新前不得把旧估值状态当作当前结论。",
                }
            )

    status = "ok" if not items else ("missing" if any(item["severity"] == "missing" for item in items) else "update_needed")
    return {
        "module": "valuation_update_check",
        "version": "ratio_only_v2",
        "generated_at": datetime.now().strftime("%Y-%m-%d_%H%M%S"),
        "basis_date": basis_date,
        "scope": "latest_portfolio_and_intraday_rules",
        "stale_days": stale_days,
        "status": status,
        "blocking_for_new_actions": bool(items),
        "update_required_count": len(items),
        "items": items,
        "summary": "估值报告无缺失或应更新项。" if not items else f"发现 {len(items)} 个估值报告缺失、过期或盘中跨区项；新增单标的动作前应先确认是否刷新估值报告。",
        "boundary": "Valuation refresh check only; no buy/sell/add/reduce instruction.",
    }


def render_markdown(report: dict[str, Any]) -> str:
    rows = [
        "| Code | Name | Severity | Latest valuation | Reasons |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in report.get("items", []):
        rows.append(
            "| {code} | {name} | {severity} | {valuation} | {reasons} |".format(
                code=item.get("code", ""),
                name=item.get("name", ""),
                severity=item.get("severity", ""),
                valuation=item.get("latest_valuation") or "-",
                reasons="; ".join(item.get("reasons", [])),
            )
        )
    if not report.get("items"):
        rows.append("| - | - | ok | - | 无 |")
    return f"""# Valuation Update Check

Generated at: {report['generated_at']}
Basis date: {report['basis_date']}
Status: {report['status']}

{report['summary']}

## Items

{chr(10).join(rows)}

## Boundary

{report['boundary']}
"""


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--basis-date", help="Check basis date in YYYYMMDD. Defaults to latest complete trading day.")
    parser.add_argument("--intraday-report", type=Path, help="Optional intraday report JSON for live zone-change checks.")
    parser.add_argument("--stale-days", type=int, default=1, help="Flag valuation reports older than this many calendar days.")
    parser.add_argument("--write-report", action="store_true", help="Write Markdown and JSON report under research/checks.")
    args = parser.parse_args(argv)

    basis_date = args.basis_date or latest_complete_trade_date()
    report = check_updates(basis_date, args.intraday_report, args.stale_days)
    if args.write_report:
        timestamp = report["generated_at"]
        json_path = CHECK_DIR / f"valuation_update_check_{timestamp}.json"
        md_path = CHECK_DIR / f"valuation_update_check_{timestamp}.md"
        write_json(json_path, report)
        md_path.write_text(render_markdown(report), encoding="utf-8")
        report["output_files"] = [rel_path(md_path), rel_path(json_path)]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["update_required_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
