from __future__ import annotations

from pathlib import Path
from typing import Any

from myinvest.db.queries.valuation_history import query_valuation_history

from ..config import HISTORY_DB_PATH


class ValuationHistoryService:
    def __init__(self, db_path: Path = HISTORY_DB_PATH) -> None:
        self.db_path = db_path

    def history(self, code: str) -> dict[str, Any]:
        if not self.db_path.exists():
            return {
                "code": code,
                "rows": [],
                "summary": {"count": 0, "db_ready": False},
                "note": "valuation zones are security-level research state, not portfolio actions",
            }
        rows = query_valuation_history(self.db_path, code)
        return {
            "code": code,
            "rows": rows,
            "summary": {
                "count": len(rows),
                "db_ready": True,
                "latest_generated_at": rows[-1]["generated_at"] if rows else None,
            },
            "note": "valuation zones are security-level research state, not portfolio actions",
        }
