from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .current_state import CurrentStateService
from .ratio_only import RatioOnlyService
from .subject_gap import SubjectGapService
from .subject_status import SubjectStatusService


ACTION_STATUSES = {"buy", "add", "reduce", "sell"}
DEFAULT_BUCKET_ORDER = ["cash_short", "core_base", "attack_mainline", "defense", "legacy_watch", "unknown"]


class BucketExplorerService:
    def __init__(self, session: Session):
        self.session = session
        self.current = CurrentStateService(session)

    def status(self) -> dict[str, Any]:
        buckets = self._bucket_rows()
        payload = {
            "module": "bucket_explorer",
            "current_only": True,
            "generated_at": self._generated_at(),
            "summary": self._summary(buckets),
            "buckets": buckets,
            "safety": {"ratio_only": True, "current_only": True},
            "source_modules": {
                "target_allocation": self.current.source_for_module("target_allocation"),
                "portfolio_snapshot": self.current.source_for_module("portfolio_snapshot"),
            },
        }
        RatioOnlyService.assert_safe(payload)
        return RatioOnlyService.sanitize(payload)

    def get_bucket(self, bucket: str) -> dict[str, Any]:
        for row in self.status().get("buckets") or []:
            if row.get("bucket") == bucket:
                return row
        raise LookupError(bucket)

    def _bucket_rows(self) -> list[dict[str, Any]]:
        target = self.current.target_allocation() or {}
        target_buckets = {row.get("bucket"): row for row in target.get("buckets") or [] if row.get("bucket")}
        positions = self._position_rows()
        subjects_by_bucket: dict[str, list[dict[str, Any]]] = {}
        for row in positions:
            subjects_by_bucket.setdefault(str(row.get("bucket") or "unknown"), []).append(row)

        bucket_names = set(target_buckets) | set(subjects_by_bucket)
        ordered = [bucket for bucket in DEFAULT_BUCKET_ORDER if bucket in bucket_names]
        ordered.extend(sorted(bucket_names - set(ordered)))

        rows: list[dict[str, Any]] = []
        for bucket in ordered:
            allocation = target_buckets.get(bucket) or {}
            subjects = subjects_by_bucket.get(bucket) or []
            gap_status = self._gap_status(allocation.get("actual_pct"), allocation.get("target_pct"), allocation.get("gap_pct"))
            row = {
                "bucket": bucket,
                "actual_pct": allocation.get("actual_pct"),
                "target_pct": allocation.get("target_pct"),
                "gap_pct": allocation.get("gap_pct"),
                "gap_status": gap_status,
                "subject_count": len(subjects),
                "pass_count": sum(1 for item in subjects if item.get("research_first_status") == "pass"),
                "research_first_count": sum(1 for item in subjects if item.get("research_first_status") == "research_first"),
                "blocked_count": sum(1 for item in subjects if item.get("research_first_status") == "blocked"),
                "stale_count": sum(1 for item in subjects if item.get("staleness_flag")),
                "risk_notes": self._risk_notes(bucket, allocation, subjects, gap_status),
                "subjects": subjects,
            }
            rows.append(RatioOnlyService.sanitize(row))
        return rows

    def _position_rows(self) -> list[dict[str, Any]]:
        portfolio = self.current.portfolio() or {}
        status_rows = SubjectStatusService(self.session).list_statuses().get("subjects") or []
        gap_rows = SubjectGapService(self.session).gap().get("rows") or []
        status_by_code = {row.get("code"): row for row in status_rows if row.get("code")}
        gap_by_code = {row.get("code"): row for row in gap_rows if row.get("code")}
        rows: list[dict[str, Any]] = []
        for position in portfolio.get("positions") or []:
            code = position.get("code")
            status = status_by_code.get(code) or {}
            gap = gap_by_code.get(code) or {}
            bucket = self._display_bucket(position.get("bucket") or status.get("bucket") or "unknown")
            gate_conclusion = self._safe_conclusion(status.get("gate_conclusion"))
            row = {
                "code": code,
                "name": position.get("name") or status.get("name"),
                "subject_type": status.get("subject_type") or position.get("subject_type"),
                "bucket": bucket,
                "position_pct": position.get("position_pct"),
                "profile_status": status.get("profile_status") or "missing",
                "valuation_status": status.get("valuation_status") or "missing",
                "liquidity_status": status.get("liquidity_status") or "missing",
                "research_first_status": status.get("research_first_status") or "research_first",
                "gate_conclusion": gate_conclusion,
                "blocking_reason": status.get("blocking_reason"),
                "staleness_flag": bool(gap.get("staleness_flag")),
                "source_paths": status.get("source_paths") or gap.get("source_paths") or {},
            }
            rows.append(RatioOnlyService.sanitize(row))
        rows.sort(key=lambda item: (str(item.get("bucket") or ""), -(float(item.get("position_pct") or 0))))
        return rows

    def _generated_at(self) -> str | None:
        target = self.current.target_allocation() or {}
        portfolio = self.current.portfolio() or {}
        candidates = [str(value) for value in [target.get("generated_at"), portfolio.get("generated_at")] if value]
        return max(candidates) if candidates else None

    @staticmethod
    def _display_bucket(value: Any) -> str:
        return "cash_short" if value == "bond_cash" else (str(value or "unknown") or "unknown")

    @staticmethod
    def _safe_conclusion(value: Any) -> str:
        conclusion = str(value or "unknown").strip().lower()
        return "blocked" if conclusion in ACTION_STATUSES else (conclusion or "unknown")

    @staticmethod
    def _gap_status(actual: Any, target: Any, gap: Any) -> str:
        if actual is None or target is None or gap is None:
            return "unknown"
        actual_value = float(actual)
        target_value = float(target)
        gap_value = float(gap)
        if target_value == 0 and actual_value > 0:
            return "zero_target_nonzero_actual"
        if abs(gap_value) <= 1:
            return "near_target"
        return "overweight" if gap_value > 0 else "underweight"

    @staticmethod
    def _risk_notes(bucket: str, allocation: dict[str, Any], subjects: list[dict[str, Any]], gap_status: str) -> list[str]:
        notes: list[str] = []
        if gap_status == "zero_target_nonzero_actual":
            notes.append("target is zero while current exposure remains nonzero")
        elif gap_status == "overweight":
            notes.append("actual allocation is above target")
        elif gap_status == "underweight":
            notes.append("actual allocation is below target")
        if any(item.get("research_first_status") == "research_first" for item in subjects):
            notes.append("ResearchFirst items present")
        if any(item.get("research_first_status") == "blocked" for item in subjects):
            notes.append("blocked gate items present")
        if any(item.get("staleness_flag") for item in subjects):
            notes.append("stale subject data present")
        if bucket == "legacy_watch":
            notes.append("legacy watch bucket is review-only")
        if not allocation:
            notes.append("bucket allocation target is missing")
        return notes

    @staticmethod
    def _summary(buckets: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "bucket_count": len(buckets),
            "overweight_count": sum(1 for item in buckets if item.get("gap_status") == "overweight"),
            "underweight_count": sum(1 for item in buckets if item.get("gap_status") == "underweight"),
            "research_first_count": sum(int(item.get("research_first_count") or 0) for item in buckets),
            "blocked_count": sum(int(item.get("blocked_count") or 0) for item in buckets),
        }
