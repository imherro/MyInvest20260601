from __future__ import annotations

from sqlalchemy.orm import Session

from .current_state import CurrentStateService


class PortfolioService:
    def __init__(self, session: Session):
        self.current = CurrentStateService(session)

    def current_snapshot(self):
        return self.current.portfolio()
