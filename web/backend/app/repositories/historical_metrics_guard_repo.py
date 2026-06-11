from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..services.database import DatabaseService
from .history_snapshot_repo import HistorySnapshotRepository


class HistoricalMetricsGuardRepository:
    def __init__(self, session: Session):
        self.db = DatabaseService(session)

    def table_counts(self, tables: list[str]) -> dict[str, int]:
        return {table: self.db.count_table(table) for table in tables}

    def source_modules(self, modules: list[str]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for module in modules:
            source = self.db.source_for_module(module)
            if source:
                result[module] = source
        return result

    def history_snapshot_summary(self) -> dict[str, Any]:
        return HistorySnapshotRepository.runtime_summary()
