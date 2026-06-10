from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..repositories.decision_timeline_repo import DecisionTimelineRepository
from .current_state import CurrentStateService
from .history_snapshot import HistorySnapshotService
from .ratio_only import RatioOnlyService


class DecisionTimelineService:
    """Read-only review timeline assembled from current Web state."""

    def __init__(self, session: Session):
        self.session = session
        self.current = CurrentStateService(session)
        self.repo = DecisionTimelineRepository(session)

    def timeline(self) -> dict[str, Any]:
        action_plan = self.current.action_plan() or {}
        target_allocation = self.current.target_allocation() or {}
        history_snapshot = self._history_snapshot()
        events: list[dict[str, Any]] = []

        if action_plan:
            events.append(self._action_plan_event(action_plan))
        if target_allocation:
            events.append(self._target_allocation_event(target_allocation))
        events.extend(self._decision_log_events())
        events.extend(self._history_events(history_snapshot))
        events = self._sort_events(events)

        payload = {
            "module": "decision_timeline",
            "current_only": True,
            "generated_at": self._latest_text(*(event.get("timestamp") for event in events)),
            "summary": self._summary(events),
            "events": events,
            "source_modules": {
                "action_plan": self.current.source_for_module("action_plan"),
                "target_allocation": self.current.source_for_module("target_allocation"),
                "decision_log": {"path": "research/logs/decision_log.md"},
                "history_snapshot": {"path": "db.HistorySnapshotService"},
            },
            "safety": self._safety(),
        }
        return self._safe(payload)

    def get_event(self, event_id: str) -> dict[str, Any]:
        for event in self.timeline()["events"]:
            if event.get("event_id") == event_id:
                return self._safe({"event": event})
        raise LookupError(event_id)

    def _decision_log_events(self) -> list[dict[str, Any]]:
        rows = self.repo.recent_decision_log_entries(limit=40)
        events = []
        for row in rows:
            entry_id = row.get("id")
            events.append(
                {
                    "event_id": f"decision-log-{entry_id}",
                    "event_type": "decision_log",
                    "timestamp": row.get("entry_time"),
                    "title": row.get("summary") or row.get("entry_type") or "decision log",
                    "summary": row.get("ratio_only_text") or row.get("summary") or "",
                    "status": row.get("entry_type") or "logged",
                    "basis_trade_date": None,
                    "details": {
                        "entry_type": row.get("entry_type"),
                        "reason": row.get("reason"),
                        "ratio_only_text": row.get("ratio_only_text"),
                    },
                    "review_links": {"decision_log": "/decision-log"},
                }
            )
        return events

    @staticmethod
    def _action_plan_event(action_plan: dict[str, Any]) -> dict[str, Any]:
        actions = action_plan.get("actions") or []
        research_first = action_plan.get("research_first") or []
        action_types = sorted({str(item.get("action_type") or "unknown") for item in actions})
        buckets = sorted({str(item.get("bucket") or "unknown") for item in actions})
        return {
            "event_id": "current-action-plan",
            "event_type": "action_plan",
            "timestamp": action_plan.get("generated_at"),
            "title": "Current action plan",
            "summary": f"{len(actions)} action rows; status {action_plan.get('status') or 'unknown'}",
            "status": action_plan.get("status") or "unknown",
            "basis_trade_date": action_plan.get("basis_trade_date"),
            "details": {
                "market_state": action_plan.get("market_state"),
                "action_count": len(actions),
                "research_first_count": len(research_first),
                "action_types": action_types,
                "buckets": buckets,
                "requires_manual_confirmation_count": sum(1 for item in actions if item.get("requires_manual_confirmation")),
            },
            "review_links": {"action_plan": "/action-plan", "research_first": "/research-first"},
        }

    @staticmethod
    def _target_allocation_event(target_allocation: dict[str, Any]) -> dict[str, Any]:
        buckets = target_allocation.get("buckets") or []
        max_gap = max([abs(float(row.get("gap_pct") or 0)) for row in buckets] or [0.0])
        return {
            "event_id": "current-target-allocation",
            "event_type": "target_allocation",
            "timestamp": target_allocation.get("generated_at"),
            "title": "Current target allocation",
            "summary": f"{len(buckets)} bucket rows; max gap {max_gap:.2f}pp",
            "status": "current",
            "basis_trade_date": target_allocation.get("basis_trade_date"),
            "details": {
                "bucket_count": len(buckets),
                "equity_min_pct": target_allocation.get("equity_min_pct"),
                "equity_max_pct": target_allocation.get("equity_max_pct"),
                "cash_min_pct": target_allocation.get("cash_min_pct"),
                "cash_max_pct": target_allocation.get("cash_max_pct"),
                "max_gap_pct": round(max_gap, 4),
                "buckets": buckets,
            },
            "review_links": {"target_allocation": "/target-allocation", "bucket_drilldown": "/buckets/drilldown"},
        }

    def _history_events(self, history_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        events = []
        for index, row in enumerate(history_snapshot.get("history_entries") or []):
            events.append(
                {
                    "event_id": f"history-{index}",
                    "event_type": "history_snapshot",
                    "timestamp": row.get("generated_at"),
                    "title": row.get("export_kind") or "history snapshot",
                    "summary": f"{row.get('status') or 'unknown'}; diffs {row.get('diff_count') or 0}",
                    "status": row.get("status") or "unknown",
                    "basis_trade_date": None,
                    "details": {
                        "source_id": row.get("source_id"),
                        "source_format": row.get("source_format"),
                        "export_kind": row.get("export_kind"),
                        "module": row.get("module"),
                        "matched": row.get("matched"),
                        "diff_count": row.get("diff_count"),
                        "unsupported_field_count": row.get("unsupported_field_count"),
                        "replay_failed": row.get("replay_failed"),
                        "official_allowed": row.get("official_allowed"),
                        "system_checks": row.get("system_checks") or {},
                    },
                    "review_links": {"history_gap": "/history/gap-dashboard", "history_export": "/api/history/export?format=json"},
                }
            )
        return events

    @staticmethod
    def _summary(events: list[dict[str, Any]]) -> dict[str, Any]:
        type_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for event in events:
            event_type = str(event.get("event_type") or "unknown")
            status = str(event.get("status") or "unknown")
            type_counts[event_type] = type_counts.get(event_type, 0) + 1
            status_counts[status] = status_counts.get(status, 0) + 1
        return {
            "event_count": len(events),
            "decision_log_count": type_counts.get("decision_log", 0),
            "history_snapshot_count": type_counts.get("history_snapshot", 0),
            "action_plan_count": type_counts.get("action_plan", 0),
            "target_allocation_count": type_counts.get("target_allocation", 0),
            "type_counts": type_counts,
            "status_counts": status_counts,
        }

    @staticmethod
    def _safety() -> dict[str, bool]:
        return {
            "ratio_only": True,
            "current_only": True,
            "read_only": True,
            "uses_latest_index_modules": True,
            "uses_latest_index_files": False,
            "generates_action_plan": False,
            "generates_target_allocation": False,
            "trading_feature": False,
            "qmt_write_feature": False,
        }

    @staticmethod
    def _sort_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            events,
            key=lambda event: str(event.get("timestamp") or ""),
            reverse=True,
        )

    @staticmethod
    def _latest_text(*values: Any) -> str | None:
        candidates = [str(value) for value in values if value]
        return max(candidates) if candidates else None

    def _history_snapshot(self) -> dict[str, Any]:
        try:
            return HistorySnapshotService(self.session).build_history_snapshot()
        except Exception:  # noqa: BLE001
            return {"history_entries": []}

    @staticmethod
    def _safe(payload: dict[str, Any]) -> dict[str, Any]:
        sanitized = RatioOnlyService.sanitize(payload)
        RatioOnlyService.assert_safe(sanitized)
        return sanitized
