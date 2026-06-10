from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .current_state import CurrentStateService
from .market_position import MarketPositionService
from .ratio_only import RatioOnlyService
from .subject_gap import SubjectGapService
from .subject_status import SubjectStatusService
from .system_check import SystemCheckService


class DashboardService:
    def __init__(self, session: Session):
        self.session = session
        self.current = CurrentStateService(session)

    def current_dashboard(self) -> dict[str, Any]:
        latest_index = self.current.latest_index()
        action_plan = self.current.action_plan() or {}
        target_allocation = self.current.target_allocation() or {}
        portfolio = self.current.portfolio() or {}
        intraday_rules = self.current.intraday_rules() or {}
        market_score = self.current.market_score() or {}
        market_position = self._market_position(market_score)
        system_check = SystemCheckService(self.session).current()
        subject_status = SubjectStatusService(self.session).list_statuses()
        subject_gap = SubjectGapService(self.session).gap()

        payload = {
            "module": "dashboard_current",
            "current_only": True,
            "generated_at": latest_index.get("generated_at"),
            "system_status": self._system_status(system_check, intraday_rules),
            "market_position": self._market_position_summary(market_score, market_position),
            "action_plan_summary": self._action_plan_summary(action_plan),
            "allocation_summary": self._allocation_summary(portfolio, target_allocation),
            "subject_status_summary": self._subject_status_summary(subject_status),
            "subject_gap_summary": self._subject_gap_summary(subject_gap),
            "quick_links": self._quick_links(),
        }
        RatioOnlyService.assert_safe(payload)
        return RatioOnlyService.sanitize(payload)

    def _market_position(self, market_score: dict[str, Any]) -> dict[str, Any]:
        try:
            return MarketPositionService(self.session).get_current_market_position()
        except LookupError:
            return {
                "score": market_score.get("score"),
                "label": market_score.get("state") or "unknown",
                "equity_min_pct": market_score.get("equity_min_pct"),
                "equity_max_pct": market_score.get("equity_max_pct"),
                "cash_min_pct": market_score.get("cash_min_pct"),
                "cash_max_pct": market_score.get("cash_max_pct"),
            }

    @staticmethod
    def _system_status(system_check: dict[str, Any], intraday_rules: dict[str, Any]) -> dict[str, Any]:
        project_check = next(
            (item for item in system_check.get("checks", []) if item.get("check_name") == "project_check_current_only"),
            {},
        )
        research_first = system_check.get("research_first_gate") or {}
        allocation = system_check.get("allocation_consistency") or {}
        sensitive = system_check.get("sensitive_scan") or {}
        return {
            "status": system_check.get("status"),
            "project_check_status": project_check.get("status"),
            "research_first_gate_status": research_first.get("status"),
            "allocation_consistency_status": allocation.get("status"),
            "sensitive_scan_status": sensitive.get("status"),
            "intraday_status": intraday_rules.get("status"),
            "intraday_stale_flag": bool(intraday_rules.get("stale_flag")),
            "intraday_degraded_flag": bool(intraday_rules.get("degraded_flag")),
        }

    @staticmethod
    def _market_position_summary(market_score: dict[str, Any], market_position: dict[str, Any]) -> dict[str, Any]:
        return {
            "score": market_position.get("score", market_score.get("score")),
            "label": market_position.get("label") or market_score.get("state"),
            "state": market_score.get("state"),
            "equity_target_min_pct": market_position.get("equity_min_pct") or market_score.get("equity_min_pct"),
            "equity_target_max_pct": market_position.get("equity_max_pct") or market_score.get("equity_max_pct"),
            "cash_target_min_pct": market_position.get("cash_min_pct") or market_score.get("cash_min_pct"),
            "cash_target_max_pct": market_position.get("cash_max_pct") or market_score.get("cash_max_pct"),
            "basis_trade_date": market_score.get("basis_trade_date"),
            "generated_at": market_score.get("generated_at"),
        }

    @staticmethod
    def _action_plan_summary(action_plan: dict[str, Any]) -> dict[str, Any]:
        actions = action_plan.get("actions") or []
        research_first = action_plan.get("research_first") or []
        return {
            "generated_at": action_plan.get("generated_at"),
            "basis_trade_date": action_plan.get("basis_trade_date"),
            "market_state": action_plan.get("market_state"),
            "status": action_plan.get("status"),
            "action_count": len(actions),
            "research_first_count": len(research_first),
            "manual_confirmation_required_count": sum(1 for item in actions if item.get("requires_manual_confirmation")),
        }

    @staticmethod
    def _allocation_summary(portfolio: dict[str, Any], target_allocation: dict[str, Any]) -> dict[str, Any]:
        return {
            "equity_current_pct": portfolio.get("equity_pct"),
            "equity_target_min_pct": target_allocation.get("equity_min_pct"),
            "equity_target_max_pct": target_allocation.get("equity_max_pct"),
            "cash_short_current_pct": portfolio.get("cash_short_pct"),
            "cash_short_target_min_pct": target_allocation.get("cash_min_pct"),
            "cash_short_target_max_pct": target_allocation.get("cash_max_pct"),
            "bucket_gaps": target_allocation.get("buckets") or [],
            "generated_at": target_allocation.get("generated_at"),
            "basis_trade_date": target_allocation.get("basis_trade_date"),
        }

    @staticmethod
    def _subject_status_summary(subject_status: dict[str, Any]) -> dict[str, Any]:
        subjects = subject_status.get("subjects") or []
        summary = dict(subject_status.get("summary") or {})
        cash_gate = next((item for item in subjects if item.get("code") == "511360.SH"), None)
        summary["cash_equivalent_gate"] = {
            "code": cash_gate.get("code"),
            "name": cash_gate.get("name"),
            "bucket": cash_gate.get("bucket"),
            "profile_status": cash_gate.get("profile_status"),
            "valuation_status": cash_gate.get("valuation_status"),
            "liquidity_status": cash_gate.get("liquidity_status"),
            "research_first_status": cash_gate.get("research_first_status"),
            "gate_conclusion": cash_gate.get("gate_conclusion"),
            "blocking_reason": cash_gate.get("blocking_reason"),
        } if cash_gate else None
        return summary

    @staticmethod
    def _subject_gap_summary(subject_gap: dict[str, Any]) -> dict[str, Any]:
        return dict(subject_gap.get("summary") or {})

    @staticmethod
    def _quick_links() -> list[dict[str, str]]:
        return [
            {"label": "Action Plan", "href": "/action-plan"},
            {"label": "Target Allocation", "href": "/target-allocation"},
            {"label": "Subject Status", "href": "/subjects"},
            {"label": "Subject Gap", "href": "/subjects/gap"},
            {"label": "Themes", "href": "/themes"},
            {"label": "Buckets", "href": "/buckets"},
            {"label": "Portfolio", "href": "/portfolio"},
            {"label": "Intraday Rules", "href": "/intraday-rules"},
            {"label": "Decision Log", "href": "/decision-log"},
            {"label": "History Snapshot", "href": "/api/history/export?format=json"},
        ]
