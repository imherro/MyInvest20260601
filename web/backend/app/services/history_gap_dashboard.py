from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from .current_state import CurrentStateService
from .history_snapshot import HistorySnapshotService
from .ratio_only import RatioOnlyService
from .target_allocation_candidate_audit import TargetAllocationCandidateAuditService
from .target_allocation_export import TargetAllocationControlledExportService


class HistoryGapDashboardService:
    """Read-only history gap dashboard assembled from current and audit snapshots."""

    def __init__(self, session: Session):
        self.session = session
        self.current = CurrentStateService(session)

    def summary(self) -> dict[str, Any]:
        history = HistorySnapshotService(self.session).build_history_snapshot()
        controlled = TargetAllocationControlledExportService(self.session).build_export_payload()
        candidate = TargetAllocationCandidateAuditService(self.session).build_audit_payload()
        target = self.current.target_allocation() or {}
        snapshots = self._snapshots(target, controlled, candidate)
        buckets = self._bucket_rows(snapshots, history)
        payload = {
            "module": "history_gap_dashboard",
            "current_only": True,
            "generated_at": self._generated_at(target, history),
            "summary": self._summary(buckets, history),
            "buckets": buckets,
            "history_entries": history.get("history_entries") or [],
            "history_entry_summary": self._history_entry_summary(history),
            "safety": {
                "ratio_only": True,
                "current_only": True,
                "uses_latest_index_modules": True,
                "writes_research_files": False,
                "updates_latest_index": False,
                "updates_current_modules": False,
                "generates_action_plan": False,
                "trading_feature": False,
                "execution_feature": False,
            },
            "source_modules": {
                "target_allocation": self.current.source_for_module("target_allocation"),
                "portfolio_snapshot": self.current.source_for_module("portfolio_snapshot"),
                "market_score": self.current.source_for_module("market_score"),
            },
        }
        sanitized = RatioOnlyService.sanitize(payload)
        RatioOnlyService.assert_safe(sanitized)
        return sanitized

    def get_bucket(self, bucket: str) -> dict[str, Any]:
        for row in self.summary().get("buckets") or []:
            if row.get("bucket") == bucket:
                return row
        raise LookupError(bucket)

    def _snapshots(self, target: dict[str, Any], controlled: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "source_kind": "current_reference",
                "generated_at": target.get("generated_at"),
                "basis_trade_date": target.get("basis_trade_date"),
                "status": "current",
                "buckets": target.get("buckets") or [],
            },
            {
                "source_kind": "controlled_shadow",
                "generated_at": controlled.get("generated_at"),
                "basis_trade_date": controlled.get("basis_trade_date"),
                "status": controlled.get("status"),
                "buckets": ((controlled.get("shadow") or {}).get("buckets") or []),
            },
            {
                "source_kind": "candidate_audit",
                "generated_at": candidate.get("generated_at"),
                "basis_trade_date": candidate.get("basis_trade_date"),
                "status": candidate.get("status"),
                "buckets": ((candidate.get("candidate") or {}).get("buckets") or []),
            },
        ]

    def _bucket_rows(self, snapshots: list[dict[str, Any]], history: dict[str, Any]) -> list[dict[str, Any]]:
        bucket_names: set[str] = set()
        for snapshot in snapshots:
            for bucket in snapshot.get("buckets") or []:
                name = self._bucket_name(bucket)
                if name:
                    bucket_names.add(name)
        rows = []
        for bucket in sorted(bucket_names):
            points = [point for snapshot in snapshots if (point := self._bucket_point(snapshot, bucket))]
            current = next((point for point in points if point.get("source_kind") == "current_reference"), {})
            gap = current.get("gap_pct")
            status = self._gap_status(gap)
            row = {
                "bucket": bucket,
                "actual_pct": current.get("actual_pct"),
                "target_pct": current.get("target_pct"),
                "gap_pct": gap,
                "gap_status": status,
                "alert_status": self._alert_status(status),
                "last_update_timestamp": current.get("generated_at") or current.get("basis_trade_date"),
                "history_point_count": len(points),
                "source_count": len(history.get("history_entries") or []),
                "timeline": points,
            }
            rows.append(RatioOnlyService.sanitize(row))
        rows.sort(key=lambda item: (self._gap_rank(item.get("gap_status")), str(item.get("bucket") or "")))
        return rows

    def _bucket_point(self, snapshot: dict[str, Any], bucket: str) -> dict[str, Any] | None:
        for row in snapshot.get("buckets") or []:
            if self._bucket_name(row) != bucket:
                continue
            point = {
                "source_kind": snapshot.get("source_kind"),
                "generated_at": snapshot.get("generated_at"),
                "basis_trade_date": snapshot.get("basis_trade_date"),
                "status": snapshot.get("status"),
                "actual_pct": row.get("actual_pct"),
                "target_pct": row.get("target_pct"),
                "gap_pct": row.get("gap_pct"),
                "gap_status": self._gap_status(row.get("gap_pct")),
                "alert_status": self._alert_status(self._gap_status(row.get("gap_pct"))),
            }
            return RatioOnlyService.sanitize(point)
        return None

    @staticmethod
    def _bucket_name(row: dict[str, Any]) -> str | None:
        value = row.get("bucket") or row.get("key")
        return str(value) if value else None

    @staticmethod
    def _gap_status(value: Any) -> str:
        if value is None:
            return "unknown"
        gap = abs(float(value))
        if gap <= 1:
            return "green"
        if gap <= 5:
            return "yellow"
        return "red"

    @staticmethod
    def _alert_status(status: str) -> str:
        return {
            "green": "ok",
            "yellow": "review",
            "red": "attention",
        }.get(status, "unknown")

    @staticmethod
    def _gap_rank(status: Any) -> int:
        return {"red": 0, "yellow": 1, "unknown": 2, "green": 3}.get(str(status), 4)

    @staticmethod
    def _generated_at(target: dict[str, Any], history: dict[str, Any]) -> str:
        return str(target.get("generated_at") or history.get("generated_at") or datetime.now().strftime("%Y-%m-%d_%H%M%S"))

    @staticmethod
    def _history_entry_summary(history: dict[str, Any]) -> dict[str, Any]:
        entries = history.get("history_entries") or []
        return {
            "source_count": len(entries),
            "matched_count": sum(1 for item in entries if item.get("matched") is True),
            "diff_count": sum(int(item.get("diff_count") or 0) for item in entries),
            "replay_failed_count": sum(int(item.get("replay_failed") or 0) for item in entries if item.get("replay_failed") is not None),
        }

    @staticmethod
    def _summary(buckets: list[dict[str, Any]], history: dict[str, Any]) -> dict[str, Any]:
        alerts = [item for item in buckets if item.get("alert_status") in {"review", "attention"}]
        return {
            "bucket_count": len(buckets),
            "green_count": sum(1 for item in buckets if item.get("gap_status") == "green"),
            "yellow_count": sum(1 for item in buckets if item.get("gap_status") == "yellow"),
            "red_count": sum(1 for item in buckets if item.get("gap_status") == "red"),
            "unknown_count": sum(1 for item in buckets if item.get("gap_status") == "unknown"),
            "alert_count": len(alerts),
            "history_source_count": len(history.get("history_entries") or []),
        }
