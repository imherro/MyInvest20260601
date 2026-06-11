from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from sqlalchemy.orm import Session

from ..repositories.historical_metrics_guard_repo import HistoricalMetricsGuardRepository
from .ratio_only import RatioOnlyService


REQUIRED_TABLES = [
    "artifacts",
    "current_modules",
    "subjects",
    "market_scores",
    "target_allocations",
    "bucket_allocations",
    "portfolio_snapshots",
    "portfolio_positions",
    "action_plans",
    "decision_log_entries",
]

REQUIRED_MODULES = [
    "target_allocation",
    "portfolio_snapshot",
    "market_score",
    "theme_registry",
]


class HistoricalMetricsGuardRepositoryProtocol(Protocol):
    def table_counts(self, tables: list[str]) -> dict[str, int]:
        ...

    def source_modules(self, modules: list[str]) -> dict[str, dict[str, Any]]:
        ...

    def history_snapshot_summary(self) -> dict[str, Any]:
        ...


class HistoricalMetricsGuardService:
    def __init__(
        self,
        session: Session,
        repository: HistoricalMetricsGuardRepositoryProtocol | None = None,
    ):
        self.repository = repository or HistoricalMetricsGuardRepository(session)

    def status(self) -> dict[str, Any]:
        checked_at = self._checked_at()
        try:
            table_counts = self.repository.table_counts(REQUIRED_TABLES)
            source_modules = self.repository.source_modules(REQUIRED_MODULES)
            history_snapshot = self.repository.history_snapshot_summary()
        except Exception:  # noqa: BLE001
            return self._safe(
                self._base_payload(
                    checked_at=checked_at,
                    status="unavailable",
                    ok=False,
                    diagnostics_warnings=["historical_metrics_guard_unavailable"],
                )
            )

        missing_inputs = self._missing_inputs(table_counts, source_modules)
        history_snapshot_available = bool(history_snapshot.get("available"))
        diagnostics_warnings: list[str] = []
        if missing_inputs:
            diagnostics_warnings.append("required_input_missing")
            status = "mismatch"
            ok = False
        elif not history_snapshot_available:
            diagnostics_warnings.append("history_snapshot_unavailable")
            status = "degraded"
            ok = True
        else:
            status = "ok"
            ok = True

        return self._safe(
            self._base_payload(
                checked_at=checked_at,
                status=status,
                ok=ok,
                table_counts=table_counts,
                source_modules=source_modules,
                history_snapshot_available=history_snapshot_available,
                history_snapshot_summary={
                    "available": history_snapshot_available,
                    "history_entry_count": int(history_snapshot.get("history_entry_count") or 0),
                    "matched_entry_count": int(history_snapshot.get("matched_entry_count") or 0),
                    "generated_at": history_snapshot.get("generated_at"),
                },
                required_inputs_present=not missing_inputs,
                missing_inputs=missing_inputs,
                diagnostics_warnings=diagnostics_warnings,
            )
        )

    @staticmethod
    def _missing_inputs(table_counts: dict[str, int], source_modules: dict[str, dict[str, Any]]) -> list[str]:
        missing = []
        for table in REQUIRED_TABLES:
            if int(table_counts.get(table) or 0) <= 0:
                missing.append(f"table:{table}")
        for module in REQUIRED_MODULES:
            if module not in source_modules:
                missing.append(f"module:{module}")
        return sorted(missing)

    @staticmethod
    def _checked_at() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _base_payload(
        *,
        checked_at: str,
        status: str,
        ok: bool,
        table_counts: dict[str, int] | None = None,
        source_modules: dict[str, dict[str, Any]] | None = None,
        history_snapshot_available: bool = False,
        history_snapshot_summary: dict[str, Any] | None = None,
        required_inputs_present: bool = False,
        missing_inputs: list[str] | None = None,
        diagnostics_warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        fail_closed = status in {"mismatch", "unavailable"}
        return {
            "module": "historical_metrics_guard",
            "current_only": True,
            "read_only": True,
            "ratio_only": True,
            "ok": ok,
            "status": status,
            "required_tables": REQUIRED_TABLES,
            "required_modules": REQUIRED_MODULES,
            "required_inputs_present": required_inputs_present,
            "missing_inputs": missing_inputs or [],
            "table_counts": table_counts or {},
            "source_modules": source_modules or {},
            "history_snapshot_available": history_snapshot_available,
            "history_snapshot_summary": history_snapshot_summary
            or {"available": False, "history_entry_count": 0, "matched_entry_count": 0, "generated_at": None},
            "checked_at": checked_at,
            "diagnostics_warnings": diagnostics_warnings or [],
            "enforcement": {
                "mode": "read_only_historical_metrics_guard",
                "status": status,
                "fail_closed": fail_closed,
                "web_smoke_compatible": status in {"ok", "degraded"},
                "audit_ready": status == "ok",
            },
            "safety": {
                "read_only": True,
                "ratio_only": True,
                "current_only": True,
                "research_first_neutral": True,
                "openapi_get_only": True,
                "uses_latest_index_modules": True,
                "uses_latest_index_files": False,
                "generates_action_plan": False,
                "generates_target_allocation": False,
                "trading_feature": False,
                "qmt_write_feature": False,
            },
        }

    @staticmethod
    def _safe(payload: dict[str, Any]) -> dict[str, Any]:
        sanitized = RatioOnlyService.sanitize(payload)
        RatioOnlyService.assert_safe(sanitized)
        return sanitized
