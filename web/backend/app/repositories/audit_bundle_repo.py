from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..services.database import DatabaseService
from .history_snapshot_repo import HistorySnapshotRepository


class AuditBundleRepository:
    """Read-only repository for Workbench audit bundle metadata."""

    def __init__(self, session: Session):
        self.db = DatabaseService(session)

    def all(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self.db.fetch_all(sql, params)

    def one(self, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        return self.db.fetch_one(sql, params)

    def current_modules(self) -> list[dict[str, Any]]:
        return self.db.current_modules()

    def source_for_module(self, module: str) -> dict[str, Any] | None:
        return self.db.source_for_module(module)

    def table_counts(self) -> dict[str, int]:
        tables = [
            "current_modules",
            "subjects",
            "profiles",
            "valuations",
            "liquidity_gates",
            "portfolio_snapshots",
            "target_allocations",
            "bucket_allocations",
            "action_plans",
            "action_items",
            "research_first_items",
            "decision_log_entries",
            "system_check_results",
        ]
        return {table: self.db.count_table(table) for table in tables}

    def history_snapshot_summary(self) -> dict[str, Any]:
        return HistorySnapshotRepository.runtime_summary()
