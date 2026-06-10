from __future__ import annotations

import json
import re
from typing import Any


LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:(?!//)[\\/]|\\\\|/Users/|/home/)")
FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(amount|market_value|profit_amount|total_amount|total_asset|share_count|shares|quantity|qty|"
    r"available_qty|available_quantity|trade_amount|account|full_account|order|fill|deal|"
    r"cost_price|raw_cost_price|current_price|qmt_timetag)($|_)",
    re.IGNORECASE,
)


def walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, item in value.items():
            key_path = f"{path}.{key}"
            yield key_path, key
            yield from walk(item, key_path)
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            yield from walk(item, f"{path}[{idx}]")
    else:
        yield path, value


def assert_integration_payload_safe(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)
    assert not LOCAL_PATH_RE.search(serialized)
    for path, item in walk(payload):
        if isinstance(item, str):
            assert not LOCAL_PATH_RE.search(item), path
        assert not FORBIDDEN_KEY_RE.search(str(item)), path


def test_workbench_integration_api_returns_safe_overview(client):
    response = client.get("/api/workbench/integration?time_window=7d")
    assert response.status_code == 200
    payload = response.json()
    data = payload["data"]
    assert data["module"] == "workbench_integration"
    assert data["current_only"] is True
    assert data["ratio_only"] is True
    assert data["read_only"] is True
    assert data["window"]["selected"] == "7d"
    labels = {item["label"] for item in data["modules"]}
    assert labels >= {"Settings", "Preferences", "Dashboard", "Research Centers"}
    assert data["metrics"]["current_module_count"] > 0
    assert data["display"]["refresh_seconds"] == 60
    assert data["safety"]["openapi_get_only"] is True
    assert_integration_payload_safe(payload)


def test_dashboard_page_includes_integration_hooks(client):
    response = client.get("/dashboard")
    assert response.status_code == 200
    html = response.text
    assert "data-dashboard-section=\"workbench-integration\"" in html
    assert "workbenchModuleLinks" in html
    assert "workbenchIntegrationRows" in html
    assert not LOCAL_PATH_RE.search(html)


def test_preferences_page_links_workbench_modules(client):
    response = client.get("/preferences")
    assert response.status_code == 200
    html = response.text
    assert "data-preferences-section=\"workbench-links\"" in html
    assert "/dashboard" in html
    assert "/settings" in html
    assert "/subjects" in html
    assert not LOCAL_PATH_RE.search(html)
