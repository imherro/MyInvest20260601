from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from web.backend.app.db import SessionLocal
from web.backend.app.services.ratio_only import RatioOnlyService
from web.backend.app.services.target_allocation_generation import BUCKET_ORDER, TargetAllocationGenerationService


ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "temp" / "web_db" / "myinvest.sqlite"


def conn(web_db: Path) -> sqlite3.Connection:
    assert web_db == DB_PATH
    connection = sqlite3.connect(web_db)
    connection.row_factory = sqlite3.Row
    return connection


def read_latest_target_reference() -> dict[str, Any]:
    latest = json.loads((ROOT / "research" / "latest_index.json").read_text(encoding="utf-8-sig"))
    path = latest["modules"]["target_allocation"]["path"]
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def approx(left: Any, right: Any, tolerance: float = 0.0001) -> bool:
    return abs(float(left) - float(right)) <= tolerance


def assert_ratio_only(value: Any) -> None:
    RatioOnlyService.assert_safe(value)


def current_db_state(web_db: Path) -> dict[str, Any]:
    with conn(web_db) as db:
        modules = [dict(row) for row in db.execute("SELECT module, artifact_id, updated_at FROM current_modules ORDER BY module")]
        current_artifacts = [
            dict(row)
            for row in db.execute("SELECT module, path, is_current FROM artifacts WHERE is_current = 1 ORDER BY module, path")
        ]
        artifact_count = db.execute("SELECT COUNT(*) AS count FROM artifacts").fetchone()["count"]
    allocation_files = sorted(path.relative_to(ROOT).as_posix() for path in (ROOT / "research" / "allocation").glob("target_allocation_*.json"))
    latest_bytes = (ROOT / "research" / "latest_index.json").read_bytes()
    return {
        "modules": modules,
        "current_artifacts": current_artifacts,
        "artifact_count": artifact_count,
        "allocation_files": allocation_files,
        "latest_bytes": latest_bytes,
    }


def test_shadow_service_can_generate_ratio_only(web_db):
    with SessionLocal() as session:
        shadow = TargetAllocationGenerationService(session).generate_shadow_current()
    assert shadow["mode"] == "shadow"
    assert shadow["source"] == "db.TargetAllocationGenerationService.shadow"
    assert {row["key"] for row in shadow["buckets"]} == set(BUCKET_ORDER)
    assert_ratio_only(shadow)


def test_shadow_uses_market_position_service(web_db):
    class FakeMarketPosition:
        def get_current_market_position(self):
            return {
                "score": 50.0,
                "label": "test_state",
                "market_score_state": "test_state",
                "basis_trade_date": "test",
                "equity_min_pct": 40.0,
                "equity_max_pct": 60.0,
                "cash_min_pct": 40.0,
                "cash_max_pct": 60.0,
            }

    with SessionLocal() as session:
        service = TargetAllocationGenerationService(session)
        service.market_position = FakeMarketPosition()
        shadow = service.generate_shadow_current()
    assert shadow["market_score"] == 50.0
    assert shadow["equity_range"] == {"min_pct": 40.0, "max_pct": 60.0, "center_pct": 50.0}
    assert shadow["cash_short_range"] == {"min_pct": 40.0, "max_pct": 60.0, "center_pct": 50.0}
    buckets = {row["key"]: row for row in shadow["buckets"]}
    assert approx(buckets["cash_short"]["target_pct"], 50.0)
    assert approx(buckets["core_base"]["target_pct"], 28.5)
    assert approx(buckets["attack_mainline"]["target_pct"], 7.0)
    assert approx(buckets["defense"]["target_pct"], 14.5)


def test_shadow_vs_current_json_golden_compare(web_db):
    reference = read_latest_target_reference()
    reference_buckets = {
        item["key"]: item for item in (reference["actual_allocation_overlay"]["buckets"] or [])
    }
    with SessionLocal() as session:
        service = TargetAllocationGenerationService(session)
        shadow = service.generate_shadow_current()
        comparison = service.compare_with_current_json()
    assert comparison["matched"] is True
    assert comparison["diffs"] == []
    assert comparison["unsupported_fields"] == []
    assert comparison["source_reference"] == json.loads((ROOT / "research" / "latest_index.json").read_text(encoding="utf-8-sig"))["modules"]["target_allocation"]["path"]
    assert shadow["market_score"] == reference["summary"]["market_position_score"]
    for bucket in BUCKET_ORDER:
        actual = {row["key"]: row for row in shadow["buckets"]}[bucket]
        expected = reference_buckets[bucket]
        for field in ["actual_pct", "target_pct", "gap_pct"]:
            assert approx(actual[field], expected[field]), f"{bucket}.{field}"


def test_shadow_bucket_values_match_intraday_rules(web_db):
    with SessionLocal() as session:
        shadow = TargetAllocationGenerationService(session).generate_shadow_current()
    with conn(web_db) as db:
        rows = db.execute(
            """
            SELECT ibr.bucket, ibr.actual_pct, ibr.target_pct, ibr.gap_pct
            FROM intraday_bucket_rules ibr
            JOIN intraday_rules ir ON ir.id = ibr.intraday_rules_id
            WHERE ir.id = (SELECT MAX(id) FROM intraday_rules)
            """
        ).fetchall()
    intraday = {row["bucket"]: row for row in rows}
    for row in shadow["buckets"]:
        expected = intraday[row["key"]]
        for field in ["actual_pct", "target_pct", "gap_pct"]:
            assert approx(row[field], expected[field], tolerance=0.05), f"{row['key']}.{field}"


def test_shadow_apis_are_ratio_only(client):
    for path in ["/api/target-allocation/shadow", "/api/target-allocation/shadow/compare"]:
        response = client.get(path)
        assert response.status_code == 200, path
        payload = response.json()
        assert payload["ok"] is True
        assert_ratio_only(payload)


def test_shadow_service_and_api_do_not_mutate_current_state(web_db, client):
    before = current_db_state(web_db)
    with SessionLocal() as session:
        service = TargetAllocationGenerationService(session)
        service.generate_shadow_current()
        service.compare_with_current_json()
    for path in ["/api/target-allocation/shadow", "/api/target-allocation/shadow/compare"]:
        assert client.get(path).status_code == 200
    after = current_db_state(web_db)
    assert after == before


def test_shadow_service_does_not_read_latest_index_files_or_hardcode_timestamps():
    path = ROOT / "web" / "backend" / "app" / "services" / "target_allocation_generation.py"
    text = path.read_text(encoding="utf-8")
    assert "latest_index.files" not in text
    assert '["files"]' not in text
    assert "['files']" not in text
    assert "target_allocation_2026-" not in text
    assert "market_score_2026-" not in text
    assert "action_plan_2026-" not in text
