from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from web.backend.app.services.ratio_only import RatioOnlyService
from web.backend.app.services.target_allocation_generation import BUCKET_ORDER, TargetAllocationGenerationService


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT / "web" / "backend" / "tests" / "fixtures" / "target_allocation_scenarios"
LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:(?!//)[\\/]|\\\\|/Users/|/home/)")
FORBIDDEN_VALUE_TERMS = [
    "total_asset",
    "market_value",
    "shares",
    "quantity",
    "available_quantity",
    "trade_amount",
    "profit_amount",
    "full_account",
    ".env",
    "总资产",
    "金额",
    "市值",
    "股数",
    "可用数量",
    "交易金额",
    "盈亏金额",
    "账号",
    "订单",
    "成交",
]


def scenario_paths() -> list[Path]:
    return sorted(FIXTURE_DIR.glob("*.json"))


def load_scenario(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def current_state_snapshot() -> dict[str, Any]:
    return {
        "latest_index": (ROOT / "research" / "latest_index.json").read_bytes(),
        "allocation_files": sorted(item.name for item in (ROOT / "research" / "allocation").glob("target_allocation_*.json")),
        "action_files": sorted(item.name for item in (ROOT / "research" / "actions").glob("action_plan_*.json")),
    }


def assert_replay_safe(value: Any) -> None:
    RatioOnlyService.assert_safe(value)
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    assert not LOCAL_PATH_RE.search(text)
    lowered = text.lower()
    for term in FORBIDDEN_VALUE_TERMS:
        assert term.lower() not in lowered


def approx(left: Any, right: Any) -> bool:
    return abs(float(left) - float(right)) <= 0.0001


@pytest.mark.parametrize("path", scenario_paths(), ids=lambda path: path.stem)
def test_target_allocation_shadow_replay_matches_fixture(path):
    scenario = load_scenario(path)
    assert_replay_safe(scenario)

    shadow = TargetAllocationGenerationService.generate_shadow_from_inputs(
        market_score=scenario["market_score"],
        market_position_mapping=scenario["market_position_mapping"],
        actual_by_bucket=scenario["portfolio_bucket_actual"],
        bucket_registry=scenario["bucket_registry"],
        scenario_name=scenario["name"],
    )

    assert_replay_safe(shadow)
    expected = scenario["expected"]
    for field in [
        "market_score",
        "market_state",
        "equity_range",
        "cash_short_range",
        "target_equity_pct",
        "target_cash_short_pct",
        "actual_equity_pct",
        "actual_cash_short_pct",
        "warnings",
    ]:
        assert shadow[field] == expected[field], field

    actual_buckets = {row["key"]: row for row in shadow["buckets"]}
    expected_buckets = {row["key"]: row for row in expected["buckets"]}
    assert set(actual_buckets) == set(BUCKET_ORDER)
    assert set(expected_buckets) == set(BUCKET_ORDER)
    for bucket in BUCKET_ORDER:
        for field in ["actual_pct", "target_pct", "gap_pct"]:
            assert approx(actual_buckets[bucket][field], expected_buckets[bucket][field]), f"{path.name}:{bucket}.{field}"


def test_target_allocation_replay_boundary_scores_are_explicit():
    boundary_30 = load_scenario(FIXTURE_DIR / "boundary_score_30.json")["expected"]
    boundary_31 = load_scenario(FIXTURE_DIR / "boundary_score_31.json")["expected"]
    max_score = load_scenario(FIXTURE_DIR / "max_score_100.json")["expected"]

    assert boundary_30["market_state"] == "risk_off"
    assert boundary_30["equity_range"] == {"min_pct": 30.0, "max_pct": 40.0, "center_pct": 35.0}
    assert boundary_31["market_state"] == "weak_choppy"
    assert boundary_31["equity_range"] == {"min_pct": 40.0, "max_pct": 45.0, "center_pct": 42.5}
    assert max_score["market_state"] == "max_trend"
    assert max_score["cash_short_range"] == {"min_pct": 15.0, "max_pct": 25.0, "center_pct": 20.0}


def test_target_allocation_replay_missing_bucket_policy_is_documented():
    scenario = load_scenario(FIXTURE_DIR / "missing_bucket_position.json")
    shadow = TargetAllocationGenerationService.generate_shadow_from_inputs(
        market_score=scenario["market_score"],
        market_position_mapping=scenario["market_position_mapping"],
        actual_by_bucket=scenario["portfolio_bucket_actual"],
        bucket_registry=scenario["bucket_registry"],
        scenario_name=scenario["name"],
    )
    assert shadow["warnings"] == [
        {
            "code": "missing_bucket_actual",
            "bucket": "defense",
            "message": "bucket actual missing; treated as 0 pct",
        }
    ]
    defense = {row["key"]: row for row in shadow["buckets"]}["defense"]
    assert defense["actual_pct"] == 0.0
    assert defense["gap_pct"] == -14.5


def test_target_allocation_replay_does_not_mutate_current_state(web_db):
    before = current_state_snapshot()
    for path in scenario_paths():
        scenario = load_scenario(path)
        TargetAllocationGenerationService.generate_shadow_from_inputs(
            market_score=scenario["market_score"],
            market_position_mapping=scenario["market_position_mapping"],
            actual_by_bucket=scenario["portfolio_bucket_actual"],
            bucket_registry=scenario["bucket_registry"],
            scenario_name=scenario["name"],
        )
    assert current_state_snapshot() == before


def test_target_allocation_replay_code_paths_are_fixture_only():
    service_path = ROOT / "web" / "backend" / "app" / "services" / "target_allocation_generation.py"
    text = service_path.read_text(encoding="utf-8")
    assert "latest_index.files" not in text
    assert '["files"]' not in text
    assert "['files']" not in text
    assert "target_allocation_2026-" not in text
    assert "market_score_2026-" not in text
    assert "action_plan_2026-" not in text
