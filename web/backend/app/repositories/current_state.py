from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..services.database import DatabaseService


class CurrentStateRepository:
    def __init__(self, session: Session):
        self.db = DatabaseService(session)

    def all(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self.db.fetch_all(sql, params)

    def one(self, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        return self.db.fetch_one(sql, params)

    def count_table(self, table: str) -> int:
        return self.db.count_table(table)
