from __future__ import annotations

import io
import json
import zipfile

from web.backend.tests.test_api_no_forbidden_fields import walk


def test_review_package_json_export_is_current_only_and_safe(client):
    response = client.get("/api/export/review_package?format=json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    data = payload["data"]
    assert data["package"]["mode"] == "current-only"
    for key in [
        "action_plan",
        "target_allocation",
        "intraday_rules",
        "portfolio_snapshot",
        "market_position_mapping",
        "bucket_registry",
        "liquidity_gate_registry",
        "decision_log",
    ]:
        assert key in data
    walk(payload)


def test_review_package_zip_export_contains_sanitized_snapshot(client):
    response = client.get("/api/export/review_package")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = set(archive.namelist())
    assert "manifest.json" in names
    assert "current_snapshot.json" in names
    assert "action_plan.json" in names
    assert "target_allocation.json" in names
    assert "intraday_rules.json" in names
    snapshot = json.loads(archive.read("current_snapshot.json").decode("utf-8"))
    assert snapshot["package"]["mode"] == "current-only"
    walk(snapshot)
