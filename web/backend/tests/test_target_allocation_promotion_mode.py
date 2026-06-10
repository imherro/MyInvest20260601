from __future__ import annotations

from pathlib import Path

from web.backend.app.services.ratio_only import RatioOnlyService
from web.backend.app.services.target_allocation_mode import get_target_allocation_mode


ROOT = Path(__file__).resolve().parents[3]


def current_state_snapshot() -> dict[str, object]:
    return {
        "latest_index": (ROOT / "research" / "latest_index.json").read_bytes(),
        "allocation_files": sorted(item.name for item in (ROOT / "research" / "allocation").glob("target_allocation_*.json")),
        "action_files": sorted(item.name for item in (ROOT / "research" / "actions").glob("action_plan_*.json")),
    }


def assert_safe_status(value):
    payload = value.as_dict()
    RatioOnlyService.assert_safe(payload)
    return payload


def test_target_allocation_mode_defaults_to_safe_shadow(monkeypatch):
    monkeypatch.delenv("MYINVEST_TARGET_ALLOCATION_MODE", raising=False)
    payload = assert_safe_status(get_target_allocation_mode())
    assert payload == {
        "mode": "shadow",
        "status": "allowed",
        "reason": "mode is read-only or export-only and cannot write current research state",
        "source": "MYINVEST_TARGET_ALLOCATION_MODE",
    }


def test_target_allocation_mode_allows_current_safe_modes():
    for mode in ["reference", "shadow", "controlled_export"]:
        payload = assert_safe_status(get_target_allocation_mode(mode))
        assert payload["mode"] == mode
        assert payload["status"] == "allowed"


def test_target_allocation_mode_blocks_candidate_and_official():
    for mode in ["candidate", "official"]:
        payload = assert_safe_status(get_target_allocation_mode(mode))
        assert payload["mode"] == mode
        assert payload["status"] == "blocked"
        assert "design-only" in payload["reason"]


def test_target_allocation_mode_blocks_unknown_values():
    payload = assert_safe_status(get_target_allocation_mode("write_current"))
    assert payload["mode"] == "write_current"
    assert payload["status"] == "blocked"
    assert payload["reason"] == "unknown target allocation mode"


def test_target_allocation_mode_does_not_mutate_current_state():
    before = current_state_snapshot()
    for mode in ["reference", "shadow", "controlled_export", "candidate", "official", "write_current"]:
        get_target_allocation_mode(mode).as_dict()
    assert current_state_snapshot() == before
