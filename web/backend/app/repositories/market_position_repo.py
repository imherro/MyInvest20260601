from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class MarketPositionRepository:
    def __init__(self, session: Session):
        self.session = session

    def active_mappings(self) -> list[dict[str, Any]]:
        rows = self.session.execute(
            text(
                """
                SELECT score_min, score_max, equity_min_pct, equity_max_pct,
                       cash_min_pct, cash_max_pct, label, is_active
                FROM market_position_mappings
                WHERE is_active = 1
                ORDER BY score_min, score_max
                """
            )
        ).mappings()
        return [dict(row) for row in rows]

    def current_market_score(self) -> dict[str, Any] | None:
        row = self.session.execute(
            text(
                """
                SELECT score, state, basis_trade_date, generated_at,
                       equity_min_pct, equity_max_pct, cash_min_pct, cash_max_pct
                FROM market_scores
                ORDER BY id DESC
                LIMIT 1
                """
            )
        ).mappings().first()
        return dict(row) if row else None
