from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..services.database import DatabaseService
from .history_snapshot_repo import HistorySnapshotRepository


class WorkbenchAnalyticsRepository:
    """Read-only analytics repository for the local workbench dashboard."""

    def __init__(self, session: Session):
        self.db = DatabaseService(session)

    def all(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self.db.fetch_all(sql, params)

    def one(self, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        return self.db.fetch_one(sql, params)

    def current_modules(self) -> list[dict[str, Any]]:
        return self.db.current_modules()

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
            "intraday_rules",
            "decision_log_entries",
            "system_check_results",
        ]
        return {table: self.db.count_table(table) for table in tables}

    def latest_action_summary(self) -> dict[str, Any]:
        return self.one(
            """
            SELECT ap.generated_at, ap.basis_trade_date, ap.status,
                   COUNT(ai.id) AS action_count,
                   SUM(CASE WHEN ai.requires_manual_confirmation THEN 1 ELSE 0 END) AS manual_review_count
            FROM action_plans ap
            LEFT JOIN action_items ai ON ai.action_plan_id = ap.id
            WHERE ap.id = (SELECT id FROM action_plans ORDER BY id DESC LIMIT 1)
            GROUP BY ap.id
            """
        ) or {}

    def latest_bucket_gaps(self) -> list[dict[str, Any]]:
        return self.all(
            """
            SELECT bucket, actual_pct, target_pct, gap_pct
            FROM bucket_allocations
            WHERE target_allocation_id = (SELECT id FROM target_allocations ORDER BY id DESC LIMIT 1)
            ORDER BY id
            """
        )

    def latest_intraday_status(self) -> dict[str, Any]:
        return self.one(
            """
            SELECT status, stale_flag, degraded_flag, generated_at, basis_trade_date
            FROM intraday_rules
            ORDER BY id DESC
            LIMIT 1
            """
        ) or {}

    def system_check_rows(self) -> list[dict[str, Any]]:
        return self.all(
            """
            SELECT check_name, status, generated_at
            FROM system_check_results
            ORDER BY id
            """
        )

    def history_snapshot_summary(self) -> dict[str, Any]:
        return HistorySnapshotRepository.runtime_summary()
