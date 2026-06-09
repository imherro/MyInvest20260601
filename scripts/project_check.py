#!/usr/bin/env python3
"""Lightweight repository checks for MyInvest20260601."""

from __future__ import annotations

import json
import re
import sys
from importlib.util import find_spec
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from check_staleness import build_report as build_stale_report
from check_staleness import cascade_findings, check_downstream
from project_utils import abs_path, build_latest_index, latest_for_module, read_json


ROOT = Path(__file__).resolve().parents[1]
TIMESTAMP = r"\d{4}-\d{2}-\d{2}_\d{6}"

RESEARCH_NAME_PATTERNS = {
    "market": re.compile(rf"^market_score_{TIMESTAMP}\.(md|json)$"),
    "themes": re.compile(rf"^theme_review_{TIMESTAMP}\.(md|json)$"),
    "theme_leaders": re.compile(rf"^theme_leaders_{TIMESTAMP}\.(md|json)$"),
    "etfs": re.compile(rf"^.+_{TIMESTAMP}\.(md|json)$"),
    "stocks": re.compile(rf"^.+_{TIMESTAMP}\.(md|json)$"),
    "portfolio": re.compile(
        rf"^(portfolio_snapshot|research_backlog)_{TIMESTAMP}\.(md|json)$"
    ),
    "allocation": re.compile(rf"^target_allocation_{TIMESTAMP}\.(md|json)$"),
    "actions": re.compile(
        rf"^action_plan_{TIMESTAMP}(_[A-Za-z0-9_-]+)?\.(md|json)$"
    ),
    "briefings": re.compile(rf"^strategy_briefing_{TIMESTAMP}\.(md|json)$"),
    "alerts": re.compile(rf"^intraday_alert_{TIMESTAMP}\.(md|json)$"),
    "valuations": re.compile(rf"^valuation_.+_{TIMESTAMP}\.(md|json)$"),
    "checks": re.compile(
        rf"^(premarket_check|staleness_check|engineering_hardening_report)_{TIMESTAMP}\.(md|json)$"
    ),
    "reviews": re.compile(
        rf"^post_market_review_{TIMESTAMP}(_[A-Za-z0-9_-]+)?\.(md|json)$"
    ),
}

FIXED_RESEARCH_FILES = {
    "alerts/intraday_rules.json",
    "themes/theme_registry.json",
    "etfs/etf_registry.json",
    "stocks/stock_registry.json",
    "logs/decision_log.md",
    "portfolio/current_holdings_template.md",
    "config/bucket_registry.json",
    "latest_index.json",
}


@dataclass
class Finding:
    level: str
    message: str


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def check_env(findings: list[Finding]) -> None:
    env_path = ROOT / ".env"
    example_path = ROOT / ".env.example"

    if not example_path.exists():
        findings.append(Finding("FAIL", ".env.example is missing"))
        return

    if not env_path.exists():
        findings.append(
            Finding("WARN", ".env is missing; copy .env.example and set TUSHARE_TOKEN")
        )
        return

    token_found = False
    token_has_value = False
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() == "TUSHARE_TOKEN":
            token_found = True
            token_has_value = bool(value.strip())

    if not token_found:
        findings.append(Finding("WARN", ".env exists but TUSHARE_TOKEN is not defined"))
    elif not token_has_value:
        findings.append(Finding("WARN", ".env has an empty TUSHARE_TOKEN"))


def check_python_dependencies(findings: list[Finding]) -> None:
    required_packages = ["baostock", "fredapi", "pandas", "tushare", "yfinance"]
    for package in required_packages:
        if find_spec(package) is None:
            findings.append(
                Finding(
                    "WARN",
                    f"Python package {package} is not installed; run python -m pip install -r requirements.txt",
                )
            )


def check_json(findings: list[Finding]) -> None:
    for path in sorted(ROOT.rglob("*.json")):
        if ".git" in path.parts or "runtime" in path.relative_to(ROOT).parts:
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - report parser detail to user.
            findings.append(Finding("FAIL", f"{rel(path)} is not valid JSON: {exc}"))


def check_research_names(findings: list[Finding]) -> None:
    research_root = ROOT / "research"
    if not research_root.exists():
        findings.append(Finding("FAIL", "research/ directory is missing"))
        return

    for path in sorted(research_root.rglob("*")):
        if not path.is_file() or path.name in {".gitkeep", ".env"}:
            continue
        relative = rel(path)
        if relative.removeprefix("research/") in FIXED_RESEARCH_FILES:
            continue

        module = path.relative_to(research_root).parts[0]
        pattern = RESEARCH_NAME_PATTERNS.get(module)
        if pattern is None:
            findings.append(Finding("WARN", f"{relative} is in an unknown research module"))
            continue
        if not pattern.match(path.name):
            findings.append(
                Finding(
                    "FAIL",
                    f"{relative} does not follow timestamp naming rules",
                )
            )


