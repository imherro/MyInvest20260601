from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..services.database import DatabaseService


class AllocationRepository:
    def __init__(self, session: Session):
        self.db = DatabaseService(session)

    def target_allocation(self) -> dict[str, Any] | None:
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

    def portfolio_snapshot(self) -> dict[str, Any] | None:
        snapshot = self.db.fetch_one(
            """
            SELECT id, generated_at, basis_trade_date, equity_pct, cash_short_pct
            FROM portfolio_snapshots
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if not snapshot:
            return None
        snapshot["positions"] = self.db.fetch_all(
            """
            SELECT s.code, s.name, pp.bucket, pp.position_pct, pp.reference_only_flag
            FROM portfolio_positions pp
            LEFT JOIN subjects s ON s.id = pp.subject_id
            WHERE pp.snapshot_id = :id
            ORDER BY pp.position_pct DESC
            """,
            {"id": snapshot["id"]},
        )
        return snapshot

    def source_modules(self, modules: list[str]) -> dict[str, dict[str, Any] | None]:
        return {module: self.db.source_for_module(module) for module in modules}
