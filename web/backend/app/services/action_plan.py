from __future__ import annotations

from sqlalchemy.orm import Session

from .current_state import CurrentStateService


class ActionPlanService:
    def __init__(self, session: Session):
        self.current = CurrentStateService(session)

    def current_plan(self):
        return self.current.action_plan()
