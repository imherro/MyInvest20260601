#!/usr/bin/env python3
"""Build the current-only SQLite read model for MyInvest."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "local" / "myinvest.sqlite"
TMP_DB_PATH = DB_PATH.with_suffix(".sqlite.tmp")
LATEST_INDEX = ROOT / "research" / "latest_index.json"

EXECUTABLE_ACTIONS = {"buy", "add", "reduce", "sell"}
CURRENT_CONFIG_MODULES = {
    "bucket_registry",
    "intraday_watchlist",
    "liquidity_gate_registry",
    "market_position_mapping",
}
REQUIRED_CURRENT_MODULES = {
    "action_plan",
    "target_allocation",
    "intraday_rules",
    "portfolio_snapshot",
    "market_score",
    "liquidity_gate_registry",
    "etf_registry",
}

FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(amount|market_value|profit_amount|total_amount|total_asset|share_count|shares|quantity|qty|"
    r"available_qty|available_quantity|account|account_masked|full_account|order|deal|fill|trade_amount|"
    r"cost_price|raw_cost_price|current_price)($|_)",
    re.IGNORECASE,
)
LOCAL_ABS_PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\)")
MONEY_OR_SHARE_RE = re.compile(r"[-+]?\d+(?:\.\d+)?\s*(?:元|万元|亿元|股|份|手)")


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE artifacts (
    id INTEGER PRIMARY KEY,
    module TEXT NOT NULL,
    code TEXT,
    name TEXT,
    path TEXT NOT NULL UNIQUE,
    generated_at TEXT,
    basis_trade_date TEXT,
    sha256 TEXT,
    quality_status TEXT,
    staleness_status TEXT,
    current_flag INTEGER NOT NULL DEFAULT 0,
    support_role TEXT,
    imported_at TEXT NOT NULL,
    json_payload TEXT NOT NULL
);

CREATE TABLE current_modules (
    module TEXT PRIMARY KEY,
    artifact_id INTEGER,
    code TEXT,
    name TEXT,
    path TEXT NOT NULL,
    generated_at TEXT,
    basis_trade_date TEXT,
    quality_status TEXT,
    staleness_status TEXT,
    imported_at TEXT NOT NULL,
    json_payload TEXT NOT NULL,
    FOREIGN KEY (artifact_id) REFERENCES artifacts(id)
);

CREATE TABLE market_scores (
    id INTEGER PRIMARY KEY,
    artifact_id INTEGER NOT NULL,
    date TEXT,
    basis_trade_date TEXT,
    market_state TEXT,
    opportunity_score REAL,
    crowding_penalty REAL,
    market_position_score REAL,
    equity_allocation_range TEXT,
    bond_cash_allocation_range TEXT,
    offensive_bucket_status TEXT,
    one_line_conclusion TEXT,
    json_payload TEXT NOT NULL,
    FOREIGN KEY (artifact_id) REFERENCES artifacts(id)
);

CREATE TABLE market_position_mappings (
    id INTEGER PRIMARY KEY,
    source_path TEXT NOT NULL,
    score_min REAL,
    score_max REAL,
    market_state TEXT,
    equity_allocation_range TEXT,
    bond_cash_allocation_range TEXT,
    offensive_bucket_status TEXT,
    json_payload TEXT NOT NULL
);

CREATE TABLE subjects (
    id INTEGER PRIMARY KEY,
    subject_key TEXT NOT NULL UNIQUE,
    code TEXT,
    name TEXT,
    subject_type TEXT,
    bucket_role TEXT,
    allocation_bucket TEXT,
    source_module TEXT,
    profile_status TEXT,
    valuation_status TEXT,
    liquidity_status TEXT,
    stance TEXT,
    json_payload TEXT NOT NULL
);

CREATE TABLE profiles (
    id INTEGER PRIMARY KEY,
    subject_id INTEGER,
    code TEXT NOT NULL,
    name TEXT,
    subject_type TEXT,
    profile_path TEXT NOT NULL,
    generated_at TEXT,
    basis_date TEXT,
    bucket_role TEXT,
    rating TEXT,
    action_rating TEXT,
    status TEXT,
    summary TEXT,
    json_payload TEXT NOT NULL,
    FOREIGN KEY (subject_id) REFERENCES subjects(id)
);

CREATE TABLE valuations (
    id INTEGER PRIMARY KEY,
    subject_id INTEGER,
    code TEXT NOT NULL,
    name TEXT,
    valuation_path TEXT NOT NULL,
    generated_at TEXT,
    basis_date TEXT,
    asset_type TEXT,
    group_name TEXT,
    role TEXT,
    confidence TEXT,
    security_stance TEXT,
    one_line_conclusion TEXT,
    json_payload TEXT NOT NULL,
    FOREIGN KEY (subject_id) REFERENCES subjects(id)
);

CREATE TABLE liquidity_gates (
    id INTEGER PRIMARY KEY,
    subject_id INTEGER,
    code TEXT NOT NULL,
    name TEXT,
    bucket_role TEXT,
    liquidity_status TEXT,
    liquidity_basis TEXT,
    valuation_status TEXT,
    valuation_source TEXT,
    duration_boundary_confirmed INTEGER,
    cash_equivalent_boundary TEXT,
    interest_rate_risk_disclosed INTEGER,
    credit_risk_disclosed INTEGER,
    liquidity_risk_disclosed INTEGER,
    source_profile TEXT,
    json_payload TEXT NOT NULL,
    FOREIGN KEY (subject_id) REFERENCES subjects(id)
);

CREATE TABLE portfolio_snapshots (
    id INTEGER PRIMARY KEY,
    artifact_id INTEGER NOT NULL,
    date TEXT,
    generated_at TEXT,
    total_items INTEGER,
    equity_weight_pct REAL,
    bond_cash_weight_pct REAL,
    cash_uninvested_pct REAL,
    weight_sum_pct REAL,
    one_line_conclusion TEXT,
    quality_status TEXT,
    json_payload TEXT NOT NULL,
    FOREIGN KEY (artifact_id) REFERENCES artifacts(id)
);

CREATE TABLE portfolio_positions (
    id INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL,
    subject_id INTEGER,
    code TEXT NOT NULL,
    ts_code TEXT,
    name TEXT,
    position_type TEXT,
    weight_pct REAL,
    day_change_pct REAL,
    reference_pnl_pct REAL,
    category TEXT,
    allocation_bucket TEXT,
    cost_basis_status TEXT,
    json_payload TEXT NOT NULL,
    FOREIGN KEY (snapshot_id) REFERENCES portfolio_snapshots(id),
    FOREIGN KEY (subject_id) REFERENCES subjects(id)
);

CREATE TABLE target_allocations (
    id INTEGER PRIMARY KEY,
    artifact_id INTEGER NOT NULL,
    date TEXT,
    generated_at TEXT,
    basis_trade_date TEXT,
    market_state TEXT,
    market_position_score REAL,
    recommended_equity_center REAL,
    recommended_equity_range TEXT,
    recommended_bond_cash_center REAL,
    recommended_bond_cash_range TEXT,
    offensive_bucket_status TEXT,
    one_line_conclusion TEXT,
    json_payload TEXT NOT NULL,
    FOREIGN KEY (artifact_id) REFERENCES artifacts(id)
);

CREATE TABLE bucket_allocations (
    id INTEGER PRIMARY KEY,
    target_allocation_id INTEGER NOT NULL,
    bucket_key TEXT NOT NULL,
    label TEXT,
    target_pct REAL,
    actual_pct REAL,
    gap_pct REAL,
    color TEXT,
    priority TEXT,
    role TEXT,
    source TEXT NOT NULL,
    json_payload TEXT NOT NULL,
    FOREIGN KEY (target_allocation_id) REFERENCES target_allocations(id)
);

CREATE TABLE action_plans (
    id INTEGER PRIMARY KEY,
    artifact_id INTEGER NOT NULL,
    date TEXT,
    generated_at TEXT,
    basis_trade_date TEXT,
    action_state TEXT,
    recommendation_strength TEXT,
    one_line_conclusion TEXT,
    quality_status TEXT,
    staleness_status TEXT,
    json_payload TEXT NOT NULL,
    FOREIGN KEY (artifact_id) REFERENCES artifacts(id)
);

CREATE TABLE action_items (
    id INTEGER PRIMARY KEY,
    action_plan_id INTEGER NOT NULL,
    priority TEXT,
    action_type TEXT,
    code TEXT,
    name TEXT,
    subject_type TEXT,
    bucket_role TEXT,
    current_position TEXT,
    suggested_change TEXT,
    target_position TEXT,
    recommendation_strength TEXT,
    needs_manual_confirmation INTEGER,
    evidence_json TEXT NOT NULL,
    trigger_conditions_json TEXT NOT NULL,
    invalidation_conditions_json TEXT NOT NULL,
    risks_json TEXT NOT NULL,
    review_points_json TEXT NOT NULL,
    json_payload TEXT NOT NULL,
    FOREIGN KEY (action_plan_id) REFERENCES action_plans(id)
);

CREATE TABLE research_first_items (
    id INTEGER PRIMARY KEY,
    action_plan_id INTEGER,
    code TEXT,
    name TEXT,
    subject_type TEXT,
    bucket_role TEXT,
    priority TEXT,
    reason TEXT,
    blocking_reasons_json TEXT NOT NULL,
    required_research_json TEXT NOT NULL,
    source TEXT NOT NULL,
    json_payload TEXT NOT NULL,
    FOREIGN KEY (action_plan_id) REFERENCES action_plans(id)
);

CREATE TABLE intraday_rules (
    id INTEGER PRIMARY KEY,
    artifact_id INTEGER NOT NULL,
    generated_at TEXT,
    last_updated TEXT,
    default_market_gate TEXT,
    allow_add_when_market_gate INTEGER,
    allow_watch_when_market_gate INTEGER,
    risk_reduce_always_allowed INTEGER,
    manual_confirmation_required INTEGER,
    staleness_status TEXT,
    staleness_reason TEXT,
    target_allocation_path TEXT,
    portfolio_snapshot_path TEXT,
    target_equity_pct REAL,
    target_cash_short_pct REAL,
    actual_equity_pct REAL,
    actual_cash_short_pct REAL,
    json_payload TEXT NOT NULL,
    FOREIGN KEY (artifact_id) REFERENCES artifacts(id)
);

CREATE TABLE intraday_bucket_rules (
    id INTEGER PRIMARY KEY,
    intraday_rules_id INTEGER NOT NULL,
    bucket_key TEXT NOT NULL,
    label TEXT,
    target_pct REAL,
    actual_pct REAL,
    gap_pct REAL,
    color TEXT,
    note TEXT,
    json_payload TEXT NOT NULL,
    FOREIGN KEY (intraday_rules_id) REFERENCES intraday_rules(id)
);

CREATE TABLE decision_log_entries (
    id INTEGER PRIMARY KEY,
    entry_date TEXT,
    title TEXT NOT NULL,
    body TEXT,
    source_path TEXT NOT NULL,
    json_payload TEXT NOT NULL
);
"""


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def plain_code(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def rel_path(path: Path | str) -> str:
    p = Path(path)
    if p.is_absolute():
        return p.resolve().relative_to(ROOT.resolve()).as_posix()
    return p.as_posix()


def resolve_repo_path(value: Any) -> Path:
    if not value:
        raise ValueError("empty path")
    text = str(value)
    path = Path(text)
    if path.is_absolute():
        raise ValueError(f"absolute paths are not allowed in current-state imports: {text}")
    resolved = (ROOT / path).resolve()
    root_resolved = ROOT.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError(f"path escapes repository root: {text}")
    if not resolved.exists():
        raise FileNotFoundError(text)
    return resolved


def safe_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = LOCAL_ABS_PATH_RE.sub("[redacted_path]", value)
    text = MONEY_OR_SHARE_RE.sub("[redacted_amount]", text)
    return text


def clean_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_value(item) for item in value]
    return safe_text(value)


