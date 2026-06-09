#!/usr/bin/env python3
"""Check that executable action-plan rows do not bypass ResearchFirst gates."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from project_utils import ROOT, abs_path, latest_for_module, load_latest_index, read_json


EXECUTABLE_ACTIONS = {"buy", "add", "reduce", "sell"}
CASH_SHORT_CODES = {"511360", "511360.SH"}
LIQUIDITY_GATE_REGISTRY = ROOT / "research" / "config" / "liquidity_gate_registry.json"
LIQUIDITY_PASS_WORDS = {"强", "available", "pass", "ok", "active", "sufficient", "high"}
LIQUIDITY_FAIL_WORDS = {"unknown", "fail", "blocked", "insufficient", "illiquid", "异常"}


def plain_code(code: Any) -> str:
    return re.sub(r"\D", "", str(code or ""))


def load_registries() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for rel, key in [("research/etfs/etf_registry.json", "etfs"), ("research/stocks/stock_registry.json", "stocks")]:
        data = read_json(ROOT / rel, {})
        for item in data.get(key, []):
            code = plain_code(item.get("code"))
            if code:
                row = dict(item)
                row["_registry"] = rel
                result[code] = row
    return result


def load_liquidity_registry() -> dict[str, dict[str, Any]]:
    data = read_json(LIQUIDITY_GATE_REGISTRY, {})
    instruments = data.get("instruments") or {}
    result: dict[str, dict[str, Any]] = {}
    for key, row in instruments.items():
        code = plain_code(row.get("code") or key)
        if code:
            result[code] = dict(row)
    return result


def has_valuation(code: str) -> bool:
    patterns = [f"valuation_{code}_*.json", f"valuation_{code}_*.md"]
    for pattern in patterns:
        if any((ROOT / "research" / "valuations").glob(pattern)):
            return True
    return False


def profile_exists(row: dict[str, Any]) -> bool:
    for field in ["last_profile_json", "last_profile_file"]:
        value = row.get(field)
        if value and (ROOT / value).exists():
            return True
    return False


def profile_path(row: dict[str, Any]) -> Path | None:
    for field in ["last_profile_json", "last_profile_file"]:
        value = row.get(field)
        if value and (ROOT / value).exists():
            return ROOT / value
    return None


def read_profile_text(row: dict[str, Any]) -> str:
    path = profile_path(row)
    if not path:
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def read_profile_json(row: dict[str, Any]) -> dict[str, Any]:
    path = profile_path(row)
    if not path or path.suffix.lower() != ".json":
        return {}
    try:
        data = read_json(path, {})
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def explicit_liquidity_pass(row: dict[str, Any] | None) -> bool | None:
    if not row:
        return None
    explicit = str(
        row.get("liquidity_status")
        or row.get("liquidity_pass")
        or row.get("liquidity_quality")
        or ""
    ).lower()
    if explicit:
        return explicit in {"pass", "ok", "strong", "available", "true"}
    return None


def has_liquidity(row: dict[str, Any], liquidity_row: dict[str, Any] | None = None) -> bool:
    explicit = explicit_liquidity_pass(liquidity_row)
    if explicit is not None:
        return explicit
    explicit = explicit_liquidity_pass(row)
    if explicit is not None:
        return explicit

    data = read_profile_json(row)
    trend_liquidity = ((data.get("trend_and_flow") or {}).get("turnover_liquidity") or {})
    if str(trend_liquidity.get("status") or "").lower() in {"available", "pass", "ok"}:
        return True
    score_liquidity = ((data.get("scores") or {}).get("liquidity_turnover") or {})
    if (score_liquidity.get("score") or 0) and "evidence" in score_liquidity:
        return True

    text = read_profile_text(row)
    if not text:
        return False
    lowered = text.lower()
    if "liquidity" not in lowered and "流动性" not in text and "成交额" not in text:
        return False
    if any(word in lowered or word in text for word in LIQUIDITY_FAIL_WORDS):
        return False
    return any(word in lowered or word in text for word in LIQUIDITY_PASS_WORDS)


def cash_equivalent_gate(row: dict[str, Any] | None, liquidity_row: dict[str, Any] | None) -> list[str]:
    if not row:
        return ["cash-equivalent code not found in ETF/stock registry"]
    errors: list[str] = []
    text = read_profile_text(row)
    code = plain_code(row.get("code"))
    if not profile_exists(row):
        errors.append("cash-equivalent profile file missing from registry")
    valuation_status = str((liquidity_row or {}).get("valuation_status") or "").lower()
    valuation_source = (liquidity_row or {}).get("valuation_source")
    valuation_source_ok = bool(valuation_source and (ROOT / str(valuation_source)).exists())
    if valuation_status not in {"pass", "ok", "available", "true"} and not (code and has_valuation(code)):
        errors.append("cash-equivalent valuation gate missing or not pass")
    if valuation_status in {"pass", "ok", "available", "true"} and not valuation_source_ok:
        errors.append("cash-equivalent valuation source missing from registry")
    if not has_liquidity(row, liquidity_row):
        errors.append("cash-equivalent liquidity gate missing or not pass")
    duration_ok = bool((liquidity_row or {}).get("duration_boundary_confirmed"))
    if not duration_ok and "短融" not in text and "short-term" not in text.lower() and "short-duration" not in text.lower():
        errors.append("cash-equivalent duration boundary not confirmed")
    risk_ok = all(bool((liquidity_row or {}).get(field)) for field in [
        "interest_rate_risk_disclosed",
        "credit_risk_disclosed",
        "liquidity_risk_disclosed",
    ])
    if not risk_ok and not all(word in text for word in ["利率", "信用", "流动性"]):
        errors.append("cash-equivalent interest-rate/credit/liquidity risks not disclosed")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, help="Specific action_plan JSON. Defaults to latest action_plan.")
    args = parser.parse_args(argv)
    if args.path:
        plan_path = args.path if args.path.is_absolute() else ROOT / args.path
    else:
        latest = latest_for_module("action_plan", load_latest_index())
        if not latest:
            print("[FAIL] latest action_plan not found")
            return 1
        plan_path = abs_path(latest["path"])
    plan = read_json(plan_path, {})
    intraday_ref = latest_for_module("intraday_rules")
    intraday = read_json(abs_path(intraday_ref["path"]), {}) if intraday_ref else {}
    market_gate = ((intraday.get("staleness") or {}).get("status") or "").lower()
    registries = load_registries()
    liquidity_registry = load_liquidity_registry()
    errors: list[str] = []

    for idx, action in enumerate(plan.get("actions", [])):
        action_type = str(action.get("action_type") or "").lower()
        if action_type not in EXECUTABLE_ACTIONS:
            continue
        subject = action.get("subject") or {}
        code = plain_code(subject.get("code"))
        bucket = str(action.get("bucket_role") or "").lower()
        if not code:
            continue
        label = f"actions[{idx}] {action_type} {subject.get('code')} {subject.get('name')}"
        if code in {plain_code(item) for item in CASH_SHORT_CODES} or bucket in {"cash_short", "bond_cash"}:
            for item in cash_equivalent_gate(registries.get(code), liquidity_registry.get(code)):
                errors.append(f"{label}: {item}")
            continue
        row = registries.get(code)
        if not row:
            errors.append(f"{label}: code not found in ETF/stock registry")
            continue
        status = str(row.get("status") or "").lower()
        if status != "profile_generated":
            errors.append(f"{label}: registry status={status}, expected profile_generated")
        if not profile_exists(row):
            errors.append(f"{label}: profile file missing from registry")
        if not has_valuation(code):
            errors.append(f"{label}: valuation report missing")
        if not has_liquidity(row, liquidity_registry.get(code)):
            errors.append(f"{label}: liquidity gate missing or not pass")
        if action_type in {"buy", "add"} and market_gate in {"degraded", "stale", "blocked"}:
            errors.append(f"{label}: buy/add blocked while intraday_rules staleness={market_gate}")

    if errors:
        print("ResearchFirst gate: FAIL")
        print(f"File: {plan_path.relative_to(ROOT).as_posix()}")
        for item in errors:
            print(f"[FAIL] {item}")
        return 1
    print("ResearchFirst gate: OK")
    print(f"File: {plan_path.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
