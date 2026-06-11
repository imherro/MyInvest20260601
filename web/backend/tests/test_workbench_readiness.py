from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from web.backend.app.db import SessionLocal
from web.backend.app.services import workbench_readiness as readiness_module
from web.backend.app.services.ratio_only import RatioOnlyService
from web.backend.app.services.workbench_readiness import WorkbenchReadinessService


ALLOWED_STATUSES = {"ok", "degraded", "mismatch", "unavailable"}
FORBIDDEN_TERMS = [
    "account",
    "masked_account",
    "cost_price",
    "current_price",
    "market_value",
    "shares",
    "quantity",
    "qty",
    "total_asset",
    "total_amount",
    "trade_amount",
    "C:" + "/Users/",
    "C:" + "\\Users\\",
    "/" + "Users/",
    "/" + "home/",
]


def _assert_readiness_payload(payload: dict[str, Any]) -> None:
    assert payload["module"] == "workbench_readiness"
    assert payload["status"] in ALLOWED_STATUSES
    assert isinstance(payload["checked_at"], str)
    assert isinstance(payload["checks"], list)
    assert payload["checks"]
    assert isinstance(payload["summary"], dict)
    assert isinstance(payload["degraded_reasons"], list)
    assert isinstance(payload["fail_closed"], bool)
    assert isinstance(payload["web_smoke_compatible"], bool)
    safety = payload["safety"]
    for key in ["read_only", "ratio_only", "current_only", "research_first", "get_only"]:
        assert safety[key] is True
    assert safety["no_validation_commands"] is True
    assert safety["no_file_writes"] is True
    assert safety["no_sqlite_writes"] is True
    assert safety["uses_latest_index_files"] is False
    for check in payload["checks"]:
        assert check["status"] in ALLOWED_STATUSES
        assert isinstance(check["summary"], dict)
        assert isinstance(check["degraded_reasons"], list)
        assert isinstance(check["fail_closed"], bool)
        assert isinstance(check["web_smoke_compatible"], bool)
    RatioOnlyService.assert_safe(payload)


def _assert_no_forbidden_terms(payload: dict[str, Any]) -> None:
    text = RatioOnlyService.safe_json(payload).lower()
    for term in FORBIDDEN_TERMS:
        assert term.lower() not in text


def test_readiness_summary_api_is_safe(client):
    response = client.get("/api/readiness/summary")

    assert response.status_code == 200
    wrapped = response.json()
    assert wrapped["ok"] is True
    payload = wrapped["data"]
    _assert_readiness_payload(payload)
    assert payload["status"] in {"ok", "degraded"}
    assert payload["web_smoke_compatible"] is True
    assert payload["summary"]["check_count"] >= 6
    _assert_no_forbidden_terms(wrapped)


def test_readiness_checks_api_is_safe(client):
    response = client.get("/api/readiness/checks")

    assert response.status_code == 200
    wrapped = response.json()
    assert wrapped["ok"] is True
    payload = wrapped["data"]
    _assert_readiness_payload(payload)
    assert {check["name"] for check in payload["checks"]} >= {
        "environment_settings",
        "schema_diagnostics",
        "historical_metrics_diagnostics",
        "dashboard_summary",
        "audit_bundle_availability",
        "current_validation_summary",
    }
    _assert_no_forbidden_terms(wrapped)


def test_readiness_signal_failure_degrades_without_raw_exception(monkeypatch):
    def fail_status(self):  # noqa: ANN001
        raise RuntimeError("C:/Users/private validation command output")

    monkeypatch.setattr(readiness_module.SchemaGuardService, "status", fail_status)

    with SessionLocal() as session:
        payload = WorkbenchReadinessService(session).summary()

    _assert_readiness_payload(payload)
    assert payload["status"] == "degraded"
    assert "schema_diagnostics_unavailable" in payload["degraded_reasons"]
    _assert_no_forbidden_terms(payload)


def test_readiness_service_does_not_run_commands_or_write_files(monkeypatch):
    def fail_call(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("unexpected command or write call")

    monkeypatch.setattr(subprocess, "run", fail_call)
    monkeypatch.setattr(Path, "write_text", fail_call)
    monkeypatch.setattr(Path, "write_bytes", fail_call)

    with SessionLocal() as session:
        payload = WorkbenchReadinessService(session).checks()

    _assert_readiness_payload(payload)
    assert payload["safety"]["no_validation_commands"] is True


def test_readiness_api_is_get_only(client):
    schema = client.get("/openapi.json").json()

    for path, methods in schema.get("paths", {}).items():
        if path.startswith("/api/"):
            assert not (set(methods) & {"post", "put", "patch", "delete"}), path
    assert set(schema["paths"]["/api/readiness/summary"]) == {"get"}
    assert set(schema["paths"]["/api/readiness/checks"]) == {"get"}


def test_readiness_service_source_has_no_validation_command_execution():
    source = (Path(__file__).resolve().parents[1] / "app" / "services" / "workbench_readiness.py").read_text(
        encoding="utf-8"
    )

    forbidden_source_terms = [
        "subprocess",
        "project_check.py",
        "web_check.py",
        "pytest",
        "ingest_current_state",
        "check_ratio_only",
        "check_research_first_gate",
        "check_cross_file_allocation_consistency",
        ".write_text(",
        ".write_bytes(",
    ]
    for term in forbidden_source_terms:
        assert term not in source
