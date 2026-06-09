from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from web.backend.app.db import SessionLocal
from web.backend.app.services.market_position import MarketPositionService
from web.backend.app.services.ratio_only import RatioOnlyService


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from project_utils import market_position_for_score  # noqa: E402


BOUNDARY_SCORES = [0, 25, 30, 31, 45, 46, 60, 61, 75, 76, 85, 86, 100]
API_SCORES = [25, 30, 31, 100]


def parse_range(value: Any) -> tuple[float, float]:
    left, right = str(value).replace("%", "").split("-", 1)
    return float(left), float(right)


def approx(left: Any, right: Any, tolerance: float = 0.0001) -> bool:
    return abs(float(left) - float(right)) <= tolerance


def load_mapping_json() -> dict[str, Any]:
    return json.loads((ROOT / "research" / "config" / "market_position_mapping.json").read_text(encoding="utf-8-sig"))


def rows_from_db(web_db: Path) -> list[sqlite3.Row]:
    conn = sqlite3.connect(web_db)
    conn.row_factory = sqlite3.Row
    with conn:
        return conn.execute(
            """
            SELECT score_min, score_max, equity_min_pct, equity_max_pct,
                   cash_min_pct, cash_max_pct, label
            FROM market_position_mappings
            WHERE is_active = 1
            ORDER BY score_min, score_max
            """
        ).fetchall()


def assert_ratio_only(value: Any) -> None:
    RatioOnlyService.assert_safe(value)


def test_market_position_db_mapping_matches_json_config(web_db):
    config_rows = load_mapping_json()["ranges"]
    db_rows = rows_from_db(web_db)
    assert len(db_rows) == len(config_rows)
    for db_row, config_row in zip(db_rows, config_rows, strict=True):
        equity_min, equity_max = parse_range(config_row["equity_allocation_range"])
        cash_min, cash_max = parse_range(config_row["bond_cash_allocation_range"])
        assert approx(db_row["score_min"], config_row["score_min"])
        assert approx(db_row["score_max"], config_row["score_max"])
        assert approx(db_row["equity_min_pct"], equity_min)
        assert approx(db_row["equity_max_pct"], equity_max)
        assert approx(db_row["cash_min_pct"], cash_min)
        assert approx(db_row["cash_max_pct"], cash_max)
        assert db_row["label"] == config_row["market_state"]


def test_market_position_service_matches_old_project_utils(web_db):
    with SessionLocal() as session:
        service = MarketPositionService(session)
        for score in BOUNDARY_SCORES:
            expected = market_position_for_score(score)
            assert expected is not None
            equity_min, equity_max = parse_range(expected["equity_allocation_range"])
            cash_min, cash_max = parse_range(expected["bond_cash_allocation_range"])
            actual = service.get_position_for_score(score)
            assert actual["score"] == float(score)
            assert actual["label"] == expected["market_state"]
            assert approx(actual["equity_min_pct"], equity_min)
            assert approx(actual["equity_max_pct"], equity_max)
            assert approx(actual["cash_min_pct"], cash_min)
            assert approx(actual["cash_max_pct"], cash_max)
            assert actual["source"] == "db.market_position_mappings"
            assert_ratio_only(actual)


def test_current_market_position_matches_target_allocation_range(web_db):
    conn = sqlite3.connect(web_db)
    conn.row_factory = sqlite3.Row
    with conn:
        target = conn.execute(
            """
            SELECT equity_min_pct, equity_max_pct, cash_min_pct, cash_max_pct
            FROM target_allocations
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    with SessionLocal() as session:
        current = MarketPositionService(session).get_current_market_position()
    assert approx(current["equity_min_pct"], target["equity_min_pct"])
    assert approx(current["equity_max_pct"], target["equity_max_pct"])
    assert approx(current["cash_min_pct"], target["cash_min_pct"])
    assert approx(current["cash_max_pct"], target["cash_max_pct"])
    assert current["source"] == "db.market_position_mappings"
    assert_ratio_only(current)


def test_market_position_api_outputs_are_ratio_only(client):
    paths = [
        "/api/market-position/mapping",
        "/api/market-position/current",
        *[f"/api/market-position/score/{score}" for score in API_SCORES],
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
        payload = response.json()
        assert payload["ok"] is True
        assert_ratio_only(payload)


def test_market_position_api_boundary_scores(client):
    expected = {
        25: "极弱/风险收缩",
        30: "极弱/风险收缩",
        31: "弱势震荡",
        100: "强趋势且风险未失控",
    }
    for score, label in expected.items():
        response = client.get(f"/api/market-position/score/{score}")
        assert response.status_code == 200
        data = response.json()["data"]["market_position"]
        assert data["label"] == label
        assert data["source"] == "db.market_position_mappings"


def test_market_position_api_invalid_scores_do_not_leak(client):
    for path in [
        "/api/market-position/score/-1",
        "/api/market-position/score/101",
        "/api/market-position/score/abc",
    ]:
        response = client.get(path)
        assert response.status_code in {404, 422}, path
        assert response.status_code != 500
        assert_ratio_only(response.json())


def test_market_position_service_does_not_read_latest_index_files():
    path = ROOT / "web" / "backend" / "app" / "services" / "market_position.py"
    text = path.read_text(encoding="utf-8")
    assert "latest_index.files" not in text
    assert '["files"]' not in text
    assert "['files']" not in text
