from __future__ import annotations

from pathlib import Path
from typing import Any

from web.backend.app.db import SessionLocal
from web.backend.app.routers.current import respond
from web.backend.app.services.historical_metrics_guard import (
    REQUIRED_INTEGRATION_PAYLOADS,
    REQUIRED_MODULES,
    REQUIRED_TABLES,
)
from web.backend.app.services.historical_metrics_guard import HistoricalMetricsGuardService
from web.backend.app.services.ratio_only import RatioOnlyService


ROOT = Path(__file__).resolve().parents[3]


class FakeHistoricalMetricsGuardRepository:
    def __init__(
        self,
        *,
        table_counts: dict[str, int] | None = None,
        source_modules: dict[str, dict[str, Any]] | None = None,
        history_snapshot: dict[str, Any] | None = None,
        fail: bool = False,
    ):
        self._table_counts = table_counts if table_counts is not None else {table: 1 for table in REQUIRED_TABLES}
        self._source_modules = source_modules if source_modules is not None else {
            module: {"module": module, "path": f"research/source/{module}.json"} for module in REQUIRED_MODULES
        }
        self._history_snapshot = history_snapshot if history_snapshot is not None else {
            "available": True,
            "history_entry_count": 2,
            "matched_entry_count": 2,
            "generated_at": "2026-06-11T00:00:00Z",
        }
        self.fail = fail

    def table_counts(self, tables: list[str]) -> dict[str, int]:
        if self.fail:
            raise RuntimeError("guard unavailable")
        return {table: self._table_counts.get(table, 0) for table in tables}

    def source_modules(self, modules: list[str]) -> dict[str, dict[str, Any]]:
        return {module: self._source_modules[module] for module in modules if module in self._source_modules}

    def history_snapshot_summary(self) -> dict[str, Any]:
        return self._history_snapshot


def test_historical_metrics_guard_current_db_is_safe(web_db):
    with SessionLocal() as session:
        payload = HistoricalMetricsGuardService(session).status()

    assert payload["status"] in {"ok", "degraded"}
    assert payload["ok"] is True
    assert payload["required_inputs_present"] is True
    assert payload["missing_inputs"] == []
    assert payload["contract"]["contract_version"] == "historical_metrics_guard_v1"
    assert payload["contract"]["fingerprint_match"] is True
    assert len(payload["contract"]["expected_fingerprint"]) == 64
    assert payload["enforcement"]["mode"] == "full_read_only_historical_metrics_guard"
    assert payload["enforcement"]["fail_closed"] is False
    assert payload["enforcement"]["read_model_usable"] is True
    assert payload["enforcement"]["web_smoke_compatible"] is True
    assert payload["enforcement"]["audit_bundle_compatible"] is True
    RatioOnlyService.assert_safe(payload)


def test_historical_metrics_guard_contract_fingerprint_is_deterministic():
    first = HistoricalMetricsGuardService(
        session=None,  # type: ignore[arg-type]
        repository=FakeHistoricalMetricsGuardRepository(),
    ).status()
    second = HistoricalMetricsGuardService(
        session=None,  # type: ignore[arg-type]
        repository=FakeHistoricalMetricsGuardRepository(),
    ).status()

    assert first["contract"]["expected_fingerprint"] == second["contract"]["expected_fingerprint"]
    assert first["contract"]["observed_fingerprint"] == second["contract"]["observed_fingerprint"]
    assert first["contract"]["expected_fingerprint"] == first["contract"]["observed_fingerprint"]
    assert first["contract"]["required_inputs"] == sorted(
        [f"table:{table}" for table in REQUIRED_TABLES]
        + [f"integration:{payload}" for payload in REQUIRED_INTEGRATION_PAYLOADS]
    )


def test_historical_metrics_guard_all_inputs_available_is_ok():
    payload = HistoricalMetricsGuardService(
        session=None,  # type: ignore[arg-type]
        repository=FakeHistoricalMetricsGuardRepository(),
    ).status()

    assert payload["status"] == "ok"
    assert payload["ok"] is True
    assert payload["history_snapshot_available"] is True
    assert payload["enforcement"]["audit_ready"] is True
    assert payload["enforcement"]["fail_closed"] is False
    assert payload["contract"]["fingerprint_match"] is True
    RatioOnlyService.assert_safe(payload)


def test_historical_metrics_guard_missing_optional_history_is_degraded():
    payload = HistoricalMetricsGuardService(
        session=None,  # type: ignore[arg-type]
        repository=FakeHistoricalMetricsGuardRepository(
            history_snapshot={"available": False, "history_entry_count": 0, "matched_entry_count": 0}
        ),
    ).status()

    assert payload["status"] == "degraded"
    assert payload["ok"] is True
    assert payload["history_snapshot_available"] is False
    assert payload["required_inputs_present"] is True
    assert "history_snapshot_unavailable" in payload["diagnostics_warnings"]
    assert payload["contract"]["fingerprint_match"] is True
    assert payload["enforcement"]["fail_closed"] is False
    assert payload["enforcement"]["read_model_usable"] is True


