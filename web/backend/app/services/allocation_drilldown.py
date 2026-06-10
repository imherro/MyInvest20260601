from __future__ import annotations

from typing import Any
from urllib.parse import quote

from sqlalchemy.orm import Session

from ..repositories.allocation_repo import AllocationRepository
from .current_state import CurrentStateService
from .market_position import MarketPositionService
from .ratio_only import RatioOnlyService
from .subject_gap import SubjectGapService
from .subject_status import SubjectStatusService
from .theme_status import ThemeStatusService


class AllocationDrilldownService:
    """Read-only allocation drilldown assembled from current SQLite state."""

    def __init__(self, session: Session):
        self.session = session
        self.current = CurrentStateService(session)
        self.repo = AllocationRepository(session)

    def buckets(self, bucket: str | None = None, detail: str = "summary") -> dict[str, Any]:
        context = self._context()
        rows = [self._bucket_row(row, context, detail=detail) for row in context["target_buckets"]]
        if bucket:
            rows = [row for row in rows if row.get("bucket") == bucket]
            if not rows:
                raise LookupError(bucket)
        payload = {
            "module": "allocation_bucket_drilldown",
            "current_only": True,
            "detail": "full" if detail == "full" else "summary",
            "query": {"bucket": bucket},
            "generated_at": context["generated_at"],
            "basis_trade_date": context["basis_trade_date"],
            "market_position": context["market_position"],
            "summary": self._bucket_summary(rows),
            "buckets": rows,
            "source_modules": context["source_modules"],
            "safety": self._safety(),
        }
        RatioOnlyService.assert_safe(payload)
        return RatioOnlyService.sanitize(payload)

    def subjects(self, subject: str | None = None, detail: str = "summary") -> dict[str, Any]:
        context = self._context()
        rows = [self._subject_row(row, context, detail=detail) for row in context["subject_gap_rows"]]
        if subject:
            subject_key = subject.strip().lower()
            rows = [
                row
                for row in rows
                if str(row.get("code") or "").lower() == subject_key
                or str(row.get("name") or "").lower() == subject_key
            ]
            if not rows:
                raise LookupError(subject)
        payload = {
            "module": "allocation_subject_drilldown",
            "current_only": True,
            "detail": "full" if detail == "full" else "summary",
            "query": {"subject": subject},
            "generated_at": context["generated_at"],
            "basis_trade_date": context["basis_trade_date"],
            "market_position": context["market_position"],
            "summary": self._subject_summary(rows),
            "subjects": rows,
            "source_modules": context["source_modules"],
            "safety": self._safety(),
        }
        RatioOnlyService.assert_safe(payload)
        return RatioOnlyService.sanitize(payload)

    def _context(self) -> dict[str, Any]:
        target = self.repo.target_allocation() or {}
        portfolio = self.repo.portfolio_snapshot() or {}
        subject_gap = SubjectGapService(self.session).gap()
        subject_status = SubjectStatusService(self.session).list_statuses()
        target_buckets = target.get("buckets") or []
        subject_gap_rows = subject_gap.get("rows") or []
        status_by_code = {row.get("code"): row for row in subject_status.get("subjects") or []}
        subjects_by_bucket: dict[str, list[dict[str, Any]]] = {}
        for row in subject_gap_rows:
            bucket = str(row.get("bucket") or "unknown")
            subjects_by_bucket.setdefault(bucket, []).append(row)

        market_position: dict[str, Any] | None
        try:
            market_position = MarketPositionService(self.session).get_current_market_position()
        except LookupError:
            market_position = None

        theme_map = self._theme_map()
        generated_at = self._latest_text(target.get("generated_at"), portfolio.get("generated_at"))
        basis_trade_date = self._latest_text(target.get("basis_trade_date"), portfolio.get("basis_trade_date"))
        return {
            "target": target,
            "portfolio": portfolio,
            "target_buckets": target_buckets,
            "subject_gap_rows": subject_gap_rows,
            "status_by_code": status_by_code,
            "subjects_by_bucket": subjects_by_bucket,
            "market_position": market_position,
            "theme_map": theme_map,
            "generated_at": generated_at,
            "basis_trade_date": basis_trade_date,
            "source_modules": self.repo.source_modules(["target_allocation", "portfolio_snapshot", "market_score"]),
        }

    def _bucket_row(self, row: dict[str, Any], context: dict[str, Any], *, detail: str) -> dict[str, Any]:
        bucket = row.get("bucket")
        subjects = [self._subject_row(item, context, detail="summary") for item in context["subjects_by_bucket"].get(bucket, [])]
        status_counts: dict[str, int] = {}
        for item in subjects:
            status = str(item.get("research_first_status") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        payload = {
            "bucket": bucket,
            "actual_pct": row.get("actual_pct"),
            "target_pct": row.get("target_pct"),
            "gap_pct": row.get("gap_pct"),
            "gap_status": self._gap_status(row.get("gap_pct")),
            "position_pct_total": self._sum_pct(item.get("position_pct") for item in subjects),
            "subject_count": len(subjects),
            "research_first_counts": status_counts,
            "generated_at": context["target"].get("generated_at"),
            "basis_trade_date": context["target"].get("basis_trade_date"),
            "review_links": {
                "bucket": f"/buckets/drilldown?bucket={quote(str(bucket or ''), safe='')}",
                "subject_list": "/subjects/drilldown",
            },
        }
        if detail == "full":
            payload["subjects"] = subjects
        return RatioOnlyService.sanitize(payload)

    def _subject_row(self, row: dict[str, Any], context: dict[str, Any], *, detail: str) -> dict[str, Any]:
        code = row.get("code")
        status = context["status_by_code"].get(code) or {}
        themes = context["theme_map"].get(code, [])
        payload = {
            "code": code,
            "name": row.get("name"),
            "subject_type": status.get("subject_type") or row.get("subject_type"),
            "bucket": row.get("bucket"),
            "position_pct": row.get("position_pct"),
            "bucket_actual_pct": row.get("actual_pct"),
            "bucket_target_pct": row.get("target_pct"),
            "bucket_gap_pct": row.get("gap_pct"),
            "gap_status": row.get("gap_status") or self._gap_status(row.get("gap_pct")),
            "research_first_status": status.get("research_first_status") or "unknown",
            "gate_conclusion": status.get("gate_conclusion") or "unknown",
            "profile_status": status.get("profile_status") or "unknown",
            "valuation_status": status.get("valuation_status") or "unknown",
            "liquidity_status": status.get("liquidity_status") or "unknown",
            "blocking_reason": status.get("blocking_reason") or "",
            "theme_count": len(themes),
            "themes": themes if detail == "full" else [],
            "last_update_timestamp": row.get("last_update_timestamp"),
            "basis_trade_date": row.get("basis_trade_date"),
            "staleness_flag": bool(row.get("staleness_flag")),
            "staleness_reason": row.get("staleness_reason"),
            "review_links": {
                "subject": f"/subjects/drilldown?subject={quote(str(code or ''), safe='')}",
                "bucket": f"/buckets/drilldown?bucket={quote(str(row.get('bucket') or ''), safe='')}",
            },
        }
        if detail != "full":
            payload.pop("themes", None)
        return RatioOnlyService.sanitize(payload)

    def _theme_map(self) -> dict[Any, list[dict[str, Any]]]:
        try:
            themes = ThemeStatusService(self.session).status().get("themes") or []
        except Exception:  # noqa: BLE001
            return {}
        result: dict[Any, list[dict[str, Any]]] = {}
        for theme in themes:
            for item in [*(theme.get("associated_etfs") or []), *(theme.get("associated_stocks") or [])]:
                code = item.get("code")
                if not code:
                    continue
                result.setdefault(code, []).append(
                    {
                        "theme_name": theme.get("theme_name"),
                        "status": theme.get("status"),
                        "tactical_rating": theme.get("tactical_rating"),
                        "stage": theme.get("stage"),
                    }
                )
        return result

    @staticmethod
    def _bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "bucket_count": len(rows),
            "subject_count": sum(int(row.get("subject_count") or 0) for row in rows),
            "green_count": sum(1 for row in rows if row.get("gap_status") == "green"),
            "yellow_count": sum(1 for row in rows if row.get("gap_status") == "yellow"),
            "red_count": sum(1 for row in rows if row.get("gap_status") == "red"),
            "unknown_count": sum(1 for row in rows if row.get("gap_status") == "unknown"),
        }

    @staticmethod
    def _subject_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "subject_count": len(rows),
            "research_first_count": sum(1 for row in rows if row.get("research_first_status") == "research_first"),
            "blocked_count": sum(1 for row in rows if row.get("research_first_status") == "blocked"),
            "pass_count": sum(1 for row in rows if row.get("research_first_status") == "pass"),
            "stale_count": sum(1 for row in rows if row.get("staleness_flag")),
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
    def _sum_pct(values: Any) -> float:
        total = 0.0
        for value in values:
            if value is None:
                continue
            total += float(value)
        return round(total, 4)

    @staticmethod
    def _latest_text(*values: Any) -> str | None:
        candidates = [str(value) for value in values if value]
        return max(candidates) if candidates else None
