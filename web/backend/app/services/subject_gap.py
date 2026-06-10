from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..repositories.subject_gap_repo import SubjectGapRepository
from .current_state import CurrentStateService
from .market_position import MarketPositionService
from .ratio_only import RatioOnlyService


class SubjectGapService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = SubjectGapRepository(session)
        self.current = CurrentStateService(session)

    def freshness(self) -> dict[str, Any]:
        rows = [self._freshness_row(row) for row in self._source_rows()]
        payload = {
            "current_only": True,
            "reference_timestamp": self._reference_timestamp(),
            "rows": rows,
            "summary": {
                "subject_count": len(rows),
                "stale_count": sum(1 for row in rows if row.get("staleness_flag")),
            },
            "source_modules": self._source_modules(),
        }
        RatioOnlyService.assert_safe(payload)
        return payload

    def gap(self) -> dict[str, Any]:
        rows = [self._gap_row(row) for row in self._source_rows()]
        payload = {
            "current_only": True,
            "market_position": MarketPositionService(self.session).get_current_market_position(),
            "rows": rows,
            "summary": {
                "subject_count": len(rows),
                "stale_count": sum(1 for row in rows if row.get("staleness_flag")),
                "green_count": sum(1 for row in rows if row.get("gap_status") == "green"),
                "yellow_count": sum(1 for row in rows if row.get("gap_status") == "yellow"),
                "red_count": sum(1 for row in rows if row.get("gap_status") == "red"),
                "unknown_count": sum(1 for row in rows if row.get("gap_status") == "unknown"),
            },
            "source_modules": self._source_modules(),
        }
        RatioOnlyService.assert_safe(payload)
        return payload

    def _source_rows(self) -> list[dict[str, Any]]:
        return self.repo.list_subject_gap_rows()

    def _gap_row(self, row: dict[str, Any]) -> dict[str, Any]:
        freshness = self._freshness_values(row)
        payload = {
            "code": row.get("code"),
            "name": row.get("name"),
            "subject_type": row.get("subject_type"),
            "bucket": self._display_bucket(row.get("bucket")),
            "position_pct": row.get("position_pct"),
            "actual_pct": row.get("actual_pct"),
            "target_pct": row.get("target_pct"),
            "gap_pct": row.get("gap_pct"),
            "gap_status": self._gap_status(row.get("gap_pct")),
            **freshness,
            "source_paths": self._source_paths(row),
        }
        return RatioOnlyService.sanitize(payload)

    def _freshness_row(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "code": row.get("code"),
            "name": row.get("name"),
            "subject_type": row.get("subject_type"),
            "bucket": self._display_bucket(row.get("bucket")),
            **self._freshness_values(row),
            "source_paths": self._source_paths(row),
        }
        return RatioOnlyService.sanitize(payload)

    def _freshness_values(self, row: dict[str, Any]) -> dict[str, Any]:
        last_update = self._latest_text(
            row.get("portfolio_generated_at"),
            row.get("target_generated_at"),
            row.get("subject_generated_at"),
        )
        basis_date = self._latest_text(
            row.get("portfolio_basis_trade_date"),
            row.get("target_basis_trade_date"),
            row.get("subject_basis_trade_date"),
        )
        reference = self._reference_timestamp()
        stale = self._is_stale(last_update, reference)
        return {
            "last_update_timestamp": last_update,
            "basis_trade_date": basis_date,
            "staleness_flag": stale,
            "staleness_reason": "missing current update" if not last_update else ("older than current module date" if stale else "current module date"),
        }

    def _source_modules(self) -> dict[str, Any]:
        return {
            "portfolio_snapshot": self.current.source_for_module("portfolio_snapshot"),
            "target_allocation": self.current.source_for_module("target_allocation"),
            "market_score": self.current.source_for_module("market_score"),
        }

    def _reference_timestamp(self) -> str | None:
        latest = self.current.latest_index()
        return latest.get("generated_at")

    @staticmethod
    def _source_paths(row: dict[str, Any]) -> dict[str, str]:
        paths: dict[str, str] = {}
        if row.get("subject_source_path"):
            paths["subject"] = str(row["subject_source_path"]).replace(chr(92), "/")
        return paths

    @staticmethod
    def _display_bucket(value: Any) -> Any:
        return "cash_short" if value == "bond_cash" else value

    @staticmethod
    def _gap_status(value: Any) -> str:
        if value is None:
            return "unknown"
        gap = abs(float(value))
        if gap <= 1:
            return "green"
        if gap <= 5:
            return "yellow"
        return "red"

    @staticmethod
    def _latest_text(*values: Any) -> str | None:
        candidates = [str(value) for value in values if value]
        return max(candidates) if candidates else None

    @classmethod
    def _is_stale(cls, value: Any, reference: Any) -> bool:
        value_key = cls._date_key(value)
        reference_key = cls._date_key(reference)
        if not value_key:
            return True
        if not reference_key:
            return False
        return value_key < reference_key

    @staticmethod
    def _date_key(value: Any) -> str:
        if value is None:
            return ""
        digits = "".join(ch for ch in str(value) if ch.isdigit())
        return digits[:8]
