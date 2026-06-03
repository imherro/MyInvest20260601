#!/usr/bin/env python3
"""Lightweight repository checks for MyInvest20260601."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TIMESTAMP = r"\d{4}-\d{2}-\d{2}_\d{6}"

RESEARCH_NAME_PATTERNS = {
    "market": re.compile(rf"^market_score_{TIMESTAMP}\.(md|json)$"),
    "themes": re.compile(rf"^theme_review_{TIMESTAMP}\.(md|json)$"),
    "etfs": re.compile(rf"^.+_{TIMESTAMP}\.(md|json)$"),
    "stocks": re.compile(rf"^.+_{TIMESTAMP}\.(md|json)$"),
    "portfolio": re.compile(
        rf"^(portfolio_snapshot|research_backlog)_{TIMESTAMP}\.(md|json)$"
    ),
    "allocation": re.compile(rf"^target_allocation_{TIMESTAMP}\.(md|json)$"),
    "actions": re.compile(
        rf"^action_plan_{TIMESTAMP}(_[A-Za-z0-9_-]+)?\.(md|json)$"
    ),
    "alerts": re.compile(rf"^intraday_alert_{TIMESTAMP}\.(md|json)$"),
    "checks": re.compile(rf"^premarket_check_{TIMESTAMP}\.(md|json)$"),
    "reviews": re.compile(
        rf"^post_market_review_{TIMESTAMP}(_[A-Za-z0-9_-]+)?\.(md|json)$"
    ),
}

FIXED_RESEARCH_FILES = {
    "themes/theme_registry.json",
    "etfs/etf_registry.json",
    "stocks/stock_registry.json",
    "logs/decision_log.md",
    "portfolio/current_holdings_template.md",
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


def check_json(findings: list[Finding]) -> None:
    for path in sorted(ROOT.rglob("*.json")):
        if ".git" in path.parts:
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
        if not path.is_file() or path.name == ".gitkeep":
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


def main() -> int:
    findings: list[Finding] = []
    check_required_files(findings)
    check_env(findings)
    check_json(findings)
    check_research_names(findings)

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
