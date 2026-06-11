from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from sqlalchemy.orm import Session

from ..repositories.schema_guard_repo import SchemaGuardRepository
from .ratio_only import RatioOnlyService, RatioOnlyViolation


EXPECTED_SCHEMA_NAME = "web_sqlite_read_model"
EXPECTED_SCHEMA_VERSION = "web_read_model_v1"

REQUIRED_SCHEMA: dict[str, set[str]] = {
    "artifacts": {"id", "module", "path", "raw_json", "is_current"},
    "current_modules": {"module", "artifact_id", "updated_at"},
    "market_scores": {"id", "score", "state", "equity_min_pct", "equity_max_pct", "cash_min_pct", "cash_max_pct"},
    "market_position_mappings": {"id", "score_min", "score_max", "equity_min_pct", "cash_min_pct", "is_active"},
    "subjects": {"id", "code", "name", "subject_type", "bucket", "status"},
    "profiles": {"id", "subject_id", "status", "source_artifact_id", "raw_json"},
    "valuations": {"id", "subject_id", "valuation_status", "valuation_source_artifact_id", "raw_json"},
    "liquidity_gates": {"id", "subject_id", "liquidity_status", "valuation_status", "generated_at"},
    "portfolio_snapshots": {"id", "generated_at", "basis_trade_date", "equity_pct", "cash_short_pct", "raw_json"},
    "portfolio_positions": {"id", "snapshot_id", "subject_id", "bucket", "position_pct"},
    "target_allocations": {"id", "generated_at", "basis_trade_date", "equity_min_pct", "cash_min_pct", "raw_json"},
    "bucket_allocations": {"id", "target_allocation_id", "bucket", "actual_pct", "target_pct", "gap_pct"},
    "action_plans": {"id", "generated_at", "basis_trade_date", "status", "raw_json"},
    "action_items": {"id", "action_plan_id", "sequence", "action_type", "bucket", "current_position_pct"},
    "research_first_items": {"id", "action_plan_id", "missing_profile", "missing_valuation", "blocking_reason"},
    "intraday_rules": {"id", "generated_at", "basis_trade_date", "status", "risk_mode", "raw_json"},
    "intraday_bucket_rules": {"id", "intraday_rules_id", "bucket", "actual_pct", "target_pct", "gap_pct"},
    "decision_log_entries": {"id", "entry_time", "entry_type", "summary", "ratio_only_text"},
    "system_check_results": {"id", "check_name", "status", "message", "generated_at"},
}


class SchemaGuardRepositoryProtocol(Protocol):
    def list_tables(self) -> list[str]:
        ...

    def table_columns(self, table: str) -> list[str]:
        ...

    def schema_version_record(self) -> dict[str, Any] | None:
        ...

    def schema_metadata(self) -> dict[str, Any]:
        ...


