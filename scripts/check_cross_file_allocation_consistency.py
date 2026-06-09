#!/usr/bin/env python3
"""Check allocation bucket consistency across target allocation and intraday rules."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from project_utils import ROOT, abs_path, latest_for_module, load_latest_index, read_json


TOLERANCE_PP = 0.05


def bucket_rows(data: dict[str, Any], source: str) -> dict[str, dict[str, float]]:
    if source == "target_allocation":
        rows = ((data.get("actual_allocation_overlay") or {}).get("buckets")) or []
    else:
        rows = ((data.get("allocation_map") or {}).get("buckets")) or []
    result: dict[str, dict[str, float]] = {}
    for row in rows:
        key = row.get("key")
        if not key:
            continue
        result[key] = {
            "target_pct": float(row.get("target_pct") or 0),
            "actual_pct": float(row.get("actual_pct") or 0),
            "gap_pct": float(row.get("gap_pct") or 0),
        }
    return result


def main() -> int:
    index = load_latest_index()
    allocation_ref = latest_for_module("target_allocation", index)
    if not allocation_ref:
        print("[FAIL] latest target_allocation not found")
        return 1
    allocation = read_json(abs_path(allocation_ref["path"]), {})
    rules_path = ROOT / "research" / "alerts" / "intraday_rules.json"
    rules = read_json(rules_path, {})
    errors: list[str] = []

    rule_target = (rules.get("allocation_map") or {}).get("target_allocation_file")
    if rule_target and rule_target != allocation_ref["path"]:
        errors.append(f"intraday_rules target_allocation_file={rule_target} but latest={allocation_ref['path']}")

    allocation_rows = bucket_rows(allocation, "target_allocation")
    rule_rows = bucket_rows(rules, "intraday_rules")
    for key in sorted(set(allocation_rows) | set(rule_rows)):
        left = allocation_rows.get(key)
        right = rule_rows.get(key)
        if left is None or right is None:
            errors.append(f"bucket {key} missing from {'target_allocation' if left is None else 'intraday_rules'}")
            continue
        for field in ["target_pct", "actual_pct", "gap_pct"]:
            if abs(left[field] - right[field]) > TOLERANCE_PP:
                errors.append(f"bucket {key} {field}: target_allocation={left[field]:.4f}, intraday_rules={right[field]:.4f}")

    if errors:
        print("Allocation consistency: FAIL")
        for item in errors:
            print(f"[FAIL] {item}")
        return 1
    print("Allocation consistency: OK")
    print(json.dumps({"target_allocation": allocation_ref["path"], "intraday_rules": rules_path.relative_to(ROOT).as_posix()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
