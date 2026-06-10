from __future__ import annotations

import json
import re
from typing import Any

import pytest

from web.backend.app.db import SessionLocal
from web.backend.app.repositories.workbench_analytics_repo import WorkbenchAnalyticsRepository


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


def assert_analytics_payload_safe(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)
    assert not LOCAL_PATH_RE.search(serialized)
    for path, item in walk(payload):
        if isinstance(item, str):
            assert not LOCAL_PATH_RE.search(item), path
        assert not FORBIDDEN_KEY_RE.search(str(item)), path


def test_dashboard_summary_api_returns_ratio_only_analytics(client):
    response = client.get("/api/dashboard/summary?time_window=7d")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    data = payload["data"]
    assert data["module"] == "workbench_analytics_dashboard"
    assert data["current_only"] is True
    assert data["ratio_only"] is True
    assert data["read_only"] is True
    assert data["window"]["selected"] == "7d"
    assert data["window"]["effective"] == "current_only"
    assert data["metrics"]["current_module_count"] > 0
    assert data["metrics"]["subject_count"] > 0
    assert data["metrics"]["bucket_count"] > 0
    assert data["gates"]["project_check_status"] in {"OK", "PASS", "ok", "unknown"}
    assert data["safety"]["uses_database_service"] is True
    assert data["safety"]["uses_history_snapshot"] is True
    assert_analytics_payload_safe(payload)


def test_dashboard_user_metrics_api_returns_default_or_safe_404(client):
    response = client.get("/api/dashboard/user_metrics/default?time_window=30d")
    assert response.status_code == 200
    payload = response.json()
    data = payload["data"]
    assert data["module"] == "workbench_user_metrics"
    assert data["user_id"] == "default"
    assert data["window"]["selected"] == "30d"
    assert data["preferences"]["refresh_seconds"] == 60
    assert data["metrics"]["current_module_count"] > 0
    assert_analytics_payload_safe(payload)

    response = client.get("/api/dashboard/user_metrics/unknown_user")
    assert response.status_code == 404
    assert response.json()["detail"] == "dashboard user metrics not found"
    assert_analytics_payload_safe(response.json())


def test_dashboard_page_includes_workbench_analytics_hooks(client):
    response = client.get("/dashboard")
    assert response.status_code == 200
    html = response.text
    assert "data-dashboard-section=\"analytics\"" in html
    assert "data-dashboard-window" in html
    assert "dashboardAnalyticsRows" in html
    assert "data-bind=\"dashboard_analytics_modules\"" in html
    assert "data-bind=\"dashboard_analytics_history_entries\"" in html
    assert not LOCAL_PATH_RE.search(html)


def test_workbench_analytics_repository_rejects_write_sql():
    with SessionLocal() as session:
        repo = WorkbenchAnalyticsRepository(session)
        with pytest.raises(ValueError):
            repo.one("UPDATE system_check_results SET status = status")
