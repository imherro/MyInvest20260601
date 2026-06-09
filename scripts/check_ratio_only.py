#!/usr/bin/env python3
"""Check that the latest action plan keeps the ratio-only privacy boundary."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from project_utils import ROOT, abs_path, latest_for_module, load_latest_index, read_json


FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(amount|market_value|profit_amount|total_amount|total_asset|share_count|shares|quantity|qty|available_qty)($|_)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    r"(总金额|单仓金额|盈亏金额|成本金额|现金金额|总资产|市值|股数|可用数量|账号全号|"
    r"\bmarket value\b|\bprofit amount\b|\btotal amount\b|\btotal asset\b|\bshare count\b|\bshares\b|\bquantity\b|\bavailable qty\b|"
    r"\d+(?:\.\d+)?\s*(?:元|万元|亿元|股))",
    re.IGNORECASE,
)
ALLOWED_KEY_PATHS = {
    "$.privacy_policy",
    "$.triggered_hard_constraints",
    "$.risks",
}


def walk(value: Any, path: str, findings: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_path = f"{path}.{key}"
            if FORBIDDEN_KEY_RE.search(str(key)) and key_path not in ALLOWED_KEY_PATHS:
                findings.append(f"forbidden key {key_path}")
            walk(item, key_path, findings)
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            walk(item, f"{path}[{idx}]", findings)
    elif isinstance(value, str):
        if FORBIDDEN_VALUE_RE.search(value):
            findings.append(f"forbidden text at {path}: {value[:120]}")


def check_file(path: Path) -> list[str]:
    data = read_json(path, {})
    findings: list[str] = []
    walk(data, "$", findings)
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, help="Specific JSON file to check. Defaults to latest action_plan.")
    args = parser.parse_args(argv)
    if args.path:
        path = args.path if args.path.is_absolute() else ROOT / args.path
    else:
        latest = latest_for_module("action_plan", load_latest_index())
        if not latest:
            print("[FAIL] latest action_plan not found")
            return 1
        path = abs_path(latest["path"])
    findings = check_file(path)
    if findings:
        print("Ratio-only check: FAIL")
        print(f"File: {path.relative_to(ROOT).as_posix()}")
        for item in findings:
            print(f"[FAIL] {item}")
        return 1
    print("Ratio-only check: OK")
    print(f"File: {path.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
