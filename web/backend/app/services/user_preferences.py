from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from ..repositories.user_preferences_repo import UserPreferencesRepository


class UserPreferencesService:
    """Build display-only workbench preferences from the current read model."""

    module = "user_preferences"
    supported_user_ids = {"default", "local", "phase10"}
    safe_user_id_re = re.compile(r"^[A-Za-z0-9_-]{1,48}$")

    def __init__(self, session: Session):
        self.repo = UserPreferencesRepository(session)

    def preferences(self, user_id: str = "default") -> dict[str, Any]:
        safe_user_id = self._normalize_user_id(user_id)
        modules = self.repo.current_modules()
        action_source = self.repo.source_for_module("action_plan") or {}
        system_check = self.repo.latest_system_check() or {}
        generated_at = self._generated_at(modules, action_source, system_check)
        return {
            "module": self.module,
            "user_id": safe_user_id,
            "scope": "local_workbench",
            "generated_at": generated_at,
            "profile": {
                "label": "Default Workbench",
                "role": "research_review",
                "editable": False,
            },
            "display": {
                "language": "zh-CN",
                "theme": "system",
                "density": "compact",
                "number_format": "ratio_pp",
                "show_basis_date": True,
                "show_generated_at": True,
                "show_relative_source": True,
            },
            "dashboard": {
                "landing_page": "/dashboard",
                "refresh_seconds": 60,
                "show_research_first": True,
                "show_allocation_gap": True,
                "show_history_gap": True,
                "show_system_checks": True,
            },
            "tables": {
                "page_size": 12,
                "search_enabled": True,
                "sort_enabled": True,
                "filter_enabled": True,
                "expanded_rows_enabled": True,
            },
            "safety": {
                "read_only": True,
                "ratio_only": True,
                "current_only": True,
                "uses_latest_index_modules": True,
                "uses_database_service": True,
                "trading_disabled": True,
                "qmt_write_disabled": True,
                "research_write_disabled": True,
                "database_write_disabled": True,
            },
            "sources": {
                "provider": "UserPreferencesRepository",
                "action_plan_path": action_source.get("path"),
                "current_module_count": len(modules),
                "system_check_status": system_check.get("status", "unknown"),
            },
        }

    @classmethod
    def _normalize_user_id(cls, user_id: str) -> str:
        safe_user_id = str(user_id or "default").strip()
        if not cls.safe_user_id_re.fullmatch(safe_user_id):
            raise LookupError("user preferences not found")
        if safe_user_id not in cls.supported_user_ids:
            raise LookupError("user preferences not found")
        return "default" if safe_user_id in {"local", "phase10"} else safe_user_id

    @staticmethod
    def _generated_at(
        modules: list[dict[str, Any]],
        action_source: dict[str, Any],
        system_check: dict[str, Any],
    ) -> Any:
        candidates = [
            action_source.get("generated_at"),
            system_check.get("generated_at"),
            *(item.get("generated_at") for item in modules),
        ]
        values = [value for value in candidates if value]
        return max(values) if values else None
