from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..services.database import DatabaseService


class MarketPositionRepository:
    def __init__(self, session: Session):
        self.db = DatabaseService(session)

    def active_mappings(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT score_min, score_max, equity_min_pct, equity_max_pct,
                   cash_min_pct, cash_max_pct, label, is_active
            FROM market_position_mappings
            WHERE is_active = 1
            ORDER BY score_min, score_max
            """
        )

    def current_market_score(self) -> dict[str, Any] | None:
        return self.db.fetch_one(
            """
            SELECT score, state, basis_trade_date, generated_at,
                   equity_min_pct, equity_max_pct, cash_min_pct, cash_max_pct
            FROM market_scores
            ORDER BY id DESC
            LIMIT 1
            """
        )
