#!/usr/bin/env python3
"""Shared project helpers for MyInvest engineering checks."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research"
LATEST_INDEX = RESEARCH / "latest_index.json"
MARKET_POSITION_MAPPING = RESEARCH / "config" / "market_position_mapping.json"
TIMESTAMP_RE = re.compile(r"(\d{4}-\d{2}-\d{2}_\d{6})")

MODULE_ALIASES = {
    "MARKET_POSITION": "market_score",
    "market_position": "market_score",
    "market_score": "market_score",
    "THEME_RESEARCH": "theme_review",
    "theme_research": "theme_review",
    "theme_review": "theme_review",
    "theme_leaders": "theme_leaders",
    "target_allocation_reference": "target_allocation",
    "target_allocation": "target_allocation",
    "portfolio_analysis": "portfolio_snapshot",
    "portfolio_snapshot": "portfolio_snapshot",
    "portfolio_research_backlog": "research_backlog",
    "research_backlog": "research_backlog",
    "portfolio_cleanup_review": "portfolio_cleanup_review",
    "current_holding_research_quality_audit": "research_quality_audit",
    "valuation_report": "valuation_report",
    "intraday_rules": "intraday_rules",
    "intraday_alert": "intraday_alerts",
    "intraday_analysis": "intraday_alerts",
    "intraday_alerts": "intraday_alerts",
    "premarket_check": "premarket_check",
    "PREMARKET_CHECK": "premarket_check",
    "action_plan": "action_plan",
    "post_market_review": "post_market_review",
    "staleness_check": "staleness_check",
    "ETF_RESEARCH": "etf_profile",
    "etf_research": "etf_profile",
    "stock_profile": "stock_profile",
    "STOCK_RESEARCH": "stock_profile",
    "stock_research": "stock_profile",
    "etf_profile": "etf_profile",
}

MODULE_BY_DIR = {
    "market": "market_score",
    "themes": "theme_review",
    "theme_leaders": "theme_leaders",
    "allocation": "target_allocation",
    "portfolio": "portfolio_snapshot",
    "valuations": "valuation_report",
    "alerts": "intraday_rules",
    "checks": "premarket_check",
    "actions": "action_plan",
    "reviews": "post_market_review",
    "stocks": "stock_profile",
    "etfs": "etf_profile",
}


def rel_path(path: Path | str) -> str:
    p = Path(path)
    if not p.is_absolute():
        return p.as_posix()
    return p.relative_to(ROOT).as_posix()


def abs_path(path: Path | str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pct_range(text: Any, default: tuple[float, float] = (0.0, 0.0)) -> tuple[float, float]:
    try:
        left, right = str(text).replace("%", "").split("-", 1)
        return float(left), float(right)
    except (TypeError, ValueError):
        return default


def format_pct_range(low: float, high: float) -> str:
    return f"{low:g}%-{high:g}%"


def market_position_for_score(score: Any) -> dict[str, Any] | None:
    try:
        value = float(score)
    except (TypeError, ValueError):
        return None
    config = read_json(MARKET_POSITION_MAPPING, {})
    for row in config.get("ranges", []):
        low = float(row.get("score_min", 0))
        high = float(row.get("score_max", 0))
        if low <= value <= high:
            return dict(row)
    return None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_module(value: Any, path: Path | None = None) -> str:
    text = str(value or "").strip()
    if text in MODULE_ALIASES:
        return MODULE_ALIASES[text]
    lowered = text.lower()
    if lowered in MODULE_ALIASES:
        return MODULE_ALIASES[lowered]
    if text:
        return text
    if path is not None:
        try:
            parts = path.relative_to(RESEARCH).parts
        except ValueError:
            parts = ()
        if parts:
            return MODULE_BY_DIR.get(parts[0], text or parts[0])
    return text or "unknown"


def timestamp_from_name(path: Path) -> str | None:
    match = TIMESTAMP_RE.search(path.name)
    return match.group(1) if match else None


def parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d_%H%M%S", "%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def sort_key(record: dict[str, Any]) -> tuple[datetime, datetime, str]:
    generated = parse_dt(record.get("generated_at")) or datetime.min
    basis = parse_dt(record.get("basis_trade_date") or record.get("basis_date") or record.get("date")) or datetime.min
    return generated, basis, str(record.get("path", ""))


def quality_status(data: dict[str, Any]) -> str:
    quality = data.get("quality") or {}
    if isinstance(quality, dict) and quality.get("status"):
        return str(quality["status"])
    return "legacy_unknown"


def staleness_status(data: dict[str, Any]) -> str:
    staleness = data.get("staleness") or {}
    if isinstance(staleness, dict) and staleness.get("status"):
        return str(staleness["status"])
    return "legacy_unknown"


def document_record(path: Path) -> dict[str, Any] | None:
    try:
        data = read_json(path, {})
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    generated_at = data.get("generated_at") or data.get("last_updated") or timestamp_from_name(path)
    basis = data.get("basis_trade_date") or data.get("basis_date") or data.get("date")
    module = normalize_module(data.get("module"), path)
    return {
        "module": module,
        "code": data.get("code") or data.get("ts_code") or data.get("security_code"),
        "name": data.get("name") or data.get("security_name"),
        "path": rel_path(path),
        "generated_at": generated_at,
        "basis_trade_date": basis,
        "sha256": file_sha256(path),
        "quality": {"status": quality_status(data)},
        "staleness": {"status": staleness_status(data)},
    }


def scan_research_json() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(RESEARCH.rglob("*.json")):
        if path.name == "latest_index.json" or "runtime" in path.parts:
            continue
        record = document_record(path)
        if record is not None:
            records.append(record)
    return records


def build_latest_index() -> dict[str, Any]:
    files = scan_research_json()
    modules: dict[str, dict[str, Any]] = {}
    for record in files:
        module = record["module"]
        if module not in modules or sort_key(record) > sort_key(modules[module]):
            modules[module] = record
    generated_dt = datetime.now()
    for record in modules.values():
        record_dt = parse_dt(record.get("generated_at"))
        if record_dt and record_dt > generated_dt:
            generated_dt = record_dt
    return {
        "module": "latest_index",
        "version": "1.0",
        "generated_at": generated_dt.strftime("%Y-%m-%d_%H%M%S"),
        "selection_rule": "latest by generated_at, then basis_trade_date/date, then path; never by filesystem mtime",
        "modules": modules,
        "files": files,
    }


def load_latest_index() -> dict[str, Any]:
    if LATEST_INDEX.exists():
        return read_json(LATEST_INDEX, {})
    return build_latest_index()


def latest_for_module(module: str, index: dict[str, Any] | None = None) -> dict[str, Any] | None:
    index = index or load_latest_index()
    return (index.get("modules") or {}).get(normalize_module(module))


def path_record(path: str | Path, index: dict[str, Any] | None = None) -> dict[str, Any] | None:
    index = index or load_latest_index()
    target = rel_path(abs_path(path))
    for record in index.get("files", []):
        if record.get("path") == target:
            return record
    return document_record(abs_path(path))
