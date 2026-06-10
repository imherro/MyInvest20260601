from __future__ import annotations

from typing import Any
from urllib.parse import quote

from sqlalchemy.orm import Session

from .current_state import CurrentStateService
from .decision_timeline import DecisionTimelineService
from .history_gap_dashboard import HistoryGapDashboardService
from .ratio_only import RatioOnlyService
from .subject_gap import SubjectGapService
from .subject_status import SubjectStatusService
from .theme_status import ThemeStatusService


class HistoricalMetricsService:
    """Read-only historical metrics assembled from current and audit summaries."""

    def __init__(self, session: Session):
        self.session = session
        self.current = CurrentStateService(session)

    def metrics(self) -> dict[str, Any]:
        history_gap = HistoryGapDashboardService(self.session).summary()
        subject_gap = SubjectGapService(self.session).gap()
        subject_status = SubjectStatusService(self.session).list_statuses()
        theme_status = ThemeStatusService(self.session).status()
        decision_timeline = DecisionTimelineService(self.session).timeline()
        market_score = self.current.market_score()

        buckets = self._bucket_metrics(history_gap.get("buckets") or [])
        subjects = self._subject_metrics(subject_gap.get("rows") or [], subject_status.get("subjects") or [])
        themes = self._theme_metrics(theme_status.get("themes") or [])
        decisions = self._decision_type_metrics(decision_timeline.get("events") or [])
        series = {
            "bucket_gap": self._bucket_gap_series(history_gap.get("buckets") or []),
            "market_score": self._market_score_series(market_score),
        }
        entities = [*buckets, *subjects, *themes, *decisions]
        payload = {
            "module": "historical_metrics",
            "current_only": True,
            "generated_at": self._latest_text(
                history_gap.get("generated_at"),
                decision_timeline.get("generated_at"),
                market_score.get("generated_at") if market_score else None,
            ),
            "summary": self._summary(buckets, subjects, themes, decisions, history_gap, decision_timeline),
            "series": series,
            "aggregations": {
                "buckets": buckets,
                "subjects": subjects,
                "themes": themes,
                "decision_types": decisions,
            },
            "entities": entities,
            "source_modules": {
                "target_allocation": self.current.source_for_module("target_allocation"),
                "portfolio_snapshot": self.current.source_for_module("portfolio_snapshot"),
                "market_score": self.current.source_for_module("market_score"),
                "decision_log": {"path": "research/logs/decision_log.md"},
                "history_gap": {"path": "db.HistoryGapDashboardService"},
            },
            "safety": self._safety(),
        }
        return self._safe(payload)

    def get_entity(self, entity_id: str) -> dict[str, Any]:
        for entity in self.metrics()["entities"]:
            if str(entity.get("entity_id") or "") == entity_id:
                return self._safe({"entity": entity})
        raise LookupError(entity_id)

    def _bucket_metrics(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for row in rows:
            trend = self._trend(row.get("timeline") or [])
            bucket = row.get("bucket")
            result.append(
                {
                    "entity_id": f"bucket-{bucket}",
                    "entity_type": "bucket",
                    "label": bucket,
                    "bucket": bucket,
                    "status": row.get("gap_status") or "unknown",
                    "alert_status": row.get("alert_status") or "unknown",
                    "actual_pct": row.get("actual_pct"),
                    "target_pct": row.get("target_pct"),
                    "gap_pct": row.get("gap_pct"),
                    "latest_timestamp": row.get("last_update_timestamp"),
                    "point_count": row.get("history_point_count") or 0,
                    "trend_indicator": trend["trend_indicator"],
                    "gap_delta_pp": trend["gap_delta_pp"],
                    "review_links": {
                        "history_gap": f"/history/gap-dashboard",
                        "bucket_drilldown": f"/buckets/drilldown?bucket={quote(str(bucket or ''), safe='')}",
                    },
                }
            )
        return result

    @staticmethod
    def _subject_metrics(rows: list[dict[str, Any]], statuses: list[dict[str, Any]]) -> list[dict[str, Any]]:
        status_by_code = {row.get("code"): row for row in statuses}
        result = []
        for row in rows:
            code = row.get("code")
            status = status_by_code.get(code) or {}
            result.append(
                {
                    "entity_id": f"subject-{code}",
                    "entity_type": "subject",
                    "label": row.get("name") or code,
                    "code": code,
                    "name": row.get("name"),
                    "bucket": row.get("bucket"),
                    "status": status.get("research_first_status") or "unknown",
                    "profile_status": status.get("profile_status") or "unknown",
                    "valuation_status": status.get("valuation_status") or "unknown",
                    "liquidity_status": status.get("liquidity_status") or "unknown",
                    "position_pct": row.get("position_pct"),
                    "actual_pct": row.get("actual_pct"),
                    "target_pct": row.get("target_pct"),
                    "gap_pct": row.get("gap_pct"),
                    "staleness_flag": bool(row.get("staleness_flag")),
                    "latest_timestamp": row.get("last_update_timestamp"),
                    "point_count": 1,
                    "trend_indicator": "current_only",
                    "review_links": {"subject": f"/subjects/drilldown?subject={quote(str(code or ''), safe='')}"},
                }
            )
        return result

    @staticmethod
    def _theme_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for row in rows:
            theme = row.get("theme_name")
            result.append(
                {
                    "entity_id": f"theme-{theme}",
                    "entity_type": "theme",
                    "label": theme,
                    "theme_name": theme,
                    "status": row.get("status") or "unknown",
                    "tactical_rating": row.get("tactical_rating"),
                    "stage": row.get("stage"),
                    "latest_timestamp": row.get("generated_at"),
                    "basis_trade_date": row.get("basis_trade_date"),
                    "associated_etf_count": len(row.get("associated_etfs") or []),
                    "associated_stock_count": len(row.get("associated_stocks") or []),
                    "leader_count": len(row.get("leaders") or []),
                    "conflict_count": len(row.get("conflicts") or []),
                    "point_count": 1,
                    "trend_indicator": "current_only",
                    "review_links": {"theme_center": "/themes"},
                }
            )
        return result

    @staticmethod
    def _decision_type_metrics(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        counts: dict[str, dict[str, Any]] = {}
        for event in events:
            event_type = str(event.get("event_type") or "unknown")
            item = counts.setdefault(
                event_type,
                {
                    "entity_id": f"decision_type-{event_type}",
                    "entity_type": "decision_type",
                    "label": event_type,
                    "status": "logged",
                    "event_count": 0,
                    "latest_timestamp": None,
                    "point_count": 0,
                    "trend_indicator": "event_count",
                    "review_links": {"decision_timeline": "/decision-timeline"},
                },
            )
            item["event_count"] += 1
            item["point_count"] += 1
            timestamp = event.get("timestamp")
            if timestamp and (not item["latest_timestamp"] or str(timestamp) > str(item["latest_timestamp"])):
                item["latest_timestamp"] = timestamp
        return list(counts.values())

    @staticmethod
    def _bucket_gap_series(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        points = []
        for row in rows:
            bucket = row.get("bucket")
            for point in row.get("timeline") or []:
                points.append(
                    {
                        "entity_id": f"bucket-{bucket}",
                        "entity_type": "bucket",
                        "bucket": bucket,
                        "timestamp": point.get("generated_at"),
                        "basis_trade_date": point.get("basis_trade_date"),
                        "source_module": point.get("source_kind"),
                        "status": point.get("status") or point.get("gap_status") or "unknown",
                        "actual_pct": point.get("actual_pct"),
                        "target_pct": point.get("target_pct"),
                        "gap_pct": point.get("gap_pct"),
                        "gap_status": point.get("gap_status"),
                    }
                )
        return sorted(points, key=lambda item: (str(item.get("bucket") or ""), str(item.get("timestamp") or "")))

    @staticmethod
    def _market_score_series(market_score: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not market_score:
            return []
        return [
            {
                "entity_id": "market-score-current",
                "entity_type": "market_score",
                "timestamp": market_score.get("generated_at"),
                "basis_trade_date": market_score.get("basis_trade_date"),
                "score": market_score.get("score"),
                "status": market_score.get("state") or "unknown",
                "equity_min_pct": market_score.get("equity_min_pct"),
                "equity_max_pct": market_score.get("equity_max_pct"),
                "cash_min_pct": market_score.get("cash_min_pct"),
                "cash_max_pct": market_score.get("cash_max_pct"),
            }
        ]

    @staticmethod
    def _trend(points: list[dict[str, Any]]) -> dict[str, Any]:
        gaps = [float(point.get("gap_pct")) for point in points if point.get("gap_pct") is not None]
        if len(gaps) < 2:
            return {"trend_indicator": "current_only", "gap_delta_pp": 0.0}
        delta = round(gaps[-1] - gaps[0], 4)
        if abs(delta) <= 0.01:
            indicator = "stable"
        elif abs(gaps[-1]) < abs(gaps[0]):
            indicator = "narrowing"
        else:
            indicator = "widening"
        return {"trend_indicator": indicator, "gap_delta_pp": delta}

    @staticmethod
    def _summary(
        buckets: list[dict[str, Any]],
        subjects: list[dict[str, Any]],
        themes: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
        history_gap: dict[str, Any],
        decision_timeline: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "entity_count": len(buckets) + len(subjects) + len(themes) + len(decisions),
            "bucket_count": len(buckets),
            "subject_count": len(subjects),
            "theme_count": len(themes),
            "decision_type_count": len(decisions),
            "history_source_count": (history_gap.get("summary") or {}).get("history_source_count", 0),
            "decision_event_count": (decision_timeline.get("summary") or {}).get("event_count", 0),
            "red_gap_count": sum(1 for row in buckets if row.get("status") == "red"),
            "yellow_gap_count": sum(1 for row in buckets if row.get("status") == "yellow"),
            "research_first_count": sum(1 for row in subjects if row.get("status") == "research_first"),
            "stale_subject_count": sum(1 for row in subjects if row.get("staleness_flag")),
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
    def _latest_text(*values: Any) -> str | None:
        candidates = [str(value) for value in values if value]
        return max(candidates) if candidates else None

    @staticmethod
    def _safe(payload: dict[str, Any]) -> dict[str, Any]:
        sanitized = RatioOnlyService.sanitize(payload)
        RatioOnlyService.assert_safe(sanitized)
        return sanitized
