#!/usr/bin/env python3
"""Check whether downstream research artifacts are stale against latest_index."""

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
    load_latest_index,
    normalize_module,
    parse_dt,
    path_record,
    read_json,
    rel_path,
    write_json,
)


REPORT_DIR = ROOT / "research" / "checks"
INTRADAY_RULES = ROOT / "research" / "alerts" / "intraday_rules.json"


def is_json_path(value: Any) -> bool:
    return isinstance(value, str) and value.replace("\\", "/").startswith("research/") and value.endswith(".json")


def dependency_paths(data: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    deps = data.get("dependencies") or {}
    if isinstance(deps, dict):
        for item in deps.get("required", []):
            if isinstance(item, dict) and is_json_path(item.get("path")):
                paths.append(str(item["path"]))
            elif is_json_path(item):
                paths.append(str(item))
    for item in data.get("data_sources", []) or []:
        if is_json_path(item):
            paths.append(str(item))
        elif isinstance(item, dict) and is_json_path(item.get("path")):
            paths.append(str(item["path"]))
    for key in ["source_plan", "read_files"]:
        for item in data.get(key, []) or []:
            if is_json_path(item):
                paths.append(str(item))
    allocation = data.get("allocation_map") or {}
    if isinstance(allocation, dict):
        for key in ["target_allocation_file", "portfolio_snapshot_file"]:
            if is_json_path(allocation.get(key)):
                paths.append(str(allocation[key]))
    return sorted(dict.fromkeys(paths))


def equity_range_from_market_score(data: dict[str, Any]) -> tuple[float | None, float | None]:
    text = (data.get("summary") or {}).get("equity_allocation_range")
    if not isinstance(text, str) or "-" not in text:
        return None, None
    left, right = text.replace("%", "").split("-", 1)
    try:
        return float(left), float(right)
    except ValueError:
        return None, None


def pct_text(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).replace("%", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def check_allocation_vs_market(index: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    market = latest_for_module("market_score", index)
    allocation = latest_for_module("target_allocation", index)
    if not market or not allocation:
        return findings
    market_data = read_json(abs_path(market["path"]), {})
    allocation_data = read_json(abs_path(allocation["path"]), {})
    low, high = equity_range_from_market_score(market_data)
    center = pct_text((allocation_data.get("summary") or {}).get("recommended_equity_center"))
    if low is not None and high is not None and center is not None and not (low <= center <= high):
        findings.append(
            {
                "level": "STALE",
                "path": allocation["path"],
                "reason": "target_allocation equity center is outside latest market_score equity range",
                "latest_market_score": market["path"],
                "market_equity_range": f"{low:g}-{high:g}%",
                "target_equity_center": center,
            }
        )
    return findings


def compare_dependency(current: dict[str, Any], dep_path: str, index: dict[str, Any]) -> dict[str, Any] | None:
    full = abs_path(dep_path)
    if not full.exists():
        return {"level": "ERROR", "path": current["path"], "dependency": dep_path, "reason": "dependency path does not exist"}
    dep = path_record(dep_path, index)
    if dep is None:
        return {"level": "WARN", "path": current["path"], "dependency": dep_path, "reason": "dependency metadata unavailable"}
    latest = latest_for_dependency(dep, index)
    if latest and latest.get("path") != dep["path"]:
        return {
            "level": "STALE",
            "path": current["path"],
            "dependency": dep_path,
            "dependency_module": dep["module"],
            "latest_path": latest["path"],
            "reason": "dependency is not latest for its module",
        }
    dep_dt = parse_dt(dep.get("generated_at"))
    cur_dt = parse_dt(current.get("generated_at"))
    if dep_dt and cur_dt and dep_dt > cur_dt:
        return {
            "level": "STALE",
            "path": current["path"],
            "dependency": dep_path,
            "reason": "dependency generated later than downstream file",
        }
    return None


def latest_for_dependency(dep: dict[str, Any], index: dict[str, Any]) -> dict[str, Any] | None:
    module = dep.get("module")
    code = dep.get("code")
    subject_scoped_modules = {"valuation_report", "stock_profile", "etf_profile"}
    if module in subject_scoped_modules and code:
        candidates = [
            item
            for item in index.get("files", [])
            if item.get("module") == module and str(item.get("code")) == str(code)
        ]
        if candidates:
            return max(candidates, key=lambda item: (parse_dt(item.get("generated_at")) or datetime.min, parse_dt(item.get("basis_trade_date")) or datetime.min, item.get("path", "")))
    return latest_for_module(str(module), index)


def check_downstream(index: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    records_by_path = {item["path"]: item for item in index.get("files", [])}
    active_paths = {item.get("path") for item in (index.get("modules") or {}).values()}
    active_paths.add("research/alerts/intraday_rules.json")
    for current in records_by_path.values():
        if current.get("path") not in active_paths:
            continue
        path = abs_path(current["path"])
        try:
            data = read_json(path, {})
        except Exception as exc:  # noqa: BLE001
            findings.append({"level": "ERROR", "path": current["path"], "reason": f"cannot parse json: {exc}"})
            continue
        if not isinstance(data, dict):
            continue
        for dep_path in dependency_paths(data):
            issue = compare_dependency(current, dep_path, index)
            if issue:
                findings.append(issue)
    findings.extend(check_allocation_vs_market(index))
    return findings


def cascade_findings(index: dict[str, Any], findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stale_paths = {item.get("path") for item in findings if item.get("level") in {"ERROR", "STALE"}}
    allocation = latest_for_module("target_allocation", index)
    portfolio = latest_for_module("portfolio_snapshot", index)
    intraday = latest_for_module("intraday_rules", index)
    cascaded: list[dict[str, Any]] = []
    if allocation and allocation["path"] in stale_paths and intraday:
        cascaded.append(
            {
                "level": "STALE",
                "path": intraday["path"],
                "reason": "latest target_allocation is stale, so active intraday_rules must be degraded",
                "dependency": allocation["path"],
            }
        )
    if intraday and portfolio:
        rules = read_json(abs_path(intraday["path"]), {})
        linked = ((rules.get("allocation_map") or {}).get("portfolio_snapshot_file"))
        if linked and linked != portfolio["path"]:
            cascaded.append(
                {
                    "level": "STALE",
                    "path": intraday["path"],
                    "reason": "intraday_rules does not reference latest portfolio_snapshot",
                    "dependency": linked,
                    "latest_path": portfolio["path"],
                }
            )
    return findings + cascaded


def status_from_findings(findings: list[dict[str, Any]], path: str | None = None) -> str:
    scoped = [item for item in findings if path is None or item.get("path") == path]
    if any(item.get("level") == "ERROR" for item in scoped):
        return "blocked"
    if any(item.get("level") == "STALE" for item in scoped):
        return "stale"
    if any(item.get("level") == "WARN" for item in scoped):
        return "degraded"
    return "fresh"


def build_report(index: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "module": "staleness_check",
        "version": "1.0",
        "generated_at": datetime.now().strftime("%Y-%m-%d_%H%M%S"),
        "summary": {
            "status": status_from_findings(findings),
            "errors": sum(1 for item in findings if item.get("level") == "ERROR"),
            "stale": sum(1 for item in findings if item.get("level") == "STALE"),
            "warnings": sum(1 for item in findings if item.get("level") == "WARN"),
        },
        "latest_modules": index.get("modules", {}),
        "findings": findings,
    }


def render_markdown(report: dict[str, Any]) -> str:
    rows = []
    for item in report.get("findings", []):
        rows.append(
            "| {level} | {path} | {reason} | {dependency} | {latest} |".format(
                level=item.get("level", ""),
                path=item.get("path", ""),
                reason=str(item.get("reason", "")).replace("|", "/"),
                dependency=item.get("dependency", ""),
                latest=item.get("latest_path", ""),
            )
        )
    if not rows:
        rows.append("| OK | - | no stale dependencies detected | - | - |")
    summary = report["summary"]
    return f"""# 工程过期检查

生成时间：{report['generated_at']}

## 汇总

| 状态 | ERROR | STALE | WARN |
| --- | ---: | ---: | ---: |
| {summary['status']} | {summary['errors']} | {summary['stale']} | {summary['warnings']} |

## 发现

| 级别 | 文件 | 原因 | 引用 | 最新 |
| --- | --- | --- | --- | --- |
{chr(10).join(rows)}
"""


def update_intraday_rules(report: dict[str, Any]) -> bool:
    if not INTRADAY_RULES.exists():
        return False
    data = read_json(INTRADAY_RULES, {})
    data["generated_at"] = report["generated_at"]
    data["last_updated"] = report["generated_at"][:10]
    rule_path = rel_path(INTRADAY_RULES)
    findings = [item for item in report.get("findings", []) if item.get("path") == rule_path]
    status = status_from_findings(report.get("findings", []), rule_path)
    data["staleness"] = {
        "status": status,
        "checked_at": report["generated_at"],
        "mode": "degraded_observation_only" if status in {"stale", "blocked", "degraded"} else "fresh",
        "reason": "当前盘中规则引用链存在过期或质量问题；stale/blocked/degraded 时禁止买入/加仓类提醒。",
        "findings": findings[:20],
    }
    write_json(INTRADAY_RULES, data)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild-index", action="store_true", help="Rebuild research/latest_index.json before checking.")
    parser.add_argument("--write-report", action="store_true", help="Write Markdown and JSON reports under research/checks.")
    parser.add_argument("--update-intraday-rules", action="store_true", help="Write current staleness status into intraday_rules.json.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when stale dependencies are found.")
    args = parser.parse_args(argv)

    index = build_latest_index() if args.rebuild_index else load_latest_index()
    findings = cascade_findings(index, check_downstream(index))
    report = build_report(index, findings)
    if args.write_report:
        ts = report["generated_at"]
        write_json(REPORT_DIR / f"staleness_check_{ts}.json", report)
        (REPORT_DIR / f"staleness_check_{ts}.md").write_text(render_markdown(report), encoding="utf-8")
    if args.update_intraday_rules:
        update_intraday_rules(report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    if args.strict and report["summary"]["status"] != "fresh":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
