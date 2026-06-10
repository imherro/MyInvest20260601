from __future__ import annotations

import io
import json
import zipfile

from sqlalchemy import text

from web.backend.app.db import engine
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


def test_system_check_runtime_messages_are_not_exported(client):
    unsafe_message = (
        "MyInvest project check\n"
        "Root: C:/Users/example/MyInvest\n"
        "Result: 0 FAIL, 2 WARN\n"
        "[WARN] .env is missing; copy .env.example and set TUSHARE_TOKEN\n"
        "[WARN] Python package pandas is not installed"
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE system_check_results
                SET message = :message
                WHERE check_name = 'project_check_current_only'
                """
            ),
            {"message": unsafe_message},
        )

    system_response = client.get("/api/system-check/current")
    assert system_response.status_code == 200
    export_response = client.get("/api/export/review_package?format=json")
    assert export_response.status_code == 200

    combined = system_response.text + export_response.text
    assert ".env is missing" not in combined
    assert "C:/Users/" not in combined
    assert "pandas is not installed" not in combined
    assert "current-only validation passed" in combined
