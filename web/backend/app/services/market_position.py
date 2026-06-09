from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..repositories.market_position_repo import MarketPositionRepository
from .ratio_only import RatioOnlyService


class MarketPositionService:
    source = "db.market_position_mappings"

    def __init__(self, session: Session):
        self.repo = MarketPositionRepository(session)

    def get_active_mapping(self) -> list[dict[str, Any]]:
        mappings = [self._format_mapping(row) for row in self.repo.active_mappings()]
        RatioOnlyService.assert_safe(mappings)
        return mappings

    def get_position_for_score(self, score: float | int) -> dict[str, Any]:
        value = self._score_value(score)
        for row in self.repo.active_mappings():
            low = row.get("score_min")
            high = row.get("score_max")
            if low is None or high is None:
                continue
            if float(low) <= value <= float(high):
                result = self._format_mapping(row)
                result["score"] = value
                RatioOnlyService.assert_safe(result)
                return result
        raise ValueError(f"market position mapping not found for score={value:g}")

    def get_current_market_position(self) -> dict[str, Any]:
        market = self.repo.current_market_score()
        if not market or market.get("score") is None:
            raise LookupError("current market score is missing")
        position = self.get_position_for_score(float(market["score"]))
        position["market_score_state"] = market.get("state")
        position["basis_trade_date"] = market.get("basis_trade_date")
        position["generated_at"] = market.get("generated_at")
        RatioOnlyService.assert_safe(position)
        return position

    @staticmethod
    def _score_value(score: float | int) -> float:
        try:
            value = float(score)
        except (TypeError, ValueError) as exc:
            raise ValueError("score must be numeric") from exc
        if not 0 <= value <= 100:
            raise ValueError("score must be between 0 and 100")
        return value

    @classmethod
    def _format_mapping(cls, row: dict[str, Any]) -> dict[str, Any]:
        equity_min = cls._float_or_none(row.get("equity_min_pct"))
        equity_max = cls._float_or_none(row.get("equity_max_pct"))
        cash_min = cls._float_or_none(row.get("cash_min_pct"))
        cash_max = cls._float_or_none(row.get("cash_max_pct"))
        return {
            "score_min": cls._float_or_none(row.get("score_min")),
            "score_max": cls._float_or_none(row.get("score_max")),
            "label": row.get("label"),
            "equity_min_pct": equity_min,
            "equity_max_pct": equity_max,
            "cash_min_pct": cash_min,
            "cash_max_pct": cash_max,
            "equity_range": {"min_pct": equity_min, "max_pct": equity_max},
            "cash_short_range": {"min_pct": cash_min, "max_pct": cash_max},
            "source": cls.source,
        }

    @staticmethod
    def _float_or_none(value: Any) -> float | None:
        return float(value) if value is not None else None
