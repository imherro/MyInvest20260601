from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..services.database import DatabaseService


class UserPreferencesRepository:
    """Read-only repository for workbench preference display metadata."""

    def __init__(self, session: Session):
        self.db = DatabaseService(session)

    def all(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self.db.fetch_all(sql, params)

    def one(self, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        return self.db.fetch_one(sql, params)

    def current_modules(self) -> list[dict[str, Any]]:
        return self.db.current_modules()

    def source_for_module(self, module: str) -> dict[str, Any] | None:
        return self.db.source_for_module(module)

    def latest_system_check(self) -> dict[str, Any] | None:
        return self.one(
            """
            SELECT status, generated_at
            FROM system_check_results
            ORDER BY id DESC
            LIMIT 1
            """
        )
