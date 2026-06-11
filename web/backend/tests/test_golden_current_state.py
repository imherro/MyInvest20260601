from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from web.backend.app.db import SessionLocal
from web.backend.app.services.research_first_gate import ResearchFirstGateService


ROOT = Path(__file__).resolve().parents[3]
BUCKETS = ["cash_short", "core_base", "attack_mainline", "defense", "legacy_watch"]


def read_latest() -> dict:
    return json.loads((ROOT / "research" / "latest_index.json").read_text(encoding="utf-8-sig"))


def read_module(latest: dict, module: str) -> dict:
    ref = latest["modules"][module]
    path = ref["path"]
    assert not Path(path).is_absolute()
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def parse_range(text: str) -> tuple[float, float]:
    cleaned = text.replace("%", "").replace("pp", "")
    values = [float(item) for item in re.findall(r"\d+(?:\.\d+)?", cleaned)]
    assert values
    if len(values) == 1:
        return values[0], values[0]
    return values[0], values[1]


def conn(web_db: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(web_db)
    connection.row_factory = sqlite3.Row
    return connection


def approx_equal(left: float, right: float, tolerance: float = 0.0001) -> bool:
    return abs(float(left) - float(right)) <= tolerance


def test_current_state_matches_golden_research_json(web_db):
    latest = read_latest()
    action_ref = latest["modules"]["action_plan"]
    action_json = read_module(latest, "action_plan")
    target_json = read_module(latest, "target_allocation")
    intraday_json = read_module(latest, "intraday_rules")
    liquidity_json = read_module(latest, "liquidity_gate_registry")

    with closing(conn(web_db)) as db:
        action_source = db.execute(
            """
            SELECT a.path
            FROM current_modules cm
            JOIN artifacts a ON a.id = cm.artifact_id
            WHERE cm.module = 'action_plan'
            """
        ).fetchone()
        action_plan = db.execute("SELECT generated_at FROM action_plans ORDER BY id DESC LIMIT 1").fetchone()
        action_count = db.execute("SELECT COUNT(*) AS count FROM action_items").fetchone()["count"]
        research_first_count = db.execute("SELECT COUNT(*) AS count FROM research_first_items").fetchone()["count"]
        target = db.execute(
            """
            SELECT equity_min_pct, equity_max_pct
            FROM target_allocations
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        buckets = {
            row["bucket"]: row
            for row in db.execute("SELECT bucket, actual_pct, target_pct, gap_pct FROM bucket_allocations")
        }
        intraday = db.execute("SELECT status FROM intraday_rules ORDER BY id DESC LIMIT 1").fetchone()
        gate_511360 = db.execute(
            """
            SELECT lg.liquidity_status, lg.valuation_status,
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

    assert action_source["path"] == action_ref["path"]
    assert action_plan["generated_at"] == action_json["generated_at"]
    assert action_count == len(action_json.get("actions") or [])
    assert research_first_count == len(action_json.get("research_first_list") or [])

    expected_equity_range = parse_range(target_json["summary"]["recommended_equity_range"])
    assert approx_equal(target["equity_min_pct"], expected_equity_range[0])
    assert approx_equal(target["equity_max_pct"], expected_equity_range[1])

    source_buckets = {item["key"]: item for item in target_json["actual_allocation_overlay"]["buckets"]}
    assert set(BUCKETS) <= set(source_buckets)
    assert set(BUCKETS) <= set(buckets)
    for bucket in BUCKETS:
        source = source_buckets[bucket]
        actual = buckets[bucket]
        assert approx_equal(actual["target_pct"], source["target_pct"])
        assert approx_equal(actual["actual_pct"], source["actual_pct"])
        assert approx_equal(actual["gap_pct"], source["gap_pct"])

    assert intraday["status"] == intraday_json["staleness"]["status"]
    with SessionLocal() as session:
        assert ResearchFirstGateService(session).check()["status"] == "ok"

    expected_gate = liquidity_json["instruments"]["511360"]
    assert gate_511360["liquidity_status"] == expected_gate["liquidity_status"]
    assert gate_511360["valuation_status"] == expected_gate["valuation_status"]
    assert bool(gate_511360["duration_boundary_confirmed"]) == bool(expected_gate["duration_boundary_confirmed"])
    assert bool(gate_511360["interest_rate_risk_disclosed"]) == bool(expected_gate["interest_rate_risk_disclosed"])
    assert bool(gate_511360["credit_risk_disclosed"]) == bool(expected_gate["credit_risk_disclosed"])
    assert bool(gate_511360["liquidity_risk_disclosed"]) == bool(expected_gate["liquidity_risk_disclosed"])
    assert gate_511360["profile_path"] == expected_gate["source_profile"]
    assert gate_511360["valuation_path"] == expected_gate["valuation_source"]
