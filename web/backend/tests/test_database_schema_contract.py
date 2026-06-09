from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from web.backend.app.services.ratio_only import RatioOnlyService


ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "temp" / "web_db" / "myinvest.sqlite"

CORE_TABLES = {
    "artifacts",
    "current_modules",
    "market_scores",
    "market_position_mappings",
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
    "system_check_results",
}

REQUIRED_CURRENT_MODULES = {
    "action_plan",
    "target_allocation",
    "intraday_rules",
    "portfolio_snapshot",
}

API_PATHS = [
    "/api/health",
    "/api/current",
    "/api/latest-index",
    "/api/modules/current",
    "/api/market-position/mapping",
    "/api/market-position/current",
    "/api/market-position/score/25",
    "/api/action-plan/current",
    "/api/target-allocation/current",
    "/api/target-allocation/shadow",
    "/api/target-allocation/shadow/compare",
    "/api/portfolio/current",
    "/api/intraday-rules/current",
    "/api/research-first/current",
    "/api/system-check/current",
    "/api/decision-log/current",
    "/api/export/review_package?format=json",
]


def connection(web_db: Path) -> sqlite3.Connection:
    assert web_db == DB_PATH
    conn = sqlite3.connect(web_db)
    conn.row_factory = sqlite3.Row
    return conn


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def parse_json_if_possible(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def assert_ratio_only_payload(value: Any, path: str = "$") -> None:
    RatioOnlyService.assert_safe(value, path)


def test_all_core_tables_exist(web_db):
    with connection(web_db) as conn:
        tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert CORE_TABLES <= tables


def test_current_modules_contains_required_current_pointers(web_db):
    with connection(web_db) as conn:
        modules = {row["module"] for row in conn.execute("SELECT module FROM current_modules")}
    assert REQUIRED_CURRENT_MODULES <= modules


def test_artifact_paths_are_repo_relative(web_db):
    with connection(web_db) as conn:
        rows = conn.execute("SELECT path FROM artifacts").fetchall()
    assert rows
    for row in rows:
        path = row["path"]
        assert not Path(path).is_absolute(), path
        assert not RatioOnlyService.local_path_re.search(path), path
        assert ".." not in Path(path).parts, path


def test_database_rows_and_raw_json_are_ratio_only(web_db):
    with connection(web_db) as conn:
        for table in CORE_TABLES:
            columns = table_columns(conn, table)
            for row in conn.execute(f"SELECT * FROM {table}"):
                payload = dict(row)
                for column in ["raw_json", "raw_markdown", "privacy_policy", "message", "summary", "reason", "ratio_only_text"]:
                    if column in columns and column in payload:
                        payload[column] = parse_json_if_possible(payload[column])
                assert_ratio_only_payload(payload, f"db.{table}")


def test_api_outputs_are_ratio_only(client):
    for path in API_PATHS:
        response = client.get(path)
        assert response.status_code == 200, path
        assert_ratio_only_payload(response.json(), path)


def test_current_action_plan_source_matches_latest_index_modules(web_db):
    latest = json.loads((ROOT / "research" / "latest_index.json").read_text(encoding="utf-8-sig"))
    expected_path = latest["modules"]["action_plan"]["path"]
    with connection(web_db) as conn:
        row = conn.execute(
            """
            SELECT a.path
            FROM current_modules cm
            JOIN artifacts a ON a.id = cm.artifact_id
            WHERE cm.module = 'action_plan'
            """
        ).fetchone()
    assert row["path"] == expected_path


def test_current_resolver_does_not_read_latest_index_files():
    scan_roots = [
        ROOT / "scripts" / "ingest_current_state.py",
        ROOT / "scripts" / "ingest_current_state_to_web_db.py",
        *list((ROOT / "web" / "backend" / "app").rglob("*.py")),
    ]
    offenders = []
    for path in scan_roots:
        text = path.read_text(encoding="utf-8", errors="replace")
        if "latest_index.files" in text or '["files"]' in text or "['files']" in text:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


def test_511360_liquidity_gate_contract(web_db):
    with connection(web_db) as conn:
        row = conn.execute(
            """
            SELECT s.code, lg.liquidity_status, lg.valuation_status,
                   lg.duration_boundary_confirmed, lg.interest_rate_risk_disclosed,
                   lg.credit_risk_disclosed, lg.liquidity_risk_disclosed,
                   profile.path AS profile_path, valuation.path AS valuation_path
            FROM liquidity_gates lg
            JOIN subjects s ON s.id = lg.subject_id
            LEFT JOIN artifacts profile ON profile.id = lg.source_profile_artifact_id
            LEFT JOIN artifacts valuation ON valuation.id = lg.source_valuation_artifact_id
            WHERE s.code = '511360.SH'
            """
        ).fetchone()
    assert row is not None
    assert row["liquidity_status"] == "pass"
    assert row["valuation_status"] == "pass"
    assert bool(row["duration_boundary_confirmed"]) is True
    assert bool(row["interest_rate_risk_disclosed"]) is True
    assert bool(row["credit_risk_disclosed"]) is True
    assert bool(row["liquidity_risk_disclosed"]) is True
    assert row["profile_path"]
    assert row["valuation_path"]
    assert not Path(row["profile_path"]).is_absolute()
    assert not Path(row["valuation_path"]).is_absolute()
