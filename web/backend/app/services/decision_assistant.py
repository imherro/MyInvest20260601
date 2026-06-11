from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .current_state import CurrentStateService
from .decision_timeline import DecisionTimelineService
from .history_workbench import HistoryWorkbenchService
from .historical_metrics import HistoricalMetricsService
from .market_position import MarketPositionService
from .ratio_only import RatioOnlyService
from .subject_gap import SubjectGapService
from .subject_status import SubjectStatusService
from .system_check import SystemCheckService


class DecisionAssistantService:
    """Read-only decision-assistant payload assembled from current facts."""

    def __init__(self, session: Session):
        self.session = session
        self.current = CurrentStateService(session)
        self.market = MarketPositionService(session)

    def daily(self) -> dict[str, Any]:
        latest_index = self.current.latest_index()
        market_score = self.current.market_score() or {}
        market_position = self._current_market_position(market_score)
        portfolio = self.current.portfolio() or {}
        target_allocation = self.current.target_allocation() or {}
        action_plan = self.current.action_plan() or {}
        intraday_rules = self.current.intraday_rules() or {}
        system_check = SystemCheckService(self.session).current()
        subject_status = SubjectStatusService(self.session).list_statuses()
        subject_gap = SubjectGapService(self.session).gap()
        decision_timeline = DecisionTimelineService(self.session).timeline()
        historical_metrics = HistoricalMetricsService(self.session).metrics()
        history_quality = HistoryWorkbenchService().quality()

        payload = {
            "module": "decision_assistant_daily",
            "current_only": True,
            "generated_at": self._latest_text(
                latest_index.get("generated_at"),
                market_score.get("generated_at"),
                target_allocation.get("generated_at"),
                action_plan.get("generated_at"),
            ),
            "today": self._today(
                market_score=market_score,
                market_position=market_position,
                portfolio=portfolio,
                target_allocation=target_allocation,
                action_plan=action_plan,
                intraday_rules=intraday_rules,
                system_check=system_check,
                subject_status=subject_status,
            ),
            "next_steps": self._next_steps(
                action_plan=action_plan,
                intraday_rules=intraday_rules,
                subject_status=subject_status,
                subject_gap=subject_gap,
                system_check=system_check,
            ),
            "risk_heatmap": self._risk_heatmap(
                target_allocation=target_allocation,
                intraday_rules=intraday_rules,
                system_check=system_check,
                subject_status=subject_status,
                subject_gap=subject_gap,
                history_quality=history_quality,
            ),
            "research_priorities": self._research_priorities(
                subject_status=subject_status,
                subject_gap=subject_gap,
                action_plan=action_plan,
            ),
            "scenario_simulation": self._scenario_simulation(market_score, market_position),
            "allocation_drift": self._allocation_drift(target_allocation),
            "review_loop": self._review_loop(decision_timeline),
            "history_visuals": self._history_visuals(historical_metrics, history_quality),
            "explanations": self._explanations(),
            "source_modules": {
                "latest_index": {"path": "research/latest_index.json"},
                "market_score": self.current.source_for_module("market_score"),
                "portfolio_snapshot": self.current.source_for_module("portfolio_snapshot"),
                "target_allocation": self.current.source_for_module("target_allocation"),
                "action_plan": self.current.source_for_module("action_plan"),
                "intraday_rules": self.current.source_for_module("intraday_rules"),
            },
            "safety": self._safety(),
        }
        return self._safe(payload)

    def _current_market_position(self, market_score: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.market.get_current_market_position()
        except LookupError:
            return {
                "score": market_score.get("score"),
                "label": market_score.get("state") or "unknown",
                "equity_min_pct": market_score.get("equity_min_pct"),
                "equity_max_pct": market_score.get("equity_max_pct"),
                "cash_min_pct": market_score.get("cash_min_pct"),
                "cash_max_pct": market_score.get("cash_max_pct"),
            }

    def _today(
        self,
        *,
        market_score: dict[str, Any],
        market_position: dict[str, Any],
        portfolio: dict[str, Any],
        target_allocation: dict[str, Any],
        action_plan: dict[str, Any],
        intraday_rules: dict[str, Any],
        system_check: dict[str, Any],
        subject_status: dict[str, Any],
    ) -> dict[str, Any]:
        subject_summary = subject_status.get("summary") or {}
        actions = action_plan.get("actions") or []
        equity_status = self._range_status(
            portfolio.get("equity_pct"),
            target_allocation.get("equity_min_pct"),
            target_allocation.get("equity_max_pct"),
        )
        cash_status = self._range_status(
            portfolio.get("cash_short_pct"),
            target_allocation.get("cash_min_pct"),
            target_allocation.get("cash_max_pct"),
        )
        return {
            "market_score": market_position.get("score", market_score.get("score")),
            "market_label": market_position.get("label") or market_score.get("state") or "unknown",
            "basis_trade_date": market_score.get("basis_trade_date") or action_plan.get("basis_trade_date"),
            "equity_pct": portfolio.get("equity_pct"),
            "equity_target_min_pct": target_allocation.get("equity_min_pct"),
            "equity_target_max_pct": target_allocation.get("equity_max_pct"),
            "equity_status": equity_status,
            "cash_short_pct": portfolio.get("cash_short_pct"),
            "cash_target_min_pct": target_allocation.get("cash_min_pct"),
            "cash_target_max_pct": target_allocation.get("cash_max_pct"),
            "cash_status": cash_status,
            "action_count": len(actions),
            "research_first_count": subject_summary.get("research_first_count", 0),
            "blocked_count": subject_summary.get("blocked_count", 0),
            "manual_review_count": sum(1 for item in actions if item.get("requires_manual_confirmation")),
            "intraday_status": intraday_rules.get("status") or "unknown",
            "intraday_stale_flag": bool(intraday_rules.get("stale_flag")),
            "intraday_degraded_flag": bool(intraday_rules.get("degraded_flag")),
            "system_status": system_check.get("status") or "unknown",
        }

    def _next_steps(
        self,
        *,
        action_plan: dict[str, Any],
        intraday_rules: dict[str, Any],
        subject_status: dict[str, Any],
        subject_gap: dict[str, Any],
        system_check: dict[str, Any],
    ) -> list[dict[str, Any]]:
        subject_summary = subject_status.get("summary") or {}
        gap_summary = subject_gap.get("summary") or {}
        research_first_count = int(subject_summary.get("research_first_count") or 0)
        blocked_count = int(subject_summary.get("blocked_count") or 0)
        red_gap_count = int(gap_summary.get("red_count") or 0)
        action_count = len(action_plan.get("actions") or [])
        return [
            {
                "phase": "盘前",
                "label": "先看每日指挥台",
                "status": self._severity_from_count(blocked_count + red_gap_count, warn_at=1, block_at=3),
                "why": "确认市场、仓位、研究门槛和系统状态是否一致。",
                "next_step": "从风险热力图进入需要复核的页面。",
                "href": "/assistant",
            },
            {
                "phase": "盘前",
                "label": "处理研究优先队列",
                "status": "block" if research_first_count else "ok",
                "why": "ResearchFirst 未通过时，新增动作应先补研究。",
                "next_step": "打开研究员工作台或 ResearchFirst 页面。",
                "href": "/researcher",
            },
            {
                "phase": "盘前",
                "label": "复核操作计划",
                "status": "watch" if action_count else "ok",
                "why": "操作计划只应引用已通过门槛的当前事实。",
                "next_step": "查看操作计划和盘中规则是否匹配。",
                "href": "/action-plan",
            },
            {
                "phase": "盘中",
                "label": "检查盘中规则",
                "status": "warn" if intraday_rules.get("stale_flag") or intraday_rules.get("degraded_flag") else "ok",
                "why": "盘中规则异常时，只能把它当作复核提醒。",
                "next_step": "打开盘中规则页面确认状态。",
                "href": "/intraday-rules",
            },
            {
                "phase": "盘后",
                "label": "完成复盘线索",
                "status": "watch",
                "why": "复盘应记录判断偏差、执行纪律和后续观察点。",
                "next_step": "查看决策时间线和历史指标。",
                "href": "/decision-timeline",
            },
            {
                "phase": "系统",
                "label": "运行发布前检查",
                "status": "warn" if system_check.get("status") != "ok" else "ok",
                "why": "系统检查异常会降低页面和数据可信度。",
                "next_step": "打开系统工作台或工具注册表。",
                "href": "/system",
            },
        ]

    def _risk_heatmap(
        self,
        *,
        target_allocation: dict[str, Any],
        intraday_rules: dict[str, Any],
        system_check: dict[str, Any],
        subject_status: dict[str, Any],
        subject_gap: dict[str, Any],
        history_quality: dict[str, Any],
    ) -> dict[str, Any]:
        subject_summary = subject_status.get("summary") or {}
        gap_summary = subject_gap.get("summary") or {}
        buckets = target_allocation.get("buckets") or []
        max_gap = max([abs(float(row.get("gap_pct") or 0)) for row in buckets] or [0.0])
        items = [
            self._risk_item(
                "allocation_drift",
                "仓位偏离",
                self._gap_severity(max_gap),
                f"最大 bucket 偏离 {max_gap:.2f}pp。",
                "查看仓位偏离和 bucket 钻取。",
                "/buckets/drilldown",
                {"max_gap_pp": round(max_gap, 4), "bucket_count": len(buckets)},
            ),
            self._risk_item(
                "research_first",
                "ResearchFirst",
                "block" if subject_summary.get("research_first_count") or subject_summary.get("blocked_count") else "ok",
                f"{subject_summary.get('research_first_count', 0)} 个标的需要先补研究。",
                "打开研究优先队列。",
                "/research-first",
                {
                    "research_first_count": subject_summary.get("research_first_count", 0),
                    "blocked_count": subject_summary.get("blocked_count", 0),
                },
            ),
            self._risk_item(
                "valuation_gap",
                "估值缺口",
                self._severity_from_count(self._missing_count(subject_status, "missing_valuation"), warn_at=1, block_at=5),
                "估值缺口会限制新增动作。",
                "优先补齐高比例持仓的估值。",
                "/subjects",
                {"missing_valuation_count": self._missing_count(subject_status, "missing_valuation")},
            ),
            self._risk_item(
                "liquidity_gap",
                "流动性缺口",
                self._severity_from_count(self._missing_count(subject_status, "missing_liquidity"), warn_at=1, block_at=5),
                "流动性缺口会影响执行纪律。",
                "优先补齐高比例持仓的流动性门槛。",
                "/subjects",
                {"missing_liquidity_count": self._missing_count(subject_status, "missing_liquidity")},
            ),
            self._risk_item(
                "stale_research",
                "当前性",
                self._severity_from_count(int(gap_summary.get("stale_count") or 0), warn_at=1, block_at=8),
                f"{gap_summary.get('stale_count', 0)} 个标的当前性需要复核。",
                "打开研究缺口页面。",
                "/subjects/gap",
                {"stale_count": gap_summary.get("stale_count", 0)},
            ),
            self._risk_item(
                "intraday_rules",
                "盘中规则",
                "warn" if intraday_rules.get("stale_flag") or intraday_rules.get("degraded_flag") else "ok",
                "盘中规则 stale/degraded 时只能作为提醒。",
                "打开盘中规则页面。",
                "/intraday-rules",
                {
                    "stale_flag": bool(intraday_rules.get("stale_flag")),
                    "degraded_flag": bool(intraday_rules.get("degraded_flag")),
                },
            ),
            self._risk_item(
                "system_checks",
                "系统检查",
                "block" if system_check.get("status") == "fail" else "ok",
                f"系统状态为 {system_check.get('status') or 'unknown'}。",
                "打开系统检查页面。",
                "/system-checks",
                {"system_status": system_check.get("status") or "unknown"},
            ),
            self._risk_item(
                "history_quality",
                "历史库质量",
                self._history_quality_severity(history_quality),
                "历史库用于复盘和趋势观察，不作为实时事实源。",
                "打开历史库质量检查。",
                "/history/quality",
                history_quality.get("summary") or {},
            ),
        ]
        summary = {
            "item_count": len(items),
            "block_count": sum(1 for item in items if item.get("severity") == "block"),
            "warn_count": sum(1 for item in items if item.get("severity") == "warn"),
            "watch_count": sum(1 for item in items if item.get("severity") == "watch"),
            "ok_count": sum(1 for item in items if item.get("severity") == "ok"),
        }
        return {"summary": summary, "items": items}

    def _research_priorities(
        self,
        *,
        subject_status: dict[str, Any],
        subject_gap: dict[str, Any],
        action_plan: dict[str, Any],
    ) -> dict[str, Any]:
        gap_by_code = {row.get("code"): row for row in subject_gap.get("rows") or []}
        rf_codes = {row.get("code") for row in action_plan.get("research_first") or []}
        items = []
        for row in subject_status.get("subjects") or []:
            code = row.get("code")
            gap = gap_by_code.get(code) or {}
            missing = self._missing_reasons(row)
            if not missing and not gap.get("staleness_flag") and abs(float(gap.get("gap_pct") or 0)) <= 1:
                continue
            score = self._priority_score(row, gap, code in rf_codes)
            items.append(
                {
                    "code": code,
                    "name": row.get("name"),
                    "bucket": row.get("bucket"),
                    "priority_score": score,
                    "priority_level": self._priority_level(score),
                    "missing_reasons": missing,
                    "position_pct": gap.get("position_pct"),
                    "bucket_gap_pct": gap.get("gap_pct"),
                    "staleness_flag": bool(gap.get("staleness_flag")),
                    "blocking_reason": row.get("blocking_reason"),
                    "why": self._priority_why(row, gap, code in rf_codes),
                    "next_step": "补齐 profile、valuation、liquidity 后再复核操作计划。",
                    "href": f"/subjects/drilldown?subject={code}",
                }
            )
        items = sorted(items, key=lambda item: (item["priority_score"], str(item.get("code") or "")), reverse=True)[:12]
        return {
            "summary": {
                "item_count": len(items),
                "high_count": sum(1 for item in items if item.get("priority_level") == "high"),
                "medium_count": sum(1 for item in items if item.get("priority_level") == "medium"),
            },
            "items": items,
        }

    def _scenario_simulation(self, market_score: dict[str, Any], market_position: dict[str, Any]) -> dict[str, Any]:
        raw_score = market_position.get("score", market_score.get("score"))
        try:
            current_score = float(raw_score)
        except (TypeError, ValueError):
            return {"summary": {"scenario_count": 0, "current_score": None}, "items": []}
        scores = sorted({self._bounded_score(current_score + delta) for delta in (-10, -5, 0, 5, 10)})
        current_equity_min = self._float_or_none(market_position.get("equity_min_pct"))
        current_equity_max = self._float_or_none(market_position.get("equity_max_pct"))
        items = []
        for score in scores:
            try:
                scenario = self.market.get_position_for_score(score)
            except ValueError:
                continue
            equity_min = self._float_or_none(scenario.get("equity_min_pct"))
            equity_max = self._float_or_none(scenario.get("equity_max_pct"))
            items.append(
                {
                    "score": score,
                    "label": scenario.get("label"),
                    "is_current": abs(score - current_score) < 0.01,
                    "equity_min_pct": equity_min,
                    "equity_max_pct": equity_max,
                    "cash_min_pct": scenario.get("cash_min_pct"),
                    "cash_max_pct": scenario.get("cash_max_pct"),
                    "equity_min_delta_pp": self._delta(equity_min, current_equity_min),
                    "equity_max_delta_pp": self._delta(equity_max, current_equity_max),
                    "why": "复用已固化市场仓位映射，仅展示区间变化。",
                    "next_step": "若情景接近当前分数，先复核目标仓位和盘中规则。",
                }
            )
        return {
            "summary": {
                "scenario_count": len(items),
                "current_score": current_score,
                "mapping_source": MarketPositionService.source,
            },
            "items": items,
        }

    @staticmethod
    def _allocation_drift(target_allocation: dict[str, Any]) -> dict[str, Any]:
        rows = []
        for row in target_allocation.get("buckets") or []:
            gap = float(row.get("gap_pct") or 0)
            rows.append(
                {
                    "bucket": row.get("bucket"),
                    "actual_pct": row.get("actual_pct"),
                    "target_pct": row.get("target_pct"),
                    "gap_pct": row.get("gap_pct"),
                    "severity": DecisionAssistantService._gap_severity(abs(gap)),
                    "why": "bucket actual 与 target 的百分点差。",
                    "href": f"/buckets/drilldown?bucket={row.get('bucket')}",
                }
            )
        rows = sorted(rows, key=lambda item: abs(float(item.get("gap_pct") or 0)), reverse=True)
        return {
            "summary": {
                "bucket_count": len(rows),
                "red_count": sum(1 for row in rows if row.get("severity") in {"warn", "block"}),
            },
            "items": rows,
        }

    @staticmethod
    def _review_loop(decision_timeline: dict[str, Any]) -> dict[str, Any]:
        events = decision_timeline.get("events") or []
        items = []
        for event in events[:8]:
            links = event.get("review_links") or {}
            href = next(iter(links.values()), "/decision-timeline")
            items.append(
                {
                    "event_id": event.get("event_id"),
                    "event_type": event.get("event_type"),
                    "timestamp": event.get("timestamp"),
                    "title": event.get("title"),
                    "status": event.get("status"),
                    "review_focus": DecisionAssistantService._review_focus(event),
                    "href": href,
                }
            )
        summary = decision_timeline.get("summary") or {}
        return {
            "summary": {
                "event_count": summary.get("event_count", len(events)),
                "decision_log_count": summary.get("decision_log_count", 0),
                "action_plan_count": summary.get("action_plan_count", 0),
            },
            "items": items,
        }

    @staticmethod
    def _history_visuals(historical_metrics: dict[str, Any], history_quality: dict[str, Any]) -> list[dict[str, Any]]:
        metrics_summary = historical_metrics.get("summary") or {}
        quality_summary = history_quality.get("summary") or {}
        return [
            {
                "label": "历史指标",
                "href": "/historical-metrics",
                "status": "ok" if metrics_summary.get("entity_count", 0) else "watch",
                "why": "查看 bucket、标的、主题和决策事件的历史指标。",
            },
            {
                "label": "缺口历史",
                "href": "/history/gap-dashboard",
                "status": "watch" if metrics_summary.get("red_gap_count", 0) else "ok",
                "why": "观察 bucket 偏离是否正在扩大或收敛。",
            },
            {
                "label": "市场历史",
                "href": "/market/history",
                "status": "ok" if quality_summary.get("db_ready") else "watch",
                "why": "查看市场分数和权益区间历史。",
            },
            {
                "label": "历史库质量",
                "href": "/history/quality",
                "status": "ok" if quality_summary.get("fail_count", 0) == 0 else "block",
                "why": "确认历史事实库可用于复盘。",
            },
        ]

    @staticmethod
    def _explanations() -> list[dict[str, str]]:
        return [
            {
                "topic": "为什么先看风险热力图",
                "text": "热力图把仓位、研究、盘中规则和系统状态统一成工作流优先级。",
            },
            {
                "topic": "为什么研究优先级会影响收益",
                "text": "高比例持仓和即将影响操作计划的缺口先补齐，能减少临时判断。",
            },
            {
                "topic": "为什么情景推演不等于建议",
                "text": "情景推演只复用既有市场仓位映射，帮助提前准备复核路径。",
            },
            {
                "topic": "为什么保持 ratio-only",
                "text": "页面只展示比例、百分点、状态、日期和原因，避免暴露敏感账户事实。",
            },
        ]

    @staticmethod
    def _risk_item(
        risk_id: str,
        label: str,
        severity: str,
        why: str,
        next_step: str,
        href: str,
        signals: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "risk_id": risk_id,
            "label": label,
            "severity": severity,
            "why": why,
            "next_step": next_step,
            "href": href,
            "signals": signals,
        }

    @staticmethod
    def _range_status(value: Any, low: Any, high: Any) -> str:
        current = DecisionAssistantService._float_or_none(value)
        low_value = DecisionAssistantService._float_or_none(low)
        high_value = DecisionAssistantService._float_or_none(high)
        if current is None or low_value is None or high_value is None:
            return "unknown"
        if low_value <= current <= high_value:
            return "ok"
        drift = min(abs(current - low_value), abs(current - high_value))
        return DecisionAssistantService._gap_severity(drift)

    @staticmethod
    def _gap_severity(value: float) -> str:
        if value <= 1:
            return "ok"
        if value <= 3:
            return "watch"
        if value <= 5:
            return "warn"
        return "block"

    @staticmethod
    def _severity_from_count(count: int, *, warn_at: int, block_at: int) -> str:
        if count >= block_at:
            return "block"
        if count >= warn_at:
            return "warn"
        return "ok"

    @staticmethod
    def _history_quality_severity(history_quality: dict[str, Any]) -> str:
        summary = history_quality.get("summary") or {}
        if not summary.get("db_ready"):
            return "watch"
        if int(summary.get("fail_count") or 0) > 0:
            return "block"
        if int(summary.get("warn_count") or 0) > 0:
            return "warn"
        return "ok"

    @staticmethod
    def _missing_count(subject_status: dict[str, Any], field: str) -> int:
        return sum(1 for row in subject_status.get("subjects") or [] if row.get(field))

    @staticmethod
    def _missing_reasons(row: dict[str, Any]) -> list[str]:
        reasons = []
        for field, label in [
            ("missing_profile", "profile"),
            ("missing_valuation", "valuation"),
            ("missing_liquidity", "liquidity"),
            ("missing_theme_binding", "theme_binding"),
        ]:
            if row.get(field):
                reasons.append(label)
        return reasons

    @staticmethod
    def _priority_score(row: dict[str, Any], gap: dict[str, Any], in_action_plan_queue: bool) -> int:
        score = 0
        score += min(int(float(gap.get("position_pct") or 0) * 4), 40)
        score += min(int(abs(float(gap.get("gap_pct") or 0)) * 3), 30)
        if row.get("missing_profile"):
            score += 30
        if row.get("missing_valuation"):
            score += 25
        if row.get("missing_liquidity"):
            score += 20
        if row.get("missing_theme_binding"):
            score += 10
        if gap.get("staleness_flag"):
            score += 10
        if in_action_plan_queue:
            score += 20
        if row.get("blocking_reason"):
            score += 15
        return min(score, 100)

    @staticmethod
    def _priority_level(score: int) -> str:
        if score >= 70:
            return "high"
        if score >= 35:
            return "medium"
        return "low"

    @staticmethod
    def _priority_why(row: dict[str, Any], gap: dict[str, Any], in_action_plan_queue: bool) -> str:
        parts = []
        missing = DecisionAssistantService._missing_reasons(row)
        if missing:
            parts.append("缺口: " + ", ".join(missing))
        if gap.get("position_pct") is not None:
            parts.append(f"持仓比例 {float(gap.get('position_pct') or 0):.2f}%")
        if gap.get("gap_pct") is not None:
            parts.append(f"bucket 偏离 {float(gap.get('gap_pct') or 0):.2f}pp")
        if in_action_plan_queue:
            parts.append("已进入 ResearchFirst 队列")
        if gap.get("staleness_flag"):
            parts.append("当前性需要复核")
        return "；".join(parts) if parts else "需要人工复核。"

    @staticmethod
    def _review_focus(event: dict[str, Any]) -> str:
        event_type = event.get("event_type")
        if event_type == "action_plan":
            return "复核计划是否遵守 ResearchFirst 和仓位边界。"
        if event_type == "target_allocation":
            return "复核目标区间与 bucket 偏离是否一致。"
        if event_type == "decision_log":
            return "复核当时理由是否仍然成立。"
        return "复核历史事实是否支持当前判断。"

    @staticmethod
    def _bounded_score(value: float) -> float:
        return round(max(0.0, min(100.0, value)), 2)

    @staticmethod
    def _delta(value: float | None, reference: float | None) -> float | None:
        if value is None or reference is None:
            return None
        return round(value - reference, 4)

    @staticmethod
    def _float_or_none(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _latest_text(*values: Any) -> str | None:
        candidates = [str(value) for value in values if value]
        return max(candidates) if candidates else None

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
    def _safe(payload: dict[str, Any]) -> dict[str, Any]:
        sanitized = RatioOnlyService.sanitize(payload)
        RatioOnlyService.assert_safe(sanitized)
        return sanitized
