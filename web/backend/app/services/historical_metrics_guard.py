from __future__ import annotations

import hashlib
import json
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

REQUIRED_INTEGRATION_PAYLOADS = [
    "historical_metrics",
    "dashboard_summary",
    "audit_bundle",
]

CONTRACT_NAME = "historical_metrics_guard_contract"
CONTRACT_VERSION = "historical_metrics_guard_v1"


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
        expected_contract = self._expected_contract()
        expected_fingerprint = self._fingerprint(expected_contract)
        try:
            table_counts = self.repository.table_counts(REQUIRED_TABLES)
            source_modules = self.repository.source_modules(REQUIRED_MODULES)
            history_snapshot = self.repository.history_snapshot_summary()
        except Exception:  # noqa: BLE001
            contract_report = self._contract_report(
                expected_fingerprint=expected_fingerprint,
                table_counts={},
                source_modules={},
                integration_payloads={},
            )
            return self._safe(
                self._base_payload(
                    checked_at=checked_at,
                    status="unavailable",
                    ok=False,
                    contract=contract_report,
                    diagnostics_warnings=["historical_metrics_guard_unavailable"],
                )
            )

        integration_payloads = self._integration_payloads(table_counts, source_modules)
        contract_report = self._contract_report(
            expected_fingerprint=expected_fingerprint,
            table_counts=table_counts,
            source_modules=source_modules,
            integration_payloads=integration_payloads,
        )
        missing_inputs = self._missing_inputs(contract_report)
        history_snapshot_available = bool(history_snapshot.get("available"))
        diagnostics_warnings: list[str] = []
        if missing_inputs:
            diagnostics_warnings.append("required_input_missing")
            status = "mismatch"
            ok = False
        elif not contract_report["fingerprint_match"]:
            diagnostics_warnings.append("historical_metrics_contract_mismatch")
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
                contract=contract_report,
                table_counts=table_counts,
                source_modules=source_modules,
                integration_payloads=integration_payloads,
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
    def _expected_contract() -> dict[str, Any]:
        return {
            "contract_name": CONTRACT_NAME,
            "contract_version": CONTRACT_VERSION,
            "required_inputs": HistoricalMetricsGuardService._required_inputs(),
            "required_source_modules": sorted(REQUIRED_MODULES),
            "required_integration_payloads": sorted(REQUIRED_INTEGRATION_PAYLOADS),
            "safety": {
                "read_only": True,
                "ratio_only": True,
                "current_only": True,
                "research_first_neutral": True,
                "openapi_get_only": True,
            },
        }

    @staticmethod
    def _required_inputs() -> list[str]:
        inputs = [f"table:{table}" for table in REQUIRED_TABLES]
        inputs.extend(f"integration:{payload}" for payload in REQUIRED_INTEGRATION_PAYLOADS)
        return sorted(inputs)

    @staticmethod
    def _observed_table_inputs(table_counts: dict[str, int]) -> list[str]:
        return sorted(f"table:{table}" for table in REQUIRED_TABLES if int(table_counts.get(table) or 0) > 0)

    @staticmethod
    def _integration_payloads(
        table_counts: dict[str, int],
        source_modules: dict[str, dict[str, Any]],
    ) -> dict[str, bool]:
        tables_present = {table for table in REQUIRED_TABLES if int(table_counts.get(table) or 0) > 0}
        modules_present = set(source_modules)
        return {
            "historical_metrics": all(table in tables_present for table in REQUIRED_TABLES)
            and all(module in modules_present for module in REQUIRED_MODULES),
            "dashboard_summary": all(
                table in tables_present
                for table in [
                    "current_modules",
                    "subjects",
                    "target_allocations",
                    "bucket_allocations",
                    "action_plans",
                    "decision_log_entries",
                ]
            ),
            "audit_bundle": all(table in tables_present for table in REQUIRED_TABLES)
            and all(module in modules_present for module in REQUIRED_MODULES),
        }

    @staticmethod
    def _contract_report(
        *,
        expected_fingerprint: str,
        table_counts: dict[str, int],
        source_modules: dict[str, dict[str, Any]],
        integration_payloads: dict[str, bool],
    ) -> dict[str, Any]:
        required_inputs = HistoricalMetricsGuardService._required_inputs()
        observed_inputs = HistoricalMetricsGuardService._observed_table_inputs(table_counts)
        observed_inputs.extend(
            f"integration:{payload}"
            for payload in REQUIRED_INTEGRATION_PAYLOADS
            if integration_payloads.get(payload) is True
        )
        observed_inputs = sorted(set(observed_inputs))
        observed_source_modules = sorted(module for module in REQUIRED_MODULES if module in source_modules)
        observed_integration_payloads = sorted(
            payload for payload in REQUIRED_INTEGRATION_PAYLOADS if integration_payloads.get(payload) is True
        )
        missing_inputs = sorted(set(required_inputs) - set(observed_inputs))
        missing_source_modules = sorted(set(REQUIRED_MODULES) - set(observed_source_modules))
        missing_integration_payloads = sorted(set(REQUIRED_INTEGRATION_PAYLOADS) - set(observed_integration_payloads))
        observed_contract = {
            "contract_name": CONTRACT_NAME,
            "contract_version": CONTRACT_VERSION,
            "required_inputs": observed_inputs,
            "required_source_modules": observed_source_modules,
            "required_integration_payloads": observed_integration_payloads,
            "safety": {
                "read_only": True,
                "ratio_only": True,
                "current_only": True,
                "research_first_neutral": True,
                "openapi_get_only": True,
            },
        }
        observed_fingerprint = HistoricalMetricsGuardService._fingerprint(observed_contract)
        return {
            "contract_name": CONTRACT_NAME,
            "contract_version": CONTRACT_VERSION,
            "required_inputs": required_inputs,
            "observed_inputs": observed_inputs,
            "missing_inputs": missing_inputs,
            "required_source_modules": sorted(REQUIRED_MODULES),
            "observed_source_modules": observed_source_modules,
            "missing_source_modules": missing_source_modules,
            "required_integration_payloads": sorted(REQUIRED_INTEGRATION_PAYLOADS),
            "observed_integration_payloads": observed_integration_payloads,
            "missing_integration_payloads": missing_integration_payloads,
            "expected_fingerprint": expected_fingerprint,
            "observed_fingerprint": observed_fingerprint,
            "fingerprint_match": observed_fingerprint == expected_fingerprint,
        }

    @staticmethod
    def _fingerprint(contract: dict[str, Any]) -> str:
        encoded = json.dumps(contract, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _missing_inputs(contract: dict[str, Any]) -> list[str]:
        missing = list(contract.get("missing_inputs") or [])
        missing.extend(f"module:{module}" for module in contract.get("missing_source_modules") or [])
        missing.extend(f"integration:{name}" for name in contract.get("missing_integration_payloads") or [])
        return sorted(set(missing))

    @staticmethod
    def _checked_at() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _base_payload(
        *,
        checked_at: str,
        status: str,
        ok: bool,
        contract: dict[str, Any],
        table_counts: dict[str, int] | None = None,
        source_modules: dict[str, dict[str, Any]] | None = None,
        integration_payloads: dict[str, bool] | None = None,
        history_snapshot_available: bool = False,
        history_snapshot_summary: dict[str, Any] | None = None,
        required_inputs_present: bool = False,
        missing_inputs: list[str] | None = None,
        diagnostics_warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        fail_closed = status in {"mismatch", "unavailable"} or contract.get("fingerprint_match") is False
        read_model_usable = status in {"ok", "degraded"} and not fail_closed
        web_smoke_compatible = read_model_usable
        audit_bundle_compatible = read_model_usable and not contract.get("missing_integration_payloads")
        return {
            "module": "historical_metrics_guard",
            "current_only": True,
            "read_only": True,
            "ratio_only": True,
            "ok": ok,
            "status": status,
            "required_tables": REQUIRED_TABLES,
            "required_modules": REQUIRED_MODULES,
            "required_integration_payloads": REQUIRED_INTEGRATION_PAYLOADS,
            "required_inputs_present": required_inputs_present,
            "missing_inputs": missing_inputs or [],
            "contract": contract,
            "table_counts": table_counts or {},
            "source_modules": source_modules or {},
            "integration_payloads": integration_payloads or {},
            "history_snapshot_available": history_snapshot_available,
            "history_snapshot_summary": history_snapshot_summary
            or {"available": False, "history_entry_count": 0, "matched_entry_count": 0, "generated_at": None},
            "checked_at": checked_at,
            "diagnostics_warnings": diagnostics_warnings or [],
            "enforcement": {
                "mode": "full_read_only_historical_metrics_guard",
                "status": status,
                "fail_closed": fail_closed,
                "read_model_usable": read_model_usable,
                "web_smoke_compatible": web_smoke_compatible,
                "audit_bundle_compatible": audit_bundle_compatible,
                "audit_ready": status == "ok",
                "contract_match": contract.get("fingerprint_match") is True,
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
