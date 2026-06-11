from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..repositories.audit_bundle_repo import AuditBundleRepository
from .historical_metrics import HistoricalMetricsService
from .ratio_only import RatioOnlyService
from .user_preferences import UserPreferencesService
from .workbench_analytics import WorkbenchAnalyticsService
from .workbench_integration_service import WorkbenchIntegrationService


class AuditBundleService:
    """Build a read-only Workbench audit bundle for preview and review."""

    module = "workbench_audit_bundle"
    supported_windows = {"current", "7d", "30d"}
    supported_filters = {"all", "dashboard", "preferences", "historical_metrics", "integration"}

    def __init__(self, session: Session):
        self.session = session
        self.repo = AuditBundleRepository(session)

    def bundle(self, time_window: str = "current", module_filter: str = "all") -> dict[str, Any]:
        selected_window = self._normalize(time_window, self.supported_windows, "current")
        selected_filter = self._normalize(module_filter, self.supported_filters, "all")
        analytics = WorkbenchAnalyticsService(self.session).summary(time_window=selected_window)
        preferences = UserPreferencesService(self.session).preferences()
        integration = WorkbenchIntegrationService(self.session).overview(time_window=selected_window)
        historical = HistoricalMetricsService(self.session).metrics()
        counts = self.repo.table_counts()
        history = self.repo.history_snapshot_summary()
        sections = self._sections(selected_filter, analytics, preferences, historical, integration, history)
        payload = {
            "module": self.module,
            "current_only": True,
            "ratio_only": True,
            "read_only": True,
            "generated_at": self._latest_text(analytics.get("generated_at"), historical.get("generated_at")),
            "window": {
                "selected": selected_window,
                "effective": "current_only",
                "supported": sorted(self.supported_windows),
            },
            "module_filter": {
                "selected": selected_filter,
                "supported": sorted(self.supported_filters),
            },
            "summary": {
                "section_count": len(sections),
                "current_module_count": counts.get("current_modules", 0),
                "subject_count": counts.get("subjects", 0),
                "action_count": counts.get("action_items", 0),
                "research_first_count": counts.get("research_first_items", 0),
                "decision_entry_count": counts.get("decision_log_entries", 0),
                "history_entry_count": history.get("history_entry_count", 0),
            },
            "sections": sections,
            "preview_chart": self._preview_chart(analytics, historical, history),
            "sources": self._sources(),
            "safety": self._safety(),
        }
        return self._safe(payload)

    def _sections(
        self,
        selected_filter: str,
        analytics: dict[str, Any],
        preferences: dict[str, Any],
        historical: dict[str, Any],
        integration: dict[str, Any],
        history: dict[str, Any],
    ) -> list[dict[str, Any]]:
        section_map = {
            "dashboard": {
                "name": "dashboard",
                "label": "Dashboard",
                "href": "/dashboard",
                "api_path": "/api/dashboard/summary",
                "status": "ready",
                "metric_count": len(analytics.get("metrics") or {}),
            },
            "preferences": {
                "name": "preferences",
                "label": "Preferences",
                "href": "/preferences",
                "api_path": "/api/user/preferences",
                "status": "ready",
                "metric_count": len(preferences.get("display") or {}) + len(preferences.get("tables") or {}),
            },
            "historical_metrics": {
                "name": "historical_metrics",
                "label": "Historical Metrics",
                "href": "/historical-metrics",
                "api_path": "/api/historical-metrics",
                "status": "ready",
                "metric_count": (historical.get("summary") or {}).get("entity_count", 0),
            },
            "integration": {
                "name": "integration",
                "label": "Workbench Integration",
                "href": "/dashboard",
                "api_path": "/api/workbench/integration",
                "status": "ready",
                "metric_count": len(integration.get("modules") or []),
            },
        }
        if history.get("available"):
            section_map["history_snapshot"] = {
                "name": "history_snapshot",
                "label": "History Snapshot",
                "href": "/api/history/export?format=json",
                "api_path": "/api/history/export?format=json",
                "status": "available",
                "metric_count": history.get("history_entry_count", 0),
            }
        sections = list(section_map.values())
        if selected_filter == "all":
            return sections
        return [section for section in sections if section["name"] == selected_filter]

    @staticmethod
    def _preview_chart(
        analytics: dict[str, Any],
        historical: dict[str, Any],
        history: dict[str, Any],
    ) -> list[dict[str, Any]]:
        metrics = analytics.get("metrics") or {}
        historical_summary = historical.get("summary") or {}
        return [
            {"label": "Modules", "value": metrics.get("current_module_count", 0), "status": "ready"},
            {"label": "Subjects", "value": metrics.get("subject_count", 0), "status": "ready"},
            {"label": "Actions", "value": metrics.get("action_count", 0), "status": "ready"},
            {"label": "History", "value": history.get("history_entry_count", 0), "status": "available" if history.get("available") else "empty"},
            {"label": "Historical", "value": historical_summary.get("entity_count", 0), "status": "ready"},
        ]

    def _sources(self) -> dict[str, Any]:
        return {
            "action_plan": self.repo.source_for_module("action_plan"),
            "target_allocation": self.repo.source_for_module("target_allocation"),
            "portfolio_snapshot": self.repo.source_for_module("portfolio_snapshot"),
            "market_score": self.repo.source_for_module("market_score"),
            "history_snapshot": {"provider": "HistorySnapshotRepository"},
        }

    @staticmethod
    def _safety() -> dict[str, bool]:
        return {
            "read_only": True,
            "ratio_only": True,
            "current_only": True,
            "uses_database_service": True,
            "uses_history_snapshot": True,
            "uses_latest_index_modules": True,
            "uses_latest_index_files": False,
            "openapi_get_only": True,
            "trading_feature": False,
            "qmt_write_feature": False,
            "generates_action_plan": False,
            "generates_target_allocation": False,
        }

    @staticmethod
    def _normalize(value: str, supported: set[str], fallback: str) -> str:
        selected = str(value or fallback).strip().lower()
        return selected if selected in supported else fallback

    @staticmethod
    def _latest_text(*values: Any) -> str | None:
        candidates = [str(value) for value in values if value]
        return max(candidates) if candidates else None

    @staticmethod
    def _safe(payload: dict[str, Any]) -> dict[str, Any]:
        sanitized = RatioOnlyService.sanitize(payload)
        RatioOnlyService.assert_safe(sanitized)
        return sanitized