def check_required_files(findings: list[Finding]) -> None:
    required = [
        "README.md",
        "docs/PROJECT_MEMORY.md",
        "docs/MODULES.md",
        "docs/RUNBOOK.md",
        "docs/DAILY_PROCESS.md",
        "docs/DATA_SOURCES.md",
        "docs/FILE_NAMING.md",
        "research/logs/decision_log.md",
    ]
    for item in required:
        if not (ROOT / item).exists():
            findings.append(Finding("FAIL", f"{item} is missing"))


def check_required_scripts(findings: list[Finding]) -> None:
    required = [
        "scripts/project_check.py",
        "scripts/build_latest_index.py",
        "scripts/check_staleness.py",
        "scripts/build_review_package.py",
        "scripts/generate_target_allocation.py",
        "scripts/generate_valuation_reports.py",
        "scripts/check_valuation_updates.py",
        "scripts/qmt_portfolio_snapshot.py",
        "scripts/intraday_monitor.py",
        "scripts/intraday_dashboard.py",
    ]
    for item in required:
        if not (ROOT / item).exists():
            findings.append(Finding("FAIL", f"{item} is missing"))


def as_float(value: Any) -> float | None:
    try:
        result = float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return None
    if result != result or result in {float("inf"), float("-inf")}:
        return None
    return result


def check_weight_math(findings: list[Finding]) -> None:
    portfolio = latest_for_module("portfolio_snapshot")
    if portfolio:
        data = read_json(abs_path(portfolio["path"]), {})
        weight_sum = as_float((data.get("summary") or {}).get("weight_sum_pct"))
        if weight_sum is not None and abs(weight_sum - 100.0) > 0.2:
            findings.append(Finding("FAIL", f"{portfolio['path']} weight_sum_pct={weight_sum} is outside 100±0.2"))
        for item in data.get("holdings", []):
            code = item.get("code", "")
            for field in ["cost_price", "current_price"]:
                value = as_float(item.get(field))
                if value is not None and value <= 0:
                    findings.append(Finding("FAIL", f"{portfolio['path']} {code} has invalid {field}={value}"))

    allocation = latest_for_module("target_allocation")
    if allocation:
        data = read_json(abs_path(allocation["path"]), {})
        groups = (((data.get("target_allocation") or {}).get("groups")) or [])
        total = sum(as_float(item.get("target_center_pct")) or 0.0 for item in groups)
        if groups and abs(total - 100.0) > 0.2:
            findings.append(Finding("WARN", f"{allocation['path']} group target_center_pct sums to {total:.2f}, not 100±0.2"))
        segments = (((data.get("ideal_allocation_map") or {}).get("segments")) or [])
        segment_total = sum(as_float(item.get("target_pct")) or 0.0 for item in segments)
        if segments and abs(segment_total - 100.0) > 0.2:
            findings.append(Finding("FAIL", f"{allocation['path']} ideal segments sum to {segment_total:.2f}, not 100±0.2"))


def check_intraday_references(findings: list[Finding], strict: bool) -> None:
    rules_path = ROOT / "research" / "alerts" / "intraday_rules.json"
    if not rules_path.exists():
        return
    rules = read_json(rules_path, {})
    references = []
    references.extend(item for item in rules.get("data_sources", []) if isinstance(item, str) and item.endswith(".json"))
    allocation_map = rules.get("allocation_map") or {}
    for key in ["target_allocation_file", "portfolio_snapshot_file"]:
        value = allocation_map.get(key)
        if isinstance(value, str) and value.endswith(".json"):
            references.append(value)
    for item in sorted(set(references)):
        if not (ROOT / item).exists():
            findings.append(Finding("FAIL", f"research/alerts/intraday_rules.json references missing file {item}"))

    stale_report = build_stale_report(build_latest_index(), cascade_findings(build_latest_index(), check_downstream(build_latest_index())))
    rule_issues = [item for item in stale_report.get("findings", []) if item.get("path") == "research/alerts/intraday_rules.json"]
    if rule_issues:
        level = "FAIL" if strict else "WARN"
        findings.append(
            Finding(
                level,
                f"research/alerts/intraday_rules.json is stale/degraded; run scripts/check_staleness.py and rebuild downstream rules before buy/add use",
            )
        )
    status = str((rules.get("staleness") or {}).get("status", ""))
    if status in {"stale", "blocked", "degraded"} and not rule_issues:
        findings.append(Finding("WARN", f"research/alerts/intraday_rules.json staleness.status={status}; check quality before action use"))


def main() -> int:
    strict = "--strict" in sys.argv
    findings: list[Finding] = []
    check_required_files(findings)
    check_required_scripts(findings)
    check_env(findings)
    check_python_dependencies(findings)
    check_json(findings)
    check_research_names(findings)
    check_weight_math(findings)
    check_intraday_references(findings, strict)

    failures = [item for item in findings if item.level == "FAIL"]
    warnings = [item for item in findings if item.level == "WARN"]

    print("MyInvest project check")
    print(f"Root: {ROOT}")
    print(f"Result: {len(failures)} FAIL, {len(warnings)} WARN")

    for item in findings:
        print(f"[{item.level}] {item.message}")

    if failures:
        return 1

    if not findings:
        print("[OK] No issues found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
