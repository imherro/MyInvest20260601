from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class CurrentStateRepository:
    def __init__(self, session: Session):
        self.session = session

    def all(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return [dict(row) for row in self.session.execute(text(sql), params or {}).mappings().all()]

    def one(self, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        row = self.session.execute(text(sql), params or {}).mappings().first()
        return dict(row) if row else None

    def count_table(self, table: str) -> int:
        allowed = {
            "artifacts",
            "current_modules",
            "market_scores",
            "market_position_mappings",
            "subjects",
            "profiles",
            "valuations",
            "liquidity_gates",
            "portfolio_snapshots",
            "portfolio_positions",
            "target_allocations",
            "bucket_allocations",
            "action_plans",
            "action_items",
            "research_first_items",
            "intraday_rules",
            "intraday_bucket_rules",
            "decision_log_entries",
            "system_check_results",
        }
        if table not in allowed:
            raise ValueError(f"unsupported table: {table}")
        return int(self.session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one())