def assert_ratio_only(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            key_path = f"{path}.{key_text}"
            if FORBIDDEN_KEY_RE.search(key_text):
                raise ValueError(f"forbidden field {key_path}")
            assert_ratio_only(item, key_path)
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            assert_ratio_only(item, f"{path}[{idx}]")
    elif isinstance(value, str):
        if LOCAL_ABS_PATH_RE.search(value):
            raise ValueError(f"local absolute path at {path}")
        if MONEY_OR_SHARE_RE.search(value):
            raise ValueError(f"forbidden amount/share-like text at {path}: {value[:80]}")


def safe_json(value: Any) -> str:
    cleaned = clean_value(value)
    assert_ratio_only(cleaned)
    return json.dumps(cleaned, ensure_ascii=False, sort_keys=True)


def scalar_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return safe_json(value)
    return safe_text(value)


def normalize_ref(ref: dict[str, Any]) -> dict[str, Any]:
    item = {
        "module": ref.get("module"),
        "code": ref.get("code"),
        "name": ref.get("name"),
        "path": ref.get("path"),
        "generated_at": ref.get("generated_at"),
        "basis_trade_date": ref.get("basis_trade_date"),
        "sha256": ref.get("sha256"),
        "quality_status": ((ref.get("quality") or {}).get("status")),
        "staleness_status": ((ref.get("staleness") or {}).get("status")),
    }
    assert_ratio_only(clean_value(item))
    return item


def run_required_check(args: list[str]) -> None:
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        output = (completed.stdout or "") + (completed.stderr or "")
        raise RuntimeError(f"{' '.join(args)} failed\n{output.strip()}")
    if completed.stdout.strip():
        print(completed.stdout.strip())


def insert_row(conn: sqlite3.Connection, table: str, row: dict[str, Any]) -> int:
    cleaned = clean_value(row)
    assert_ratio_only(cleaned)
    keys = list(cleaned.keys())
    placeholders = ", ".join("?" for _ in keys)
    sql = f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({placeholders})"
    cur = conn.execute(sql, [scalar_value(cleaned[key]) for key in keys])
    return int(cur.lastrowid)


def upsert_subject(conn: sqlite3.Connection, row: dict[str, Any]) -> int:
    code = str(row.get("code") or "").strip()
    name = str(row.get("name") or "").strip()
    subject_type = str(row.get("subject_type") or row.get("type") or "").strip()
    key = code or f"{subject_type}:{name}" or f"subject:{conn.execute('SELECT COUNT(*) FROM subjects').fetchone()[0] + 1}"
    payload = {
        "code": scalar_value(code or None),
        "name": scalar_value(name or None),
        "subject_type": scalar_value(subject_type or None),
        "bucket_role": scalar_value(row.get("bucket_role")),
        "allocation_bucket": scalar_value(row.get("allocation_bucket")),
        "source_module": scalar_value(row.get("source_module")),
        "profile_status": scalar_value(row.get("profile_status")),
        "valuation_status": scalar_value(row.get("valuation_status")),
        "liquidity_status": scalar_value(row.get("liquidity_status")),
        "stance": scalar_value(row.get("stance")),
    }
    conn.execute(
        """
        INSERT INTO subjects (
            subject_key, code, name, subject_type, bucket_role, allocation_bucket,
            source_module, profile_status, valuation_status, liquidity_status, stance, json_payload
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(subject_key) DO UPDATE SET
            name=COALESCE(excluded.name, subjects.name),
            subject_type=COALESCE(excluded.subject_type, subjects.subject_type),
            bucket_role=COALESCE(excluded.bucket_role, subjects.bucket_role),
            allocation_bucket=COALESCE(excluded.allocation_bucket, subjects.allocation_bucket),
            source_module=COALESCE(excluded.source_module, subjects.source_module),
            profile_status=COALESCE(excluded.profile_status, subjects.profile_status),
            valuation_status=COALESCE(excluded.valuation_status, subjects.valuation_status),
            liquidity_status=COALESCE(excluded.liquidity_status, subjects.liquidity_status),
            stance=COALESCE(excluded.stance, subjects.stance),
            json_payload=excluded.json_payload
        """,
        (
            key,
            payload["code"],
            payload["name"],
            payload["subject_type"],
            payload["bucket_role"],
            payload["allocation_bucket"],
            payload["source_module"],
            payload["profile_status"],
            payload["valuation_status"],
            payload["liquidity_status"],
            payload["stance"],
            safe_json(payload),
        ),
    )
    return int(conn.execute("SELECT id FROM subjects WHERE subject_key = ?", (key,)).fetchone()[0])


def add_artifact(
    conn: sqlite3.Connection,
    ref: dict[str, Any],
    imported_at: str,
    current_flag: bool,
    support_role: str | None = None,
) -> int:
    normalized = normalize_ref(ref)
    payload = dict(normalized)
    payload["current_flag"] = bool(current_flag)
    payload["support_role"] = support_role
    row = {
        **normalized,
        "current_flag": 1 if current_flag else 0,
        "support_role": support_role,
        "imported_at": imported_at,
        "json_payload": safe_json(payload),
    }
    return insert_row(conn, "artifacts", row)


def current_ref(index: dict[str, Any], module: str) -> dict[str, Any]:
    ref = (index.get("modules") or {}).get(module)
    if not isinstance(ref, dict):
        raise KeyError(f"latest_index.modules.{module} is missing")
    resolve_repo_path(ref.get("path"))
    return ref


def build_support_ref(path_text: str, module: str, support_role: str, data: dict[str, Any]) -> dict[str, Any]:
    path = resolve_repo_path(path_text)
    return {
        "module": module,
        "code": data.get("code") or data.get("ts_code"),
        "name": data.get("name"),
        "path": rel_path(path),
        "generated_at": data.get("generated_at") or data.get("last_updated"),
        "basis_trade_date": data.get("basis_trade_date") or data.get("basis_date") or data.get("date"),
        "sha256": None,
        "quality": {"status": ((data.get("quality") or {}).get("status"))},
        "staleness": {"status": ((data.get("staleness") or {}).get("status"))},
        "support_role": support_role,
    }


def import_current_modules(conn: sqlite3.Connection, index: dict[str, Any], imported_at: str) -> dict[str, int]:
    artifact_ids: dict[str, int] = {}
    for module, ref in sorted((index.get("modules") or {}).items()):
        resolve_repo_path(ref.get("path"))
        artifact_id = add_artifact(conn, ref, imported_at, current_flag=True)
        artifact_ids[module] = artifact_id
        normalized = normalize_ref(ref)
        payload = dict(normalized)
        payload["module_pointer"] = module
        insert_row(
            conn,
            "current_modules",
            {
                "module": module,
                "artifact_id": artifact_id,
                "code": normalized.get("code"),
                "name": normalized.get("name"),
                "path": normalized.get("path"),
                "generated_at": normalized.get("generated_at"),
                "basis_trade_date": normalized.get("basis_trade_date"),
                "quality_status": normalized.get("quality_status"),
                "staleness_status": normalized.get("staleness_status"),
                "imported_at": imported_at,
                "json_payload": safe_json(payload),
            },
        )
    return artifact_ids


def import_market_score(conn: sqlite3.Connection, data: dict[str, Any], artifact_id: int) -> None:
    summary = data.get("summary") or {}
    payload = {
        "date": data.get("date"),
        "basis_trade_date": data.get("basis_trade_date"),
        "summary": {
            "market_state": summary.get("market_state"),
            "opportunity_score": summary.get("opportunity_score"),
            "crowding_penalty": summary.get("crowding_penalty"),
            "market_position_score": summary.get("market_position_score"),
            "equity_allocation_range": summary.get("equity_allocation_range"),
            "bond_cash_allocation_range": summary.get("bond_cash_allocation_range"),
            "offensive_bucket_status": summary.get("offensive_bucket_status"),
            "one_line_conclusion": safe_text(summary.get("one_line_conclusion")),
        },
    }
    insert_row(
        conn,
        "market_scores",
        {
            "artifact_id": artifact_id,
            "date": data.get("date"),
            "basis_trade_date": data.get("basis_trade_date"),
            "market_state": summary.get("market_state"),
            "opportunity_score": summary.get("opportunity_score"),
            "crowding_penalty": summary.get("crowding_penalty"),
            "market_position_score": summary.get("market_position_score"),
            "equity_allocation_range": summary.get("equity_allocation_range"),
            "bond_cash_allocation_range": summary.get("bond_cash_allocation_range"),
            "offensive_bucket_status": summary.get("offensive_bucket_status"),
            "one_line_conclusion": safe_text(summary.get("one_line_conclusion")),
            "json_payload": safe_json(payload),
        },
    )


def import_market_position_mapping(conn: sqlite3.Connection, data: dict[str, Any], source_path: str) -> None:
    for row in data.get("ranges") or []:
        payload = {
            "score_min": row.get("score_min"),
            "score_max": row.get("score_max"),
            "market_state": row.get("market_state"),
            "equity_allocation_range": row.get("equity_allocation_range"),
            "bond_cash_allocation_range": row.get("bond_cash_allocation_range"),
            "offensive_bucket_status": row.get("offensive_bucket_status"),
        }
        insert_row(
            conn,
            "market_position_mappings",
            {
                "source_path": source_path,
                **payload,
                "json_payload": safe_json(payload),
            },
        )


def import_target_allocation(conn: sqlite3.Connection, data: dict[str, Any], artifact_id: int) -> int:
    summary = data.get("summary") or {}
    payload = {
        "date": data.get("date"),
        "generated_at": data.get("generated_at"),
        "basis_trade_date": data.get("basis_trade_date"),
        "summary": summary,
    }
    allocation_id = insert_row(
        conn,
        "target_allocations",
        {
            "artifact_id": artifact_id,
            "date": data.get("date"),
            "generated_at": data.get("generated_at"),
            "basis_trade_date": data.get("basis_trade_date"),
            "market_state": summary.get("market_state"),
            "market_position_score": summary.get("market_position_score"),
            "recommended_equity_center": summary.get("recommended_equity_center"),
            "recommended_equity_range": summary.get("recommended_equity_range"),
            "recommended_bond_cash_center": summary.get("recommended_bond_cash_center"),
            "recommended_bond_cash_range": summary.get("recommended_bond_cash_range"),
            "offensive_bucket_status": summary.get("offensive_bucket_status"),
            "one_line_conclusion": safe_text(summary.get("one_line_conclusion")),
            "json_payload": safe_json(payload),
        },
    )
    for bucket in ((data.get("actual_allocation_overlay") or {}).get("buckets") or []):
        payload = {
            "key": bucket.get("key"),
            "label": bucket.get("label"),
            "target_pct": bucket.get("target_pct"),
            "actual_pct": bucket.get("actual_pct"),
            "gap_pct": bucket.get("gap_pct"),
            "color": bucket.get("color"),
            "source": "target_allocation",
        }
        insert_row(
            conn,
            "bucket_allocations",
            {
                "target_allocation_id": allocation_id,
                "bucket_key": bucket.get("key"),
                "label": bucket.get("label"),
                "target_pct": bucket.get("target_pct"),
                "actual_pct": bucket.get("actual_pct"),
                "gap_pct": bucket.get("gap_pct"),
                "color": bucket.get("color"),
                "priority": bucket.get("priority"),
                "role": bucket.get("role"),
                "source": "target_allocation",
                "json_payload": safe_json(payload),
            },
        )
    return allocation_id


def import_portfolio_snapshot(conn: sqlite3.Connection, data: dict[str, Any], artifact_id: int) -> int:
    summary = data.get("summary") or {}
    quality = data.get("quality") or {}
    payload = {
        "date": data.get("date"),
        "generated_at": data.get("generated_at"),
        "summary": {
            "total_items": summary.get("total_items"),
            "equity_weight_pct": summary.get("equity_weight_pct"),
            "bond_cash_weight_pct": summary.get("bond_cash_weight_pct"),
            "cash_uninvested_pct": summary.get("cash_uninvested_pct"),
            "weight_sum_pct": summary.get("weight_sum_pct"),
            "one_line_conclusion": safe_text(summary.get("one_line_conclusion")),
        },
        "quality_status": quality.get("status"),
    }
    snapshot_id = insert_row(
        conn,
        "portfolio_snapshots",
        {
            "artifact_id": artifact_id,
            "date": data.get("date"),
            "generated_at": data.get("generated_at"),
            "total_items": summary.get("total_items"),
            "equity_weight_pct": summary.get("equity_weight_pct"),
            "bond_cash_weight_pct": summary.get("bond_cash_weight_pct"),
            "cash_uninvested_pct": summary.get("cash_uninvested_pct"),
            "weight_sum_pct": summary.get("weight_sum_pct"),
            "one_line_conclusion": safe_text(summary.get("one_line_conclusion")),
            "quality_status": quality.get("status"),
            "json_payload": safe_json(payload),
        },
    )
    for item in data.get("holdings") or []:
        subject_id = upsert_subject(
            conn,
            {
                "code": item.get("code"),
                "name": item.get("name"),
                "subject_type": item.get("type"),
                "allocation_bucket": item.get("allocation_bucket"),
                "source_module": "portfolio_snapshot",
            },
        )
        payload = {
            "code": item.get("code"),
            "ts_code": item.get("ts_code"),
            "name": item.get("name"),
            "position_type": item.get("type"),
            "weight_pct": item.get("weight_pct"),
            "day_change_pct": item.get("day_change_pct"),
            "reference_pnl_pct": item.get("reference_pnl_pct"),
            "category": item.get("category"),
            "allocation_bucket": item.get("allocation_bucket"),
            "cost_basis_status": item.get("cost_basis_status"),
        }
        insert_row(
            conn,
            "portfolio_positions",
            {
                "snapshot_id": snapshot_id,
                "subject_id": subject_id,
                **payload,
                "json_payload": safe_json(payload),
            },
        )
    return snapshot_id


def import_action_plan(conn: sqlite3.Connection, data: dict[str, Any], artifact_id: int) -> int:
    summary = data.get("summary") or {}
    quality = data.get("quality") or {}
    staleness = data.get("staleness") or {}
    payload = {
        "date": data.get("date"),
        "generated_at": data.get("generated_at"),
        "basis_trade_date": data.get("basis_trade_date"),
        "summary": summary,
        "quality_status": quality.get("status"),
        "staleness_status": staleness.get("status"),
    }
    plan_id = insert_row(
        conn,
        "action_plans",
        {
            "artifact_id": artifact_id,
            "date": data.get("date"),
            "generated_at": data.get("generated_at"),
            "basis_trade_date": data.get("basis_trade_date"),
            "action_state": summary.get("action_state"),
            "recommendation_strength": summary.get("recommendation_strength"),
            "one_line_conclusion": safe_text(summary.get("one_line_conclusion")),
            "quality_status": quality.get("status"),
            "staleness_status": staleness.get("status"),
            "json_payload": safe_json(payload),
        },
    )
    for item in data.get("actions") or []:
        subject = item.get("subject") or {}
        action_type = str(item.get("action_type") or "").lower()
        code = subject.get("code") or None
        subject_id = upsert_subject(
            conn,
            {
                "code": code,
                "name": subject.get("name"),
                "subject_type": subject.get("type"),
                "bucket_role": item.get("bucket_role"),
                "source_module": "action_plan",
            },
        )
        if action_type in EXECUTABLE_ACTIONS and code and not plain_code(code):
            raise ValueError(f"executable action has invalid code: {code}")
        payload = {
            "priority": item.get("priority"),
            "action_type": item.get("action_type"),
            "subject": {
                "code": code,
                "name": subject.get("name"),
                "type": subject.get("type"),
            },
            "bucket_role": item.get("bucket_role"),
            "current_position": item.get("current_position"),
            "suggested_change": item.get("suggested_change"),
            "target_position": item.get("target_position"),
            "recommendation_strength": item.get("recommendation_strength"),
            "needs_manual_confirmation": bool(item.get("needs_manual_confirmation")),
            "evidence": item.get("evidence") or [],
            "trigger_conditions": item.get("trigger_conditions") or [],
            "invalidation_conditions": item.get("invalidation_conditions") or [],
            "risks": item.get("risks") or [],
            "review_points": item.get("review_points") or [],
        }
        insert_row(
            conn,
            "action_items",
            {
                "action_plan_id": plan_id,
                "priority": item.get("priority"),
                "action_type": item.get("action_type"),
                "code": code,
                "name": subject.get("name"),
                "subject_type": subject.get("type"),
                "bucket_role": item.get("bucket_role"),
                "current_position": item.get("current_position"),
                "suggested_change": item.get("suggested_change"),
                "target_position": item.get("target_position"),
                "recommendation_strength": item.get("recommendation_strength"),
                "needs_manual_confirmation": 1 if item.get("needs_manual_confirmation") else 0,
                "evidence_json": safe_json(item.get("evidence") or []),
                "trigger_conditions_json": safe_json(item.get("trigger_conditions") or []),
                "invalidation_conditions_json": safe_json(item.get("invalidation_conditions") or []),
                "risks_json": safe_json(item.get("risks") or []),
                "review_points_json": safe_json(item.get("review_points") or []),
                "json_payload": safe_json(payload),
            },
        )
    for source_key in ["research_first", "research_first_list", "research_first_items"]:
        for item in data.get(source_key) or []:
            subject = item.get("subject") or item
            payload = {
                "code": subject.get("code") or item.get("code"),
                "name": subject.get("name") or item.get("name"),
                "subject_type": subject.get("type") or item.get("subject_type"),
                "bucket_role": item.get("bucket_role"),
                "priority": item.get("priority"),
                "reason": item.get("reason") or item.get("blocking_reason"),
                "blocking_reasons": item.get("blocking_reasons") or [],
                "required_research": item.get("required_research") or item.get("next_steps") or [],
            }
            insert_row(
                conn,
                "research_first_items",
                {
                    "action_plan_id": plan_id,
                    "code": payload["code"],
                    "name": payload["name"],
                    "subject_type": payload["subject_type"],
                    "bucket_role": payload["bucket_role"],
                    "priority": payload["priority"],
                    "reason": safe_text(payload["reason"]),
                    "blocking_reasons_json": safe_json(payload["blocking_reasons"]),
                    "required_research_json": safe_json(payload["required_research"]),
                    "source": source_key,
                    "json_payload": safe_json(payload),
                },
            )
    return plan_id


def import_intraday_rules(conn: sqlite3.Connection, data: dict[str, Any], artifact_id: int) -> int:
    gate = data.get("global_gate") or {}
    staleness = data.get("staleness") or {}
    allocation = data.get("allocation_map") or {}
    payload = {
        "generated_at": data.get("generated_at"),
        "last_updated": data.get("last_updated"),
        "global_gate": gate,
        "staleness": {
            "status": staleness.get("status"),
            "reason": staleness.get("reason"),
        },
        "allocation_map": {
            "target_equity_pct": allocation.get("target_equity_pct"),
            "target_cash_short_pct": allocation.get("target_cash_short_pct"),
            "actual_equity_pct": allocation.get("actual_equity_pct"),
            "actual_cash_short_pct": allocation.get("actual_cash_short_pct"),
        },
    }
    rules_id = insert_row(
        conn,
        "intraday_rules",
        {
            "artifact_id": artifact_id,
            "generated_at": data.get("generated_at"),
            "last_updated": data.get("last_updated"),
            "default_market_gate": gate.get("default_market_gate"),
            "allow_add_when_market_gate": 1 if gate.get("allow_add_when_market_gate") else 0,
            "allow_watch_when_market_gate": 1 if gate.get("allow_watch_when_market_gate") else 0,
            "risk_reduce_always_allowed": 1 if gate.get("risk_reduce_always_allowed") else 0,
            "manual_confirmation_required": 1 if gate.get("manual_confirmation_required") else 0,
            "staleness_status": staleness.get("status"),
            "staleness_reason": safe_text(staleness.get("reason")),
            "target_allocation_path": allocation.get("target_allocation_file"),
            "portfolio_snapshot_path": allocation.get("portfolio_snapshot_file"),
            "target_equity_pct": allocation.get("target_equity_pct"),
            "target_cash_short_pct": allocation.get("target_cash_short_pct"),
            "actual_equity_pct": allocation.get("actual_equity_pct"),
            "actual_cash_short_pct": allocation.get("actual_cash_short_pct"),
            "json_payload": safe_json(payload),
        },
    )
    for bucket in allocation.get("buckets") or []:
        payload = {
            "key": bucket.get("key"),
            "label": bucket.get("label"),
            "target_pct": bucket.get("target_pct"),
            "actual_pct": bucket.get("actual_pct"),
            "gap_pct": bucket.get("gap_pct"),
            "color": bucket.get("color"),
            "note": bucket.get("note"),
        }
        insert_row(
            conn,
            "intraday_bucket_rules",
            {
                "intraday_rules_id": rules_id,
                "bucket_key": bucket.get("key"),
                "label": bucket.get("label"),
                "target_pct": bucket.get("target_pct"),
                "actual_pct": bucket.get("actual_pct"),
                "gap_pct": bucket.get("gap_pct"),
                "color": bucket.get("color"),
                "note": safe_text(bucket.get("note")),
                "json_payload": safe_json(payload),
            },
        )
    for subject in data.get("subjects") or []:
        upsert_subject(
            conn,
            {
                "code": subject.get("code"),
                "name": subject.get("name"),
                "subject_type": subject.get("type"),
                "bucket_role": subject.get("role"),
                "allocation_bucket": subject.get("allocation_bucket"),
                "source_module": "intraday_rules",
                "stance": subject.get("security_stance"),
            },
        )
    return rules_id


def find_registry_511360(etf_registry: dict[str, Any]) -> dict[str, Any]:
    for item in etf_registry.get("etfs") or []:
        if plain_code(item.get("code")) == "511360":
            return item
    raise KeyError("511360 not found in current etf_registry")


def import_511360_profile_and_valuation(
    conn: sqlite3.Connection,
    etf_registry: dict[str, Any],
    liquidity_registry: dict[str, Any],
    imported_at: str,
) -> None:
    registry_row = find_registry_511360(etf_registry)
    subject_id = upsert_subject(
        conn,
        {
            "code": registry_row.get("code"),
            "name": registry_row.get("name"),
            "subject_type": "ETF",
            "bucket_role": registry_row.get("bucket_role"),
            "source_module": "etf_registry",
            "profile_status": registry_row.get("status"),
        },
    )
    profile_path_text = registry_row.get("last_profile_json")
    if not profile_path_text:
        raise ValueError("511360 profile pointer missing from current etf_registry")
    profile_path = resolve_repo_path(profile_path_text)
    profile_data = read_json(profile_path)
    profile_ref = build_support_ref(rel_path(profile_path), "etf_profile", "511360_profile", profile_data)
    add_artifact(conn, profile_ref, imported_at, current_flag=False, support_role="511360_profile")
    profile_payload = {
        "code": registry_row.get("code"),
        "name": registry_row.get("name"),
        "profile_path": rel_path(profile_path),
        "generated_at": profile_data.get("generated_at"),
        "basis_date": profile_data.get("basis_trade_date") or profile_data.get("basis_date") or profile_data.get("date"),
        "bucket_role": registry_row.get("bucket_role"),
        "rating": registry_row.get("rating"),
        "action_rating": registry_row.get("action_rating"),
        "status": registry_row.get("status"),
        "summary": safe_text(profile_data.get("one_line_conclusion") or registry_row.get("reason")),
    }
    insert_row(
        conn,
        "profiles",
        {
            "subject_id": subject_id,
            "code": registry_row.get("code"),
            "name": registry_row.get("name"),
            "subject_type": "ETF",
            "profile_path": rel_path(profile_path),
            "generated_at": profile_data.get("generated_at"),
            "basis_date": profile_payload["basis_date"],
            "bucket_role": registry_row.get("bucket_role"),
            "rating": registry_row.get("rating"),
            "action_rating": registry_row.get("action_rating"),
            "status": registry_row.get("status"),
            "summary": profile_payload["summary"],
            "json_payload": safe_json(profile_payload),
        },
    )

    instruments = liquidity_registry.get("instruments") or {}
    liquidity_row = instruments.get("511360") or next(
        (item for item in instruments.values() if plain_code(item.get("code")) == "511360"),
        None,
    )
    if not isinstance(liquidity_row, dict):
        raise KeyError("511360 liquidity gate not found")
    valuation_path_text = liquidity_row.get("valuation_source")
    if not valuation_path_text:
        raise ValueError("511360 valuation_source missing from liquidity gate registry")
    valuation_path = resolve_repo_path(valuation_path_text)
    valuation_data = read_json(valuation_path)
    valuation_ref = build_support_ref(rel_path(valuation_path), "valuation_report", "511360_valuation", valuation_data)
    add_artifact(conn, valuation_ref, imported_at, current_flag=False, support_role="511360_valuation")
    valuation_payload = {
        "code": valuation_data.get("code") or liquidity_row.get("code"),
        "name": valuation_data.get("name") or liquidity_row.get("name"),
        "valuation_path": rel_path(valuation_path),
        "generated_at": valuation_data.get("generated_at"),
        "basis_date": valuation_data.get("basis_date") or valuation_data.get("basis_trade_date") or valuation_data.get("date"),
        "asset_type": valuation_data.get("asset_type"),
        "group_name": valuation_data.get("group"),
        "role": valuation_data.get("role"),
        "confidence": valuation_data.get("confidence"),
        "security_stance": valuation_data.get("security_stance"),
        "one_line_conclusion": safe_text(valuation_data.get("one_line_conclusion")),
    }
    insert_row(
        conn,
        "valuations",
        {
            "subject_id": subject_id,
            "code": valuation_payload["code"],
            "name": valuation_payload["name"],
            "valuation_path": valuation_payload["valuation_path"],
            "generated_at": valuation_payload["generated_at"],
            "basis_date": valuation_payload["basis_date"],
            "asset_type": valuation_payload["asset_type"],
            "group_name": valuation_payload["group_name"],
            "role": valuation_payload["role"],
            "confidence": valuation_payload["confidence"],
            "security_stance": valuation_payload["security_stance"],
            "one_line_conclusion": valuation_payload["one_line_conclusion"],
            "json_payload": safe_json(valuation_payload),
        },
    )
    gate_payload = {
        "code": liquidity_row.get("code"),
        "name": liquidity_row.get("name"),
        "bucket_role": liquidity_row.get("bucket_role"),
        "liquidity_status": liquidity_row.get("liquidity_status"),
        "liquidity_basis": liquidity_row.get("liquidity_basis"),
        "valuation_status": liquidity_row.get("valuation_status"),
        "valuation_source": liquidity_row.get("valuation_source"),
        "duration_boundary_confirmed": bool(liquidity_row.get("duration_boundary_confirmed")),
        "cash_equivalent_boundary": liquidity_row.get("cash_equivalent_boundary"),
        "interest_rate_risk_disclosed": bool(liquidity_row.get("interest_rate_risk_disclosed")),
        "credit_risk_disclosed": bool(liquidity_row.get("credit_risk_disclosed")),
        "liquidity_risk_disclosed": bool(liquidity_row.get("liquidity_risk_disclosed")),
        "source_profile": liquidity_row.get("source_profile"),
    }
    insert_row(
        conn,
        "liquidity_gates",
        {
            "subject_id": subject_id,
            "code": liquidity_row.get("code"),
            "name": liquidity_row.get("name"),
            "bucket_role": liquidity_row.get("bucket_role"),
            "liquidity_status": liquidity_row.get("liquidity_status"),
            "liquidity_basis": liquidity_row.get("liquidity_basis"),
            "valuation_status": liquidity_row.get("valuation_status"),
            "valuation_source": liquidity_row.get("valuation_source"),
            "duration_boundary_confirmed": 1 if liquidity_row.get("duration_boundary_confirmed") else 0,
            "cash_equivalent_boundary": liquidity_row.get("cash_equivalent_boundary"),
            "interest_rate_risk_disclosed": 1 if liquidity_row.get("interest_rate_risk_disclosed") else 0,
            "credit_risk_disclosed": 1 if liquidity_row.get("credit_risk_disclosed") else 0,
            "liquidity_risk_disclosed": 1 if liquidity_row.get("liquidity_risk_disclosed") else 0,
            "source_profile": liquidity_row.get("source_profile"),
            "json_payload": safe_json(gate_payload),
        },
    )


def import_decision_log(conn: sqlite3.Connection) -> None:
    path = ROOT / "research" / "logs" / "decision_log.md"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        if not line.startswith("## "):
            continue
        title = line.removeprefix("## ").strip()
        entry_date = title.split(" ", 1)[0] if title else None
        payload = {"entry_date": entry_date, "title": safe_text(title), "source_path": rel_path(path)}
        insert_row(
            conn,
            "decision_log_entries",
            {
                "entry_date": entry_date,
                "title": safe_text(title),
                "body": "",
                "source_path": rel_path(path),
                "json_payload": safe_json(payload),
            },
        )


def validate_current_inputs(index: dict[str, Any]) -> None:
    missing = [module for module in sorted(REQUIRED_CURRENT_MODULES) if module not in (index.get("modules") or {})]
    if missing:
        raise KeyError(f"missing latest_index current modules: {', '.join(missing)}")
    action_ref = current_ref(index, "action_plan")
    run_required_check(["scripts/check_ratio_only.py", "--path", str(action_ref["path"])])
    run_required_check(["scripts/check_research_first_gate.py", "--path", str(action_ref["path"])])
    run_required_check(["scripts/check_cross_file_allocation_consistency.py"])


def make_writable(path: Path) -> None:
    if path.exists():
        try:
            os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
        except OSError:
            pass


def make_readonly(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IREAD)
    except OSError:
        pass


def verify_database_safe(conn: sqlite3.Connection) -> None:
    table_rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    for (table,) in table_rows:
        columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        for db_row in conn.execute(f"SELECT * FROM {table}").fetchall():
            record = dict(zip(columns, db_row))
            for key, value in list(record.items()):
                if key.endswith("_json") or key == "json_payload":
                    try:
                        record[key] = json.loads(value or "null")
                    except (TypeError, json.JSONDecodeError):
                        pass
            assert_ratio_only(record, f"db.{table}")


def create_database(index: dict[str, Any]) -> dict[str, int]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    make_writable(DB_PATH)
    make_writable(TMP_DB_PATH)
    if TMP_DB_PATH.exists():
        TMP_DB_PATH.unlink()
    imported_at = now_text()
    conn = sqlite3.connect(TMP_DB_PATH)
    try:
        conn.executescript(SCHEMA_SQL)
        artifact_ids = import_current_modules(conn, index, imported_at)
        loaded: dict[str, dict[str, Any]] = {}
        for module in REQUIRED_CURRENT_MODULES | CURRENT_CONFIG_MODULES:
            ref = current_ref(index, module)
            loaded[module] = read_json(resolve_repo_path(ref["path"]))

        import_market_score(conn, loaded["market_score"], artifact_ids["market_score"])
        import_market_position_mapping(
            conn,
            loaded["market_position_mapping"],
            current_ref(index, "market_position_mapping")["path"],
        )
        import_target_allocation(conn, loaded["target_allocation"], artifact_ids["target_allocation"])
        import_portfolio_snapshot(conn, loaded["portfolio_snapshot"], artifact_ids["portfolio_snapshot"])
        import_action_plan(conn, loaded["action_plan"], artifact_ids["action_plan"])
        import_intraday_rules(conn, loaded["intraday_rules"], artifact_ids["intraday_rules"])
        import_511360_profile_and_valuation(conn, loaded["etf_registry"], loaded["liquidity_gate_registry"], imported_at)
        import_decision_log(conn)
        verify_database_safe(conn)
        conn.commit()
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in [
                "artifacts",
                "current_modules",
                "market_scores",
                "subjects",
                "profiles",
                "valuations",
                "liquidity_gates",
                "portfolio_snapshots",
                "portfolio_positions",
                "target_allocations",
                "bucket_allocations",
                "action_plans",
                "action_items",
                "research_first_items",
                "intraday_rules",
                "intraday_bucket_rules",
                "decision_log_entries",
            ]
        }
    finally:
        conn.close()
    if DB_PATH.exists():
        DB_PATH.unlink()
    TMP_DB_PATH.replace(DB_PATH)
    make_readonly(DB_PATH)
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH, help="Reserved for display; database path is fixed for phase 1.")
    args = parser.parse_args(argv)
    if args.db.resolve() != DB_PATH.resolve():
        print(f"[FAIL] phase 1 database path is fixed: {DB_PATH.relative_to(ROOT).as_posix()}")
        return 1
    if not LATEST_INDEX.exists():
        print("[FAIL] research/latest_index.json not found")
        return 1
    try:
        index = read_json(LATEST_INDEX)
        validate_current_inputs(index)
        counts = create_database(index)
    except Exception as exc:  # noqa: BLE001 - command-line importer should surface exact blocker.
        print(f"[FAIL] current-state ingest failed: {exc}")
        return 1
    print("Current-state ingest: OK")
    print(f"Database: {DB_PATH.relative_to(ROOT).as_posix()}")
    print(json.dumps(counts, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
