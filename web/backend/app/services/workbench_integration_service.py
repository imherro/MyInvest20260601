from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .environment_status import EnvironmentStatusService
from .ratio_only import RatioOnlyService
from .user_preferences import UserPreferencesService
from .workbench_analytics import WorkbenchAnalyticsService


class WorkbenchIntegrationService:
    """Read-only integration summary for Workbench modules."""

    module = "workbench_integration"

    def __init__(self, session: Session):
        self.session = session

    def overview(self, time_window: str = "current") -> dict[str, Any]:
        analytics = WorkbenchAnalyticsService(self.session).summary(time_window=time_window)
        preferences = UserPreferencesService(self.session).preferences()
        environment = EnvironmentStatusService().status()
        payload = {
            "module": self.module,
            "current_only": True,
            "ratio_only": True,
            "read_only": True,
            "generated_at": analytics.get("generated_at"),
            "window": analytics["window"],
            "modules": self._modules(environment, preferences, analytics),
            "metrics": {
                "current_module_count": analytics["metrics"]["current_module_count"],
                "subject_count": analytics["metrics"]["subject_count"],
                "action_count": analytics["metrics"]["action_count"],
                "research_first_count": analytics["metrics"]["research_first_count"],
                "large_gap_count": analytics["metrics"]["large_gap_count"],
                "history_entry_count": analytics["metrics"]["history_entry_count"],
            },
            "gates": analytics["gates"],
            "display": {
                "density": preferences["display"]["density"],
                "theme": preferences["display"]["theme"],
                "language": preferences["display"]["language"],
                "refresh_seconds": preferences["dashboard"]["refresh_seconds"],
                "table_page_size": preferences["tables"]["page_size"],
            },
            "safety": {
                "read_only": True,
                "ratio_only": True,
                "current_only": True,
                "uses_database_service": True,
                "uses_history_snapshot": True,
                "openapi_get_only": True,
                "trading_disabled": True,
                "qmt_write_disabled": True,
                "research_write_disabled": True,
            },
        }
        return self._safe(payload)

    @staticmethod
    def _modules(
        environment: dict[str, Any],
        preferences: dict[str, Any],
        analytics: dict[str, Any],
    ) -> list[dict[str, Any]]:
        env_status = "ready" if environment.get("read_only") and environment.get("current_only") else "check"
        pref_status = "ready" if preferences.get("safety", {}).get("read_only") else "check"
        analytics_status = "ready" if analytics.get("read_only") and analytics.get("current_only") else "check"
        gates = analytics.get("gates") or {}
        research_status = gates.get("research_first_status") or "unknown"
        return [
            {
                "name": "settings",
                "label": "Settings",
                "href": "/settings",
                "api_path": "/api/environment/status",
                "status": env_status,
            },
            {
                "name": "preferences",
                "label": "Preferences",
                "href": "/preferences",
                "api_path": "/api/user/preferences",
                "status": pref_status,
            },
            {
                "name": "dashboard",
                "label": "Dashboard",
                "href": "/dashboard",
                "api_path": "/api/dashboard/summary",
                "status": analytics_status,
            },
            {
                "name": "research_centers",
                "label": "Research Centers",
                "href": "/subjects",
                "api_path": "/api/subjects/status",
                "status": research_status,
            },
        ]

    @staticmethod
    def _safe(payload: dict[str, Any]) -> dict[str, Any]:
        sanitized = RatioOnlyService.sanitize(payload)
        RatioOnlyService.assert_safe(sanitized)
        return sanitized
