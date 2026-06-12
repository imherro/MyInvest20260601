from __future__ import annotations

import json
import re
from typing import Any

import pytest

from web.backend.app.db import SessionLocal
from web.backend.app.repositories.audit_bundle_repo import AuditBundleRepository


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


def assert_audit_payload_safe(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)
    assert not LOCAL_PATH_RE.search(serialized)
    for path, item in walk(payload):
        if isinstance(item, str):
            assert not LOCAL_PATH_RE.search(item), path
        assert not FORBIDDEN_KEY_RE.search(str(item)), path


def test_audit_bundle_api_returns_safe_bundle(client):
    response = client.get("/api/audit/bundle")
    assert response.status_code == 200
    payload = response.json()
    data = payload["data"]
    assert data["module"] == "workbench_audit_bundle"
    assert data["current_only"] is True
    assert data["ratio_only"] is True
    assert data["read_only"] is True
    assert data["summary"]["section_count"] >= 4
    labels = {item["label"] for item in data["sections"]}
    assert labels >= {"Dashboard", "Preferences", "Historical Metrics", "Workbench Integration"}
    assert data["preview_chart"]
    assert data["safety"]["openapi_get_only"] is True
    assert_audit_payload_safe(payload)


def test_audit_bundle_api_supports_window_and_module_switch(client):
    response = client.get("/api/audit/bundle?time_window=7d&module_filter=dashboard")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["window"]["selected"] == "7d"
    assert data["module_filter"]["selected"] == "dashboard"
    assert [item["name"] for item in data["sections"]] == ["dashboard"]


def test_audit_page_and_script_hooks(client):
    response = client.get("/audit")
    assert response.status_code == 200
    html = response.text
    assert "Workbench Audit" in html
    assert "/api/audit/bundle" in html
    assert "data-audit-section=\"summary\"" in html
    assert "data-audit-window" in html
    assert "data-audit-module" in html
    assert "Export Review Package" in html
    assert "/api/export/review_package" in html
    assert "History Tools" in html
    assert "auditPreviewChart" in html
    assert "auditBundleRows" in html
    assert "/static/audit.js" in html
    assert not LOCAL_PATH_RE.search(html)

    script = client.get("/static/audit.js")
    assert script.status_code == 200
    assert "function refreshAudit" in script.text
    assert "function renderChart" in script.text
    assert "assertSafe" in script.text


def test_audit_bundle_repository_rejects_write_sql():
    with SessionLocal() as session:
        repo = AuditBundleRepository(session)
        with pytest.raises(ValueError):
            repo.one("UPDATE system_check_results SET status = status")
