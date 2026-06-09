#!/usr/bin/env python3
"""Check whether watched or held securities need valuation report updates."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "research" / "portfolio"
VALUATION_DIR = ROOT / "research" / "valuations"
ALERT_RULES = ROOT / "research" / "alerts" / "intraday_rules.json"


def rel_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


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
        prev = [day for day in open_days if day < today]
        return prev[-1] if prev else open_days[-1]
    return open_days[-1]


def plain_code(code: str) -> str:
    return re.sub(r"\D", "", str(code))[:6]


def suffix_for_code(code: str) -> str:
    code = plain_code(code)
    if not code:
        return ""
    if code.startswith(("5", "6", "9")):
        return f"{code}.SH"
    return f"{code}.SZ"


def latest_file(directory: Path, pattern: str) -> Path | None:
    files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def latest_portfolio() -> tuple[dict[str, Any], Path | None]:
    path = latest_file(PORTFOLIO_DIR, "portfolio_snapshot_*.json")
    if not path:
        return {}, None
    return read_json(path, {}), path


def load_subjects() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rules = read_json(ALERT_RULES, {})
    return rules, rules.get("subjects", [])


def collect_targets() -> dict[str, dict[str, Any]]:
    targets: dict[str, dict[str, Any]] = {}
    portfolio, portfolio_path = latest_portfolio()
    for item in portfolio.get("holdings", []):
        code = suffix_for_code(str(item.get("code", "")))
        if not code:
            continue
        targets.setdefault(
            code,
            {
                "code": code,
                "name": item.get("name", ""),
                "sources": [],
            },
        )
        targets[code]["sources"].append("portfolio")
        targets[code]["portfolio_snapshot"] = portfolio_path.as_posix() if portfolio_path else None

    _rules, subjects = load_subjects()
    for subject in subjects:
        code = suffix_for_code(str(subject.get("code", "")))
        if not code:
            continue
        targets.setdefault(
            code,
            {
                "code": code,
                "name": subject.get("name", ""),
                "sources": [],
            },
        )
        targets[code]["name"] = targets[code].get("name") or subject.get("name", "")
        targets[code]["sources"].append("intraday_rules")
    return targets


def latest_valuation_for(code: str) -> tuple[dict[str, Any], Path | None]:
    code_key = suffix_for_code(code).replace(".", "_")
    path = latest_file(VALUATION_DIR, f"valuation_{code_key}_*.json")
    if not path:
        return {}, None
    return read_json(path, {}), path


def report_by_code(report_path: Path | None) -> dict[str, dict[str, Any]]:
    if not report_path:
        return {}
    report = read_json(report_path, {})
    quotes = report.get("monitored_quotes", [])
    result = {}
    for item in quotes:
        code = suffix_for_code(str(item.get("code", "")))
        if code:
            result[code] = item
    return result


def date_age_days(date_text: str | None, basis_date: str) -> int | None:
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


def check_updates(basis_date: str, intraday_report: Path | None, stale_days: int) -> dict[str, Any]:
    targets = collect_targets()
    intraday_quotes = report_by_code(intraday_report)
    items = []
    for code, target in sorted(targets.items()):
        valuation, valuation_path = latest_valuation_for(code)
        intraday = intraday_quotes.get(code, {})
        reasons = []
        severity = "ok"
        if not valuation_path:
            reasons.append("缺少估值报告")
            severity = "missing"
        else:
            price_date = valuation.get("reference_metrics", {}).get("price_date") or valuation.get("basis_date")
            age = date_age_days(str(price_date) if price_date else None, basis_date)
            if age is None:
                reasons.append("估值报告缺少可解析的基准日")
                severity = "update"
            elif age > stale_days:
                reasons.append(f"估值基准日 {price_date} 距离检查基准日 {basis_date} 已超过 {stale_days} 天")
                severity = "update"

        if intraday.get("valuation_zone_changed"):
            if intraday.get("allocation_bucket") != "cash_short":
                report_zone = intraday.get("valuation_report_zone", {}).get("label")
                live_zone = intraday.get("realtime_valuation_zone", {}).get("label")
                reasons.append(f"实时价格已跨估值区：报告 {report_zone or '-'}，实时 {live_zone or '-'}")
                severity = "update"

        if reasons:
            items.append(
                {
                    "code": code,
                    "name": target.get("name", ""),
                    "sources": sorted(set(target.get("sources", []))),
                    "severity": severity,
                    "reasons": reasons,
                    "latest_valuation": rel_path(valuation_path) if valuation_path else None,
                    "suggested_prompt": f"是否更新 {code} {target.get('name', '')} 的估值报告？",
                }
            )

    return {
        "module": "valuation_update_check",
        "generated_at": datetime.now().strftime("%Y-%m-%d_%H%M%S"),
        "basis_date": basis_date,
        "scope": "latest_portfolio_and_intraday_rules",
        "update_required_count": len(items),
        "items": items,
        "summary": "无估值报告缺失或应更新项。" if not items else f"发现 {len(items)} 个估值报告缺失或应更新项，分析前应提示用户是否更新。",
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--basis-date", help="Check basis date in YYYYMMDD. Defaults to latest complete trading day when Tushare is available.")
    parser.add_argument("--intraday-report", type=Path, help="Optional intraday once-json/report JSON for live zone-change checks.")
    parser.add_argument("--stale-days", type=int, default=1, help="Flag valuation reports older than this many calendar days.")
    args = parser.parse_args(argv)

    basis_date = args.basis_date or latest_complete_trade_date()
    report = check_updates(basis_date, args.intraday_report, args.stale_days)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["update_required_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
