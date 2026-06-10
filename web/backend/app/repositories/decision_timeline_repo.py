from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..services.database import DatabaseService


class DecisionTimelineRepository:
    def __init__(self, session: Session):
        self.db = DatabaseService(session)

    def recent_decision_log_entries(self, limit: int = 40) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT id, entry_time, entry_type, summary, reason, ratio_only_text
            FROM decision_log_entries
            ORDER BY id DESC
            LIMIT :limit
            """,
            {"limit": limit},
        )
