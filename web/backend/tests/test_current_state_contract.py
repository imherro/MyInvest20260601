from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from web.backend.app.db import SessionLocal
from web.backend.app.services.allocation_consistency import AllocationConsistencyService
from web.backend.app.services.research_first_gate import ResearchFirstGateService


ROOT = Path(__file__).resolve().parents[3]


def read_latest() -> dict:
    return json.loads((ROOT / "research" / "latest_index.json").read_text(encoding="utf-8-sig"))


def read_current_module(module: str) -> dict:
    latest = read_latest()
    path = latest["modules"][module]["path"]
    assert "files" not in latest["modules"][module]
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def connect(web_db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(web_db)
    conn.row_factory = sqlite3.Row
    return conn


def test_current_modules_is_database_form_of_latest_index_modules(web_db):
    latest = read_latest()
    expected = {module: ref["path"] for module, ref in latest["modules"].items()}
    with connect(web_db) as conn:
        actual = {
            row["module"]: row["path"]
            for row in conn.execute(
                """
                SELECT cm.module, a.path
                FROM current_modules cm
                JOIN artifacts a ON a.id = cm.artifact_id
                """
            )
        }
    assert actual == expected


def test_action_plan_is_split_into_plan_actions_and_research_first(web_db):
    source = read_current_module("action_plan")
    with connect(web_db) as conn:
        plan = conn.execute("SELECT generated_at, basis_trade_date FROM action_plans ORDER BY id DESC LIMIT 1").fetchone()
        action_count = conn.execute("SELECT COUNT(*) AS count FROM action_items").fetchone()["count"]
        research_first_count = conn.execute("SELECT COUNT(*) AS count FROM research_first_items").fetchone()["count"]
    assert plan["generated_at"] == source["generated_at"]
    assert plan["basis_trade_date"] == source["basis_trade_date"]
    assert action_count == len(source.get("actions") or [])
    assert research_first_count == len(source.get("research_first_list") or [])


def test_target_allocation_is_split_into_header_and_buckets(web_db):
    source = read_current_module("target_allocation")
    source_buckets = {row["key"]: row for row in source["actual_allocation_overlay"]["buckets"]}
    with connect(web_db) as conn:
        target = conn.execute(
            """
            SELECT generated_at, basis_trade_date, equity_min_pct, equity_max_pct,
                   cash_min_pct, cash_max_pct
            FROM target_allocations
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        buckets = {
            row["bucket"]: row
            for row in conn.execute("SELECT bucket, actual_pct, target_pct, gap_pct FROM bucket_allocations")
        }
    assert target["generated_at"] == source["generated_at"]
    assert target["basis_trade_date"] == source["basis_trade_date"]
    assert set(buckets) == set(source_buckets)
    for bucket, expected in source_buckets.items():
        actual = buckets[bucket]
        assert float(actual["actual_pct"]) == float(expected["actual_pct"])
        assert float(actual["target_pct"]) == float(expected["target_pct"])
        assert float(actual["gap_pct"]) == float(expected["gap_pct"])


def test_intraday_rules_split_and_allocation_consistency(web_db):
    source = read_current_module("intraday_rules")
    source_buckets = {row["key"]: row for row in source["allocation_map"]["buckets"]}
    with connect(web_db) as conn:
        rules = conn.execute("SELECT status, risk_mode FROM intraday_rules ORDER BY id DESC LIMIT 1").fetchone()
        buckets = {
            row["bucket"]: row
            for row in conn.execute("SELECT bucket, actual_pct, target_pct, gap_pct FROM intraday_bucket_rules")
        }
    assert rules["status"] == source["staleness"]["status"]
    assert rules["risk_mode"] == source["global_gate"]["default_market_gate"]
    assert set(buckets) == set(source_buckets)
    for bucket, expected in source_buckets.items():
        actual = buckets[bucket]
        for field in ["actual_pct", "target_pct", "gap_pct"]:
            assert abs(float(actual[field]) - float(expected[field])) <= 0.05
    with SessionLocal() as session:
        assert AllocationConsistencyService(session).check()["status"] == "ok"


def test_portfolio_snapshot_persists_only_ratio_fields(web_db):
    source = read_current_module("portfolio_snapshot")
    summary = source["summary"]
    with connect(web_db) as conn:
        snapshot = conn.execute(
            "SELECT generated_at, equity_pct, cash_short_pct FROM portfolio_snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()
        position_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(portfolio_positions)")
        }
    assert snapshot["generated_at"] == source["generated_at"]
    assert float(snapshot["equity_pct"]) == float(summary["equity_weight_pct"])
    assert float(snapshot["cash_short_pct"]) == float(summary["bond_cash_weight_pct"])
    assert {"position_pct", "bucket", "reference_only_flag"} <= position_columns
    assert "market_value" not in position_columns
    assert "shares" not in position_columns
    assert "account" not in position_columns


def test_liquidity_gate_registry_maps_to_liquidity_gates(web_db):
    source = read_current_module("liquidity_gate_registry")
    gate = source["instruments"]["511360"]
    with connect(web_db) as conn:
        row = conn.execute(
            """
            SELECT lg.liquidity_status, lg.valuation_status,
                   lg.duration_boundary_confirmed, lg.interest_rate_risk_disclosed,
                   lg.credit_risk_disclosed, lg.liquidity_risk_disclosed
            FROM liquidity_gates lg
            JOIN subjects s ON s.id = lg.subject_id
            WHERE s.code = '511360.SH'
            """
        ).fetchone()
    assert row["liquidity_status"] == gate["liquidity_status"]
    assert row["valuation_status"] == gate["valuation_status"]
    assert bool(row["duration_boundary_confirmed"]) == bool(gate["duration_boundary_confirmed"])
    assert bool(row["interest_rate_risk_disclosed"]) == bool(gate["interest_rate_risk_disclosed"])
    assert bool(row["credit_risk_disclosed"]) == bool(gate["credit_risk_disclosed"])
    assert bool(row["liquidity_risk_disclosed"]) == bool(gate["liquidity_risk_disclosed"])


def test_decision_log_maps_to_recent_entries(web_db):
    with connect(web_db) as conn:
        count = conn.execute("SELECT COUNT(*) AS count FROM decision_log_entries").fetchone()["count"]
        unsafe_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(decision_log_entries)")
            if row["name"] in {"account", "order", "fill", "market_value", "shares"}
        }
    assert count > 0
    assert unsafe_columns == set()


def test_research_first_gate_status_is_ok(web_db):
    with SessionLocal() as session:
        result = ResearchFirstGateService(session).check()
    assert result["status"] == "ok"
    assert result["failures"] == []
