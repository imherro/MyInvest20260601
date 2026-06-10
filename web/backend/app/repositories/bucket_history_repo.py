from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..services.database import DatabaseService


class BucketHistoryRepository:
    def __init__(self, session: Session):
        self.db = DatabaseService(session)

    def current_target_allocation(self) -> dict[str, Any] | None:
        target = self.db.fetch_one(
            """
            SELECT id, generated_at, basis_trade_date, equity_min_pct, equity_max_pct,
                   cash_min_pct, cash_max_pct
            FROM target_allocations
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if not target:
            return None
        target["buckets"] = self.db.fetch_all(
            """
            SELECT bucket, actual_pct, target_pct, gap_pct
            FROM bucket_allocations
            WHERE target_allocation_id = :id
            ORDER BY id
            """,
            {"id": target["id"]},
        )
        return target

    def source_modules(self, modules: list[str]) -> dict[str, dict[str, Any] | None]:
        return {module: self.db.source_for_module(module) for module in modules}
