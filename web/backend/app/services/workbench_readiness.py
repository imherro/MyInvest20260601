from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..config import DB_PATH, ROOT
from ..repositories.audit_bundle_repo import AuditBundleRepository
from .historical_metrics_guard import HistoricalMetricsGuardService
from .ratio_only import RatioOnlyService
from .schema_guard import SchemaGuardService
from .system_check import SystemCheckService
from .workbench_analytics import WorkbenchAnalyticsService


ALLOWED_READINESS_STATUSES = {"ok", "degraded", "mismatch", "unavailable"}


class WorkbenchReadinessService:
    """Read-only Workbench readiness aggregation.

    The service intentionally avoids command execution and write paths. It
    reports already-available safe metadata from read-only services and DB
    diagnostics only.
    """

    module = "workbench_readiness"

    def __init__(self, session: Session):
        self.session = session

    def summary(self) -> dict[str, Any]:
        return self._build(include_details=False)

    def checks(self) -> dict[str, Any]:
        return self._build(include_details=True)

    def _build(self, *, include_details: bool) -> dict[str, Any]:
        checked_at = self._checked_at()
        checks = [
            self._read_check("environment_settings", checked_at, self._environment_settings_check),
            self._read_check("schema_diagnostics", checked_at, self._schema_diagnostics_check),
            self._read_check("historical_metrics_diagnostics", checked_at, self._historical_metrics_check),
            self._read_check("dashboard_summary", checked_at, self._dashboard_summary_check),
            self._read_check("audit_bundle_availability", checked_at, self._audit_bundle_check),
            self._read_check("current_validation_summary", checked_at, self._current_validation_check),
        ]
        status = self._overall_status(checks)
        fail_closed = any(bool(check.get("fail_closed")) for check in checks) or status in {"mismatch", "unavailable"}
        web_smoke_compatible = not fail_closed and all(bool(check.get("web_smoke_compatible")) for check in checks)
        degraded_reasons = sorted(
            {
                str(reason)
                for check in checks
                for reason in check.get("degraded_reasons", [])
                if str(reason).strip()
            }
        )
        payload = {
            "module": self.module,
            "status": status,
            "checked_at": checked_at,
            "checks": checks if include_details else [self._compact_check(check) for check in checks],
            "summary": self._summary(checks, web_smoke_compatible),
            "safety": self._safety(),
            "degraded_reasons": degraded_reasons,
            "fail_closed": fail_closed,
            "web_smoke_compatible": web_smoke_compatible,
        }
        return self._safe(payload)

    def _environment_settings_check(self) -> dict[str, Any]:
        repo_path = self._repo_path(DB_PATH)
        db_in_temp = repo_path == "temp/web_db/myinvest.sqlite"
        status = "ok" if db_in_temp and DB_PATH.exists() else "degraded"
        reasons: list[str] = []
        if not db_in_temp:
            status = "mismatch"
            reasons.append("web_db_path_outside_temp")
        elif not DB_PATH.exists():
            reasons.append("web_db_missing")
        return self._check_payload(
            name="environment_settings",
            label="Environment and settings metadata",
            status=status,
            summary={
                "api_path": "/api/environment/status",
                "settings_page": "/settings",
                "environment_page": "/environment",
                "web_db_path": repo_path,
                "web_db_present": DB_PATH.exists(),
                "phase10_development_port": 8010,
            },
            source={"api_path": "/api/environment/status", "metadata": "repo_relative_runtime_paths"},
            degraded_reasons=reasons,
            fail_closed=status == "mismatch",
        )

    def _schema_diagnostics_check(self) -> dict[str, Any]:
        guard = SchemaGuardService(self.session).status()
        status = self._normalize_status(guard.get("status"))
        enforcement = guard.get("enforcement") or {}
        return self._check_payload(
            name="schema_diagnostics",
            label="Schema diagnostics",
            status=status,
            summary={
                "api_path": "/api/diagnostics/schema",
                "expected_schema_version": guard.get("expected_schema_version"),
                "required_tables_present": guard.get("required_tables_present") is True,
                "required_columns_present": guard.get("required_columns_present") is True,
                "warning_count": len(guard.get("diagnostics_warnings") or []),
            },
            source={"api_path": "/api/diagnostics/schema", "service": "SchemaGuardService"},
            degraded_reasons=list(guard.get("diagnostics_warnings") or []),
            fail_closed=bool(enforcement.get("fail_closed")),
            web_smoke_compatible=bool(enforcement.get("web_smoke_compatible")),
        )

    def _historical_metrics_check(self) -> dict[str, Any]:
        guard = HistoricalMetricsGuardService(self.session).status()
        status = self._normalize_status(guard.get("status"))
        enforcement = guard.get("enforcement") or {}
        contract = guard.get("contract") or {}
        return self._check_payload(
            name="historical_metrics_diagnostics",
            label="Historical Metrics diagnostics",
            status=status,
            summary={
                "api_path": "/api/diagnostics/historical-metrics",
                "contract_version": contract.get("contract_version"),
                "required_inputs_present": guard.get("required_inputs_present") is True,
                "history_snapshot_available": guard.get("history_snapshot_available") is True,
                "warning_count": len(guard.get("diagnostics_warnings") or []),
            },
            source={"api_path": "/api/diagnostics/historical-metrics", "service": "HistoricalMetricsGuardService"},
            degraded_reasons=list(guard.get("diagnostics_warnings") or []),
            fail_closed=bool(enforcement.get("fail_closed")),
            web_smoke_compatible=bool(enforcement.get("web_smoke_compatible")),
        )

    def _dashboard_summary_check(self) -> dict[str, Any]:
        dashboard = WorkbenchAnalyticsService(self.session).summary(time_window="current")
        metrics = dashboard.get("metrics") or {}
        gates = dashboard.get("gates") or {}
        safety = dashboard.get("safety") or {}
        ready = bool(metrics) and dashboard.get("read_only") is True and dashboard.get("current_only") is True
        reasons: list[str] = []
        if not ready:
            reasons.append("dashboard_summary_incomplete")
        if safety.get("uses_latest_index_files") is not False:
            ready = False
            reasons.append("dashboard_latest_index_files_flag_unexpected")
        return self._check_payload(
            name="dashboard_summary",
            label="Dashboard summary",
            status="ok" if ready else "degraded",
            summary={
                "api_path": "/api/dashboard/summary",
                "generated_at": dashboard.get("generated_at"),
                "metric_count": len(metrics),
                "gate_count": len(gates),
                "current_module_count": metrics.get("current_module_count", 0),
                "subject_count": metrics.get("subject_count", 0),
            },
            source={"api_path": "/api/dashboard/summary", "service": "WorkbenchAnalyticsService"},
            degraded_reasons=reasons,
        )

    def _audit_bundle_check(self) -> dict[str, Any]:
        repo = AuditBundleRepository(self.session)
        counts = repo.table_counts()
        history = repo.history_snapshot_summary()
        required_tables = ["current_modules", "subjects", "system_check_results"]
        missing = [table for table in required_tables if int(counts.get(table) or 0) <= 0]
        status = "ok" if not missing else "degraded"
        reasons = [f"audit_table_missing:{table}" for table in missing]
        return self._check_payload(
            name="audit_bundle_availability",
            label="Audit bundle availability",
            status=status,
            summary={
                "api_path": "/api/audit/bundle",
                "required_table_count": len(required_tables),
                "available_table_count": len(required_tables) - len(missing),
                "history_snapshot_available": history.get("available") is True,
            },
            source={"api_path": "/api/audit/bundle", "provider": "AuditBundleRepository"},
            degraded_reasons=reasons,
        )

    def _current_validation_check(self) -> dict[str, Any]:
        validation = SystemCheckService(self.session).current()
        checks = validation.get("checks") or []
        status_value = str(validation.get("status") or "unknown").lower()
        if status_value == "ok":
            status = "ok"
        elif status_value == "fail":
            status = "mismatch"
        else:
            status = "degraded"
        reasons = [] if status == "ok" else ["current_validation_status_not_ok"]
        return self._check_payload(
            name="current_validation_summary",
            label="Current validation summary",
            status=status,
            summary={
                "api_path": "/api/system-check/current",
                "recorded_check_count": len(checks),
                "research_first_status": (validation.get("research_first_gate") or {}).get("status", "unknown"),
                "allocation_consistency_status": (validation.get("allocation_consistency") or {}).get(
                    "status",
                    "unknown",
                ),
                "sensitive_scan_status": (validation.get("sensitive_scan") or {}).get("status", "unknown"),
            },
            source={"api_path": "/api/system-check/current", "service": "SystemCheckService"},
            degraded_reasons=reasons,
            fail_closed=status == "mismatch",
            web_smoke_compatible=status in {"ok", "degraded"},
        )

    def _read_check(self, name: str, checked_at: str, reader: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        try:
            check = reader()
            check["checked_at"] = checked_at
            return check
        except Exception:  # noqa: BLE001
            return self._check_payload(
                name=name,
                label=name.replace("_", " ").title(),
                status="degraded",
                summary={"available": False},
                source={"provider": "safe_readiness_wrapper"},
                degraded_reasons=[f"{name}_unavailable"],
                checked_at=checked_at,
            )

    def _check_payload(
        self,
        *,
        name: str,
        label: str,
        status: str,
        summary: dict[str, Any],
        source: dict[str, Any],
        degraded_reasons: list[str] | None = None,
        fail_closed: bool | None = None,
        web_smoke_compatible: bool | None = None,
        checked_at: str | None = None,
    ) -> dict[str, Any]:
        normalized_status = self._normalize_status(status)
        reasons = sorted({str(reason) for reason in degraded_reasons or [] if str(reason).strip()})
        closed = normalized_status in {"mismatch", "unavailable"} if fail_closed is None else fail_closed
        smoke = normalized_status in {"ok", "degraded"} and not closed
        if web_smoke_compatible is not None:
            smoke = bool(web_smoke_compatible) and not closed
        if normalized_status == "degraded" and not reasons:
            reasons = [f"{name}_degraded"]
        return {
            "name": name,
            "label": label,
            "status": normalized_status,
            "ok": normalized_status in {"ok", "degraded"} and not closed,
            "checked_at": checked_at,
            "summary": summary,
            "source": source,
            "degraded_reasons": reasons,
            "fail_closed": closed,
            "web_smoke_compatible": smoke,
            "safety": self._safety(),
        }

    @staticmethod
    def _overall_status(checks: list[dict[str, Any]]) -> str:
        statuses = {str(check.get("status")) for check in checks}
        if "mismatch" in statuses:
            return "mismatch"
        if "unavailable" in statuses:
            return "unavailable"
        if "degraded" in statuses:
            return "degraded"
        return "ok"

    @staticmethod
    def _summary(checks: list[dict[str, Any]], web_smoke_compatible: bool) -> dict[str, Any]:
        status_counts = {status: 0 for status in sorted(ALLOWED_READINESS_STATUSES)}
        for check in checks:
            status = str(check.get("status"))
            status_counts[status] = status_counts.get(status, 0) + 1
        return {
            "check_count": len(checks),
            "ok_count": status_counts.get("ok", 0),
            "degraded_count": status_counts.get("degraded", 0),
            "mismatch_count": status_counts.get("mismatch", 0),
            "unavailable_count": status_counts.get("unavailable", 0),
            "fail_closed_count": sum(1 for check in checks if check.get("fail_closed") is True),
            "web_smoke_compatible": web_smoke_compatible,
            "status_counts": status_counts,
        }

    @staticmethod
    def _compact_check(check: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": check.get("name"),
            "label": check.get("label"),
            "status": check.get("status"),
            "ok": check.get("ok"),
            "summary": check.get("summary"),
            "source": check.get("source"),
            "degraded_reasons": check.get("degraded_reasons") or [],
            "fail_closed": check.get("fail_closed") is True,
            "web_smoke_compatible": check.get("web_smoke_compatible") is True,
            "safety": check.get("safety") or {},
        }

    @staticmethod
    def _safety() -> dict[str, bool]:
        return {
            "read_only": True,
            "ratio_only": True,
            "current_only": True,
            "research_first": True,
            "research_first_neutral": True,
            "get_only": True,
            "openapi_get_only": True,
            "no_validation_commands": True,
            "no_file_writes": True,
            "no_sqlite_writes": True,
            "no_ingest_rebuild": True,
            "uses_latest_index_modules": True,
            "uses_latest_index_files": False,
            "generates_action_plan": False,
            "generates_target_allocation": False,
            "trading_feature": False,
            "qmt_write_feature": False,
        }

    @staticmethod
    def _checked_at() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _normalize_status(status: Any) -> str:
        value = str(status or "unavailable").strip().lower()
        return value if value in ALLOWED_READINESS_STATUSES else "unavailable"

    @staticmethod
    def _repo_path(path: Any) -> str:
        try:
            return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
        except (OSError, ValueError, AttributeError):
            return "redacted_path"

    @staticmethod
    def _safe(payload: dict[str, Any]) -> dict[str, Any]:
        sanitized = RatioOnlyService.sanitize(payload)
        RatioOnlyService.assert_safe(sanitized)
        return sanitized