class SchemaGuardService:
    def __init__(
        self,
        session: Session,
        repository: SchemaGuardRepositoryProtocol | None = None,
    ):
        self.repository = repository or SchemaGuardRepository(session)

    def status(self) -> dict[str, Any]:
        checked_at = self._checked_at()
        try:
            tables = set(self.repository.list_tables())
            columns_by_table = {
                table: set(self.repository.table_columns(table))
                for table in sorted(REQUIRED_SCHEMA)
                if table in tables
            }
            optional_columns = {
                table: set(self.repository.table_columns(table))
                for table in ["schema_version", "schema_metadata"]
                if table in tables
            }
        except Exception:  # noqa: BLE001
            return self._base_payload(
                checked_at=checked_at,
                status="unavailable",
                ok=False,
                diagnostics_warnings=["schema_introspection_unavailable"],
            )

        missing_tables = sorted(set(REQUIRED_SCHEMA) - tables)
        missing_columns = {
            table: sorted(required - columns_by_table.get(table, set()))
            for table, required in sorted(REQUIRED_SCHEMA.items())
            if table in tables and required - columns_by_table.get(table, set())
        }

        schema_version_table_present = "schema_version" in tables
        schema_metadata_table_present = "schema_metadata" in tables
        observed_name: str | None = None
        observed_version: str | None = None
        version_source: str | None = None
        warnings: list[str] = []

        if missing_tables:
            warnings.append("required_table_missing")
        if missing_columns:
            warnings.append("required_column_missing")

        if schema_version_table_present:
            version_record = self.repository.schema_version_record() or {}
            observed_name = self._safe_string(version_record.get("schema_name"))
            observed_version = self._safe_string(version_record.get("schema_version"))
            version_source = "schema_version"
            version_columns = optional_columns.get("schema_version", set())
            required_version_columns = {"id", "schema_name", "schema_version", "schema_fingerprint", "created_at", "source"}
            if required_version_columns - version_columns:
                missing_columns["schema_version"] = sorted(required_version_columns - version_columns)
                warnings.append("schema_version_column_missing")
        elif schema_metadata_table_present:
            metadata = self.repository.schema_metadata()
            observed_name = self._safe_string(metadata.get("schema_name"))
            observed_version = self._safe_string(metadata.get("schema_version"))
            version_source = "schema_metadata"
            metadata_columns = optional_columns.get("schema_metadata", set())
            if not {"key", "value"}.issubset(metadata_columns):
                missing_columns["schema_metadata"] = sorted({"key", "value"} - metadata_columns)
                warnings.append("schema_metadata_column_missing")
        else:
            warnings.append("missing_version_table")

        if missing_tables or missing_columns:
            status = "mismatch"
            ok = False
        elif observed_version is None:
            status = "degraded"
            ok = True
        elif observed_name != EXPECTED_SCHEMA_NAME or observed_version != EXPECTED_SCHEMA_VERSION:
            status = "mismatch"
            ok = False
            warnings.append("schema_version_mismatch")
        else:
            status = "ok"
            ok = True

        return self._base_payload(
            checked_at=checked_at,
            status=status,
            ok=ok,
            observed_schema_name=observed_name,
            observed_schema_version=observed_version,
            version_source=version_source,
            schema_version_table_present=schema_version_table_present,
            schema_metadata_table_present=schema_metadata_table_present,
            required_tables_present=not missing_tables,
            required_columns_present=not missing_columns,
            missing_required_tables=missing_tables,
            missing_required_columns=missing_columns,
            diagnostics_warnings=sorted(set(warnings)),
        )

    @staticmethod
    def _checked_at() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _safe_string(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            RatioOnlyService.assert_safe({"value": text})
        except RatioOnlyViolation:
            return None
        return text

    @staticmethod
    def _base_payload(
        *,
        checked_at: str,
        status: str,
        ok: bool,
        observed_schema_name: str | None = None,
        observed_schema_version: str | None = None,
        version_source: str | None = None,
        schema_version_table_present: bool = False,
        schema_metadata_table_present: bool = False,
        required_tables_present: bool = False,
        required_columns_present: bool = False,
        missing_required_tables: list[str] | None = None,
        missing_required_columns: dict[str, list[str]] | None = None,
        diagnostics_warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "module": "schema_guard",
            "current_only": True,
            "read_only": True,
            "ok": ok,
            "status": status,
            "expected_schema_name": EXPECTED_SCHEMA_NAME,
            "expected_schema_version": EXPECTED_SCHEMA_VERSION,
            "observed_schema_name": observed_schema_name,
            "observed_schema_version": observed_schema_version,
            "version_source": version_source,
            "schema_version_table_present": schema_version_table_present,
            "schema_metadata_table_present": schema_metadata_table_present,
            "required_tables_present": required_tables_present,
            "required_columns_present": required_columns_present,
            "missing_required_tables": missing_required_tables or [],
            "missing_required_columns": missing_required_columns or {},
            "checked_at": checked_at,
            "diagnostics_warnings": diagnostics_warnings or [],
            "safety": {
                "no_sqlite_writes": True,
                "no_migration": True,
                "get_only": True,
                "ratio_only": True,
                "current_only": True,
            },
        }
