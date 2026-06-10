from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from ..repositories.workbench_analytics_repo import WorkbenchAnalyticsRepository
from .ratio_only import RatioOnlyService
from .user_preferences import UserPreferencesService


class WorkbenchAnalyticsService:
    """Build ratio-only analytics for the Workbench dashboard."""

    module = "workbench_analytics_dashboard"
    supported_windows = {"current", "7d", "30d"}
    safe_user_id_re = re.compile(r"^[A-Za-z0-9_-]{1,48}$")

    def __init__(self, session: Session):
        self.repo = WorkbenchAnalyticsRepository(session)
        self.session = session

    def summary(self, time_window: str = "current") -> dict[str, Any]:
        selected_window = self._normalize_window(time_window)
        modules = self.repo.current_modules()
        counts = self.repo.table_counts()
        action = self.repo.latest_action_summary()
        bucket_gaps = self.repo.latest_bucket_gaps()
        intraday = self.repo.latest_intraday_status()
        system_rows = self.repo.system_check_rows()
        history = self.repo.history_snapshot_summary()
        payload = {
            "module": self.module,
            "current_only": True,
            "ratio_only": True,
            "read_only": True,
            "generated_at": self._latest_text(
                action.get("generated_at"),
                intraday.get("generated_at"),
                history.get("generated_at"),
                *(item.get("generated_at") for item in modules),
            ),
            "window": {
                "selected": selected_window,
                "effective": "current_only",
                "supported": sorted(self.supported_windows),
            },
            "metrics": self._metrics(counts, action, bucket_gaps, history),
            "gates": self._gates(system_rows, intraday),
            "history_snapshot": history,
            "source": {
                "provider": "WorkbenchAnalyticsRepository",
                "current_module_count": len(modules),
                "database_service": True,
                "history_snapshot_runtime": history.get("available") is True,
            },
            "safety": self._safety(),
        }
        return self._safe(payload)

    def user_metrics(self, user_id: str, time_window: str = "current") -> dict[str, Any]:
        safe_user_id = self._normalize_user_id(user_id)
        preferences = UserPreferencesService(self.session).preferences(safe_user_id)
        summary = self.summary(time_window)
        payload = {
            "module": "workbench_user_metrics",
            "user_id": preferences["user_id"],
            "current_only": True,
            "ratio_only": True,
            "read_only": True,
            "generated_at": summary.get("generated_at"),
            "window": summary["window"],
            "preferences": {
                "density": preferences["display"]["density"],
                "theme": preferences["display"]["theme"],
                "language": preferences["display"]["language"],
                "refresh_seconds": preferences["dashboard"]["refresh_seconds"],
                "table_page_size": preferences["tables"]["page_size"],
            },
            "metrics": summary["metrics"],
            "gates": summary["gates"],
            "safety": self._safety(),
        }
        return self._safe(payload)

    @staticmethod
    def _metrics(
        counts: dict[str, int],
        action: dict[str, Any],
        bucket_gaps: list[dict[str, Any]],
        history: dict[str, Any],
    ) -> dict[str, Any]:
        gap_values = [float(row.get("gap_pct") or 0) for row in bucket_gaps]
        return {
            "current_module_count": counts.get("current_modules", 0),
            "subject_count": counts.get("subjects", 0),
            "profile_count": counts.get("profiles", 0),
            "valuation_count": counts.get("valuations", 0),
            "liquidity_gate_count": counts.get("liquidity_gates", 0),
            "action_count": int(action.get("action_count") or 0),
            "manual_review_count": int(action.get("manual_review_count") or 0),
            "research_first_count": counts.get("research_first_items", 0),
            "bucket_count": len(bucket_gaps),
            "large_gap_count": sum(1 for value in gap_values if abs(value) >= 5),
            "medium_gap_count": sum(1 for value in gap_values if 2 <= abs(value) < 5),
            "decision_entry_count": counts.get("decision_log_entries", 0),
            "history_entry_count": history.get("history_entry_count", 0),
            "history_matched_count": history.get("matched_entry_count", 0),
        }

    @staticmethod
    def _gates(system_rows: list[dict[str, Any]], intraday: dict[str, Any]) -> dict[str, Any]:
        rows = {row.get("check_name"): row for row in system_rows}
        return {
            "project_check_status": (rows.get("project_check_current_only") or {}).get("status", "unknown"),
            "research_first_status": (rows.get("research_first_gate") or {}).get("status", "unknown"),
            "allocation_consistency_status": (rows.get("allocation_consistency") or {}).get("status", "unknown"),
            "sensitive_scan_status": (rows.get("sensitive_scan") or {}).get("status", "unknown"),
            "intraday_status": intraday.get("status", "unknown"),
            "intraday_stale_flag": bool(intraday.get("stale_flag")),
            "intraday_degraded_flag": bool(intraday.get("degraded_flag")),
        }

    @classmethod
    def _normalize_window(cls, time_window: str) -> str:
        value = str(time_window or "current").strip().lower()
        return value if value in cls.supported_windows else "current"

    @classmethod
    def _normalize_user_id(cls, user_id: str) -> str:
        safe_user_id = str(user_id or "default").strip()
        if not cls.safe_user_id_re.fullmatch(safe_user_id):
            raise LookupError("dashboard user metrics not found")
        if safe_user_id not in UserPreferencesService.supported_user_ids:
            raise LookupError("dashboard user metrics not found")
        return safe_user_id

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
            "generates_action_plan": False,
            "generates_target_allocation": False,
            "trading_feature": False,
            "qmt_write_feature": False,
        }

    @staticmethod
    def _latest_text(*values: Any) -> str | None:
        candidates = [str(value) for value in values if value]
        return max(candidates) if candidates else None

    @staticmethod
    def _safe(payload: dict[str, Any]) -> dict[str, Any]:
        sanitized = RatioOnlyService.sanitize(payload)
        RatioOnlyService.assert_safe(sanitized)
        return sanitized