def test_historical_metrics_guard_missing_required_table_is_mismatch():
    counts = {table: 1 for table in REQUIRED_TABLES}
    counts["subjects"] = 0

    payload = HistoricalMetricsGuardService(
        session=None,  # type: ignore[arg-type]
        repository=FakeHistoricalMetricsGuardRepository(table_counts=counts),
    ).status()

    assert payload["status"] == "mismatch"
    assert payload["ok"] is False
    assert payload["required_inputs_present"] is False
    assert "table:subjects" in payload["missing_inputs"]
    assert "table:subjects" in payload["contract"]["missing_inputs"]
    assert payload["contract"]["fingerprint_match"] is False
    assert payload["enforcement"]["fail_closed"] is True
    assert payload["enforcement"]["read_model_usable"] is False


def test_historical_metrics_guard_missing_required_module_is_mismatch():
    sources = {module: {"module": module, "path": f"research/source/{module}.json"} for module in REQUIRED_MODULES}
    sources.pop("market_score")

    payload = HistoricalMetricsGuardService(
        session=None,  # type: ignore[arg-type]
        repository=FakeHistoricalMetricsGuardRepository(source_modules=sources),
    ).status()

    assert payload["status"] == "mismatch"
    assert payload["ok"] is False
    assert "module:market_score" in payload["missing_inputs"]
    assert payload["contract"]["missing_source_modules"] == ["market_score"]
    assert payload["contract"]["fingerprint_match"] is False
    assert payload["enforcement"]["fail_closed"] is True


def test_historical_metrics_guard_unavailable_is_safe():
    payload = HistoricalMetricsGuardService(
        session=None,  # type: ignore[arg-type]
        repository=FakeHistoricalMetricsGuardRepository(fail=True),
    ).status()

    assert payload["status"] == "unavailable"
    assert payload["ok"] is False
    assert payload["enforcement"]["fail_closed"] is True
    assert payload["enforcement"]["read_model_usable"] is False
    assert payload["contract"]["fingerprint_match"] is False
    assert payload["diagnostics_warnings"] == ["historical_metrics_guard_unavailable"]
    RatioOnlyService.assert_safe(payload)


def test_historical_metrics_guard_api_get_is_safe(client):
    response = client.get("/api/diagnostics/historical-metrics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    guard = payload["data"]["historical_metrics_guard"]
    assert guard["status"] in {"ok", "degraded"}
    assert guard["required_inputs_present"] is True
    assert guard["contract"]["fingerprint_match"] is True
    assert guard["contract"]["expected_fingerprint"] == guard["contract"]["observed_fingerprint"]
    assert guard["enforcement"]["web_smoke_compatible"] is True
    assert guard["enforcement"]["audit_bundle_compatible"] is True
    RatioOnlyService.assert_safe(payload)


def test_historical_metrics_guard_payload_passes_api_wrapper_sanitizer():
    payload = {
        "historical_metrics_guard": HistoricalMetricsGuardService(
            session=None,  # type: ignore[arg-type]
            repository=FakeHistoricalMetricsGuardRepository(),
        ).status()
    }

    wrapped = respond(payload, source={"path": "db.HistoricalMetricsGuardRepository"})

    assert wrapped["ok"] is True
    RatioOnlyService.assert_safe(wrapped)


def test_historical_metrics_guard_payload_has_no_forbidden_terms():
    payload = HistoricalMetricsGuardService(
        session=None,  # type: ignore[arg-type]
        repository=FakeHistoricalMetricsGuardRepository(),
    ).status()

    text = RatioOnlyService.safe_json(payload).lower()
    forbidden = [
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
    for term in forbidden:
        assert term.lower() not in text


def test_historical_metrics_guard_repository_has_no_direct_write_sql():
    repo_source = (
        ROOT / "web" / "backend" / "app" / "repositories" / "historical_metrics_guard_repo.py"
    ).read_text(encoding="utf-8")
    service_source = (
        ROOT / "web" / "backend" / "app" / "services" / "historical_metrics_guard.py"
    ).read_text(encoding="utf-8")

    assert "DatabaseService" in repo_source
    assert ".count_table(" in repo_source
    assert ".source_for_module(" in repo_source
    assert ".execute(" not in repo_source
    for token in ["CREATE ", "INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "VACUUM", "REPLACE "]:
        assert token not in repo_source
        assert token not in service_source
