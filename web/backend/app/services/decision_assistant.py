from __future__ import annotations

from typing import Any
from urllib.parse import quote

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
from .theme_status import ThemeStatusService
from .tool_console import ToolConsoleService


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

    def risk_center(self) -> dict[str, Any]:
        daily = self.daily()
        items = [dict(item) for item in daily["risk_heatmap"]["items"]]
        category_by_id = {
            "allocation_drift": "allocation",
            "research_first": "research",
            "valuation_gap": "valuation",
            "liquidity_gap": "liquidity",
            "stale_research": "research",
            "intraday_rules": "intraday",
            "system_checks": "system",
            "history_quality": "history",
        }
        for item in items:
            item["category"] = category_by_id.get(str(item.get("risk_id")), "other")
            item["impact"] = self._risk_impact(str(item.get("severity") or "ok"))
        categories = sorted({item["category"] for item in items})
        payload = {
            "module": "assistant_risk_center",
            "current_only": True,
            "generated_at": daily.get("generated_at"),
            "summary": daily["risk_heatmap"]["summary"],
            "filters": [{"category": category, "count": sum(1 for item in items if item["category"] == category)} for category in categories],
            "items": items,
            "safety": self._safety(),
        }
        return self._safe(payload)

    def research_tasks(self) -> dict[str, Any]:
        daily = self.daily()
        items = []
        for item in daily["research_priorities"]["items"]:
            task = dict(item)
            task["task_status"] = self._task_status(task)
            task["task_type"] = "ResearchFirst" if task.get("missing_reasons") else "review"
            task["impact"] = "may block new action review" if task["task_status"] in {"pending", "blocked"} else "review only"
            task["status_rank"] = {"blocked": 0, "pending": 1, "review": 2, "complete": 3}.get(task["task_status"], 4)
            items.append(task)
        items.sort(key=lambda row: (row["status_rank"], -int(row.get("priority_score") or 0), str(row.get("code") or "")))
        payload = {
            "module": "assistant_research_tasks",
            "current_only": True,
            "generated_at": daily.get("generated_at"),
            "summary": {
                "task_count": len(items),
                "blocked_count": sum(1 for item in items if item["task_status"] == "blocked"),
                "pending_count": sum(1 for item in items if item["task_status"] == "pending"),
                "review_count": sum(1 for item in items if item["task_status"] == "review"),
                "complete_count": sum(1 for item in items if item["task_status"] == "complete"),
            },
            "items": items,
            "safety": self._safety(),
        }
        return self._safe(payload)

    def preference_simulation(self) -> dict[str, Any]:
        daily = self.daily()
        today = daily["today"]
        equity_min = self._float_or_none(today.get("equity_target_min_pct"))
        equity_max = self._float_or_none(today.get("equity_target_max_pct"))
        cash_min = self._float_or_none(today.get("cash_target_min_pct"))
        cash_max = self._float_or_none(today.get("cash_target_max_pct"))
        modes = [
            ("conservative", "保守", -5.0, 1.0, "lower equity preview and tighter drift tolerance"),
            ("balanced", "平衡", 0.0, 3.0, "current official target range preview"),
            ("aggressive", "进取", 5.0, 5.0, "higher equity preview and wider drift tolerance"),
        ]
        items = []
        for mode_id, label, shift, tolerance, why in modes:
            item = {
                "mode": mode_id,
                "label": label,
                "equity_min_pct": self._bounded_pct(equity_min, shift),
                "equity_max_pct": self._bounded_pct(equity_max, shift),
                "cash_min_pct": self._bounded_pct(cash_min, -shift),
                "cash_max_pct": self._bounded_pct(cash_max, -shift),
                "drift_tolerance_pp": tolerance,
                "official_output": False,
                "why": why,
                "next_step": "Use as read-only preference preview; do not replace official allocation.",
            }
            items.append(item)
        payload = {
            "module": "assistant_preference_simulation",
            "current_only": True,
            "generated_at": daily.get("generated_at"),
            "summary": {"mode_count": len(items), "official_mode": "balanced"},
            "items": items,
            "safety": self._safety(),
        }
        return self._safe(payload)

    def deep_scenarios(self) -> dict[str, Any]:
        daily = self.daily()
        scenario = daily["scenario_simulation"]
        risk_summary = daily["risk_heatmap"]["summary"]
        task_summary = self.research_tasks()["summary"]
        intraday_risk = next((item for item in daily["risk_heatmap"]["items"] if item.get("risk_id") == "intraday_rules"), {})
        items = []
        for row in scenario["items"]:
            review_flags = []
            if int(task_summary.get("blocked_count") or 0) or int(task_summary.get("pending_count") or 0):
                review_flags.append("research_tasks")
            if int(risk_summary.get("block_count") or 0) or int(risk_summary.get("warn_count") or 0):
                review_flags.append("risk_heatmap")
            if intraday_risk.get("severity") in {"warn", "block"}:
                review_flags.append("intraday_rules")
            items.append(
                {
                    **row,
                    "review_flags": review_flags,
                    "constraint_count": len(review_flags),
                    "constraint_level": "block" if "research_tasks" in review_flags else ("warn" if review_flags else "ok"),
                    "next_step": "Review risk center and research tasks before interpreting this scenario.",
                }
            )
        payload = {
            "module": "assistant_deep_scenarios",
            "current_only": True,
            "generated_at": daily.get("generated_at"),
            "summary": {
                "scenario_count": len(items),
                "current_score": scenario["summary"].get("current_score"),
                "scenario_with_constraints": sum(1 for item in items if item["constraint_count"]),
            },
            "items": items,
            "safety": self._safety(),
        }
        return self._safe(payload)

    def history_visuals_page(self) -> dict[str, Any]:
        daily = self.daily()
        metrics = HistoricalMetricsService(self.session).metrics()
        quality = HistoryWorkbenchService().quality()
        series = metrics.get("series") or {}
        items = [
            {
                "visual_id": "market_score_history",
                "label": "市场分数与权益区间",
                "status": self._history_visual_status(quality),
                "point_count": len(series.get("market_score") or []),
                "href": "/market/history",
                "why": "Observe market score and allocation range changes.",
            },
            {
                "visual_id": "bucket_gap_history",
                "label": "Bucket gap 趋势",
                "status": "watch" if (metrics.get("summary") or {}).get("red_gap_count") else "ok",
                "point_count": len(series.get("bucket_gap") or []),
                "href": "/history/gap-dashboard",
                "why": "Observe whether allocation drift is widening or narrowing.",
            },
            {
                "visual_id": "valuation_band_history",
                "label": "估值区间带",
                "status": self._history_visual_status(quality),
                "point_count": (quality.get("counts") or {}).get("research_runs", 0),
                "href": "/securities/688333.SH/valuation",
                "why": "Open a security valuation history page for band inspection.",
            },
            {
                "visual_id": "research_first_trend",
                "label": "ResearchFirst 阻塞趋势",
                "status": "watch" if daily["today"].get("research_first_count") else "ok",
                "point_count": daily["today"].get("research_first_count") or 0,
                "href": "/research-first",
                "why": "Track whether research blockers are cleared.",
            },
            {
                "visual_id": "decision_event_trend",
                "label": "决策事件趋势",
                "status": "ok",
                "point_count": (metrics.get("summary") or {}).get("decision_event_count", 0),
                "href": "/decision-timeline",
                "why": "Review decision events and logged reasons.",
            },
        ]
        payload = {
            "module": "assistant_history_visuals",
            "current_only": True,
            "generated_at": daily.get("generated_at"),
            "summary": {"visual_count": len(items), "history_db_ready": (quality.get("summary") or {}).get("db_ready", False)},
            "items": items,
            "safety": self._safety(),
        }
        return self._safe(payload)

    def review_score(self) -> dict[str, Any]:
        daily = self.daily()
        risk = daily["risk_heatmap"]["summary"]
        history_quality = HistoryWorkbenchService().quality()
        intraday_ok = not daily["today"].get("intraday_stale_flag") and not daily["today"].get("intraday_degraded_flag")
        items = [
            self._score_item("research_first_discipline", "ResearchFirst discipline", 100 if not daily["today"].get("research_first_count") else 70, "/research-first"),
            self._score_item("allocation_drift_control", "Allocation drift control", 100 - min(int(risk.get("block_count") or 0) * 20 + int(risk.get("warn_count") or 0) * 10, 60), "/buckets/drilldown"),
            self._score_item("intraday_freshness", "Intraday freshness", 100 if intraday_ok else 70, "/intraday-rules"),
            self._score_item("system_readiness", "System readiness", 100 if daily["today"].get("system_status") == "ok" else 60, "/system-checks"),
            self._score_item("history_readiness", "History readiness", 100 if self._history_quality_severity(history_quality) == "ok" else 70, "/history/quality"),
        ]
        total = round(sum(float(item["score"]) for item in items) / len(items), 2) if items else 0
        payload = {
            "module": "assistant_review_score",
            "current_only": True,
            "generated_at": daily.get("generated_at"),
            "summary": {"overall_score": total, "item_count": len(items), "grade": self._score_grade(total)},
            "items": items,
            "safety": self._safety(),
        }
        return self._safe(payload)

    def premarket_workflow(self) -> dict[str, Any]:
        daily = self.daily()
        steps = [
            self._workflow_step(1, "刷新 Web DB", "system", "/tools?group=系统与开发", "Use the whitelisted Web refresh tool."),
            self._workflow_step(2, "项目 current-only 检查", "system", "/tools?group=系统与开发", "Run the current-only validation tool."),
            self._workflow_step(3, "每日指挥台", "review", "/assistant", "Check daily status and next steps."),
            self._workflow_step(4, "风险预警中心", "risk", "/assistant/risk-center", "Resolve block and warn items first."),
            self._workflow_step(5, "研究任务闭环", "research", "/assistant/research-tasks", "Clear ResearchFirst blockers before new actions."),
            self._workflow_step(6, "操作计划", "trader", "/action-plan", "Review existing plan only after gates are clear."),
            self._workflow_step(7, "盘中规则", "trader", "/intraday-rules", "Confirm rule freshness and degraded flags."),
        ]
        payload = {
            "module": "assistant_premarket_workflow",
            "current_only": True,
            "generated_at": daily.get("generated_at"),
            "summary": {"step_count": len(steps), "blocked_risk_count": daily["risk_heatmap"]["summary"].get("block_count", 0)},
            "items": steps,
            "safety": self._safety(),
        }
        return self._safe(payload)

    def global_search(self, query: str = "") -> dict[str, Any]:
        q = (query or "").strip().lower()
        candidates = self._search_candidates()
        if q:
            items = [item for item in candidates if q in " ".join(str(value).lower() for value in item.values()).lower()]
        else:
            items = candidates[:20]
        payload = {
            "module": "assistant_global_search",
            "current_only": True,
            "query": query,
            "summary": {"result_count": len(items), "candidate_count": len(candidates)},
            "items": items[:50],
            "safety": self._safety(),
        }
        return self._safe(payload)

    def security_center(self, code: str) -> dict[str, Any]:
        normalized = str(code or "").strip().upper()
        statuses = SubjectStatusService(self.session).list_statuses().get("subjects") or []
        gaps = SubjectGapService(self.session).gap().get("rows") or []
        status = next((row for row in statuses if str(row.get("code") or "").upper() == normalized), {})
        gap = next((row for row in gaps if str(row.get("code") or "").upper() == normalized), {})
        history = HistoryWorkbenchService().security_history(normalized)
        task = self._security_task(status, gap)
        payload = {
            "module": "assistant_security_center",
            "current_only": True,
            "code": normalized,
            "summary": {
                "found": bool(status or gap or (history.get("summary") or {}).get("db_ready")),
                "research_first_status": status.get("research_first_status") or "unknown",
                "bucket": status.get("bucket") or gap.get("bucket"),
                "history_latest_generated_at": (history.get("summary") or {}).get("latest_generated_at"),
            },
            "current_status": {
                "code": status.get("code") or normalized,
                "name": status.get("name") or gap.get("name"),
                "subject_type": status.get("subject_type") or gap.get("subject_type"),
                "bucket": status.get("bucket") or gap.get("bucket"),
                "profile_status": status.get("profile_status") or "unknown",
                "valuation_status": status.get("valuation_status") or "unknown",
                "liquidity_status": status.get("liquidity_status") or "unknown",
                "research_first_status": status.get("research_first_status") or "unknown",
                "blocking_reason": status.get("blocking_reason"),
                "position_pct": gap.get("position_pct"),
                "bucket_gap_pct": gap.get("gap_pct"),
                "staleness_flag": bool(gap.get("staleness_flag")),
            },
            "task": task,
            "history_summary": history.get("summary") or {},
            "links": [
                {"label": "标的钻取", "href": f"/subjects/drilldown?subject={quote(normalized, safe='')}"},
                {"label": "标的历史", "href": f"/securities/{quote(normalized, safe='')}/history"},
                {"label": "估值历史", "href": f"/securities/{quote(normalized, safe='')}/valuation"},
                {"label": "研究任务", "href": "/assistant/research-tasks"},
            ],
            "safety": self._safety(),
        }
        return self._safe(payload)

    def weekly_safety(self) -> dict[str, Any]:
        daily = self.daily()
        risks = self.risk_center()
        tasks = self.research_tasks()
        score = self.review_score()
        history = self.history_visuals_page()
        next_week = []
        for risk in risks["items"]:
            if risk.get("severity") in {"block", "warn"}:
                next_week.append({"label": risk.get("label"), "href": risk.get("href"), "why": risk.get("next_step")})
        for task in tasks["items"][:5]:
            next_week.append({"label": f"{task.get('code')} {task.get('name') or ''}".strip(), "href": task.get("href"), "why": task.get("next_step")})
        payload = {
            "module": "assistant_weekly_safety",
            "current_only": True,
            "generated_at": daily.get("generated_at"),
            "summary": {
                "risk_block_count": risks["summary"].get("block_count", 0),
                "risk_warn_count": risks["summary"].get("warn_count", 0),
                "research_task_count": tasks["summary"].get("task_count", 0),
                "review_score": score["summary"].get("overall_score", 0),
                "history_visual_count": history["summary"].get("visual_count", 0),
            },
            "sections": [
                {"label": "风险预警", "href": "/assistant/risk-center", "count": risks["summary"].get("item_count", 0)},
                {"label": "研究任务", "href": "/assistant/research-tasks", "count": tasks["summary"].get("task_count", 0)},
                {"label": "复盘评分", "href": "/assistant/review-score", "score": score["summary"].get("overall_score", 0)},
                {"label": "历史可视化", "href": "/assistant/history-visuals", "count": history["summary"].get("visual_count", 0)},
            ],
            "next_week_priorities": next_week[:12],
            "safety": self._safety(),
        }
        return self._safe(payload)

    def feature_view(self, feature: str, *, query: str = "", code: str = "") -> dict[str, Any]:
        payload_by_feature = {
            "risk-center": self.risk_center,
            "research-tasks": self.research_tasks,
            "preferences": self.preference_simulation,
            "scenarios": self.deep_scenarios,
            "history-visuals": self.history_visuals_page,
            "review-score": self.review_score,
            "premarket": self.premarket_workflow,
            "weekly-safety": self.weekly_safety,
        }
        if feature == "search":
            payload = self.global_search(query)
        elif feature == "security-center":
            payload = self.security_center(code)
        else:
            payload = payload_by_feature[feature]()
        return self._feature_view(feature, payload, query=query, code=code)

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
    def _risk_impact(severity: str) -> str:
        if severity == "block":
            return "blocks new action review until resolved"
        if severity == "warn":
            return "needs review before daily execution"
        if severity == "watch":
            return "watch and confirm before relying on it"
        return "no immediate workflow impact"

    @staticmethod
    def _task_status(task: dict[str, Any]) -> str:
        if task.get("blocking_reason"):
            return "blocked"
        if task.get("missing_reasons"):
            return "pending"
        if task.get("staleness_flag") or abs(float(task.get("bucket_gap_pct") or 0)) > 1:
            return "review"
        return "complete"

    @staticmethod
    def _bounded_pct(value: float | None, shift: float) -> float | None:
        if value is None:
            return None
        return round(max(0.0, min(100.0, value + shift)), 4)

    @staticmethod
    def _history_visual_status(history_quality: dict[str, Any]) -> str:
        summary = history_quality.get("summary") or {}
        if not summary.get("db_ready"):
            return "watch"
        if summary.get("fail_count"):
            return "block"
        return "ok"

    @staticmethod
    def _score_item(score_id: str, label: str, score: float, href: str) -> dict[str, Any]:
        clipped = round(max(0.0, min(100.0, float(score))), 2)
        return {
            "score_id": score_id,
            "label": label,
            "score": clipped,
            "grade": DecisionAssistantService._score_grade(clipped),
            "href": href,
            "why": "Rule-alignment score based on current read-only facts.",
        }

    @staticmethod
    def _score_grade(score: float) -> str:
        if score >= 90:
            return "strong"
        if score >= 75:
            return "ok"
        if score >= 60:
            return "watch"
        return "weak"

    @staticmethod
    def _workflow_step(sequence: int, label: str, role: str, href: str, why: str) -> dict[str, Any]:
        return {
            "sequence": sequence,
            "label": label,
            "role": role,
            "status": "ready",
            "why": why,
            "next_step": "Open the linked page or whitelisted tool.",
            "href": href,
        }

    def _search_candidates(self) -> list[dict[str, Any]]:
        pages = [
            ("page", "每日指挥台", "/assistant", "daily command center"),
            ("page", "风险预警中心", "/assistant/risk-center", "risk center"),
            ("page", "研究任务闭环", "/assistant/research-tasks", "research task loop"),
            ("page", "偏好模拟", "/assistant/preferences", "preference preview"),
            ("page", "深度情景推演", "/assistant/scenarios", "scenario simulation"),
            ("page", "历史可视化", "/assistant/history-visuals", "history visuals"),
            ("page", "复盘评分", "/assistant/review-score", "review scoring"),
            ("page", "一键盘前流程", "/assistant/premarket", "premarket workflow"),
            ("page", "全局搜索", "/assistant/search", "global search"),
            ("page", "安全周报", "/assistant/weekly-safety", "weekly safety report"),
            ("page", "操作计划", "/action-plan", "action plan"),
            ("page", "理想仓位", "/target-allocation", "target allocation"),
            ("page", "ResearchFirst", "/research-first", "research first"),
            ("page", "盘中规则", "/intraday-rules", "intraday rules"),
        ]
        candidates = [{"kind": kind, "label": label, "href": href, "description": description} for kind, label, href, description in pages]
        try:
            tools = ToolConsoleService().list_tools().get("tools") or []
        except Exception:  # noqa: BLE001
            tools = []
        for tool in tools:
            candidates.append(
                {
                    "kind": "tool",
                    "label": tool.get("title") or tool.get("id"),
                    "href": f"/tools?group={quote(str(tool.get('group') or ''), safe='')}",
                    "description": tool.get("when_to_use") or tool.get("description") or "",
                }
            )
        for row in SubjectStatusService(self.session).list_statuses().get("subjects") or []:
            code = str(row.get("code") or "")
            candidates.append(
                {
                    "kind": "subject",
                    "label": f"{code} {row.get('name') or ''}".strip(),
                    "href": f"/assistant/securities/{quote(code, safe='')}",
                    "description": f"{row.get('bucket') or ''} {row.get('research_first_status') or ''}".strip(),
                }
            )
        for row in ThemeStatusService(self.session).status().get("themes") or []:
            theme = str(row.get("theme_name") or "")
            candidates.append(
                {
                    "kind": "theme",
                    "label": theme,
                    "href": "/themes",
                    "description": f"{row.get('status') or ''} {row.get('tactical_rating') or ''}".strip(),
                }
            )
        target_allocation = self.current.target_allocation() or {}
        for row in target_allocation.get("buckets", []):
            bucket = str(row.get("bucket") or "")
            candidates.append(
                {
                    "kind": "bucket",
                    "label": bucket,
                    "href": f"/buckets/drilldown?bucket={quote(bucket, safe='')}",
                    "description": f"gap {float(row.get('gap_pct') or 0):.2f}pp",
                }
            )
        return candidates

    def _security_task(self, status: dict[str, Any], gap: dict[str, Any]) -> dict[str, Any]:
        missing = self._missing_reasons(status)
        task = {
            "missing_reasons": missing,
            "position_pct": gap.get("position_pct"),
            "bucket_gap_pct": gap.get("gap_pct"),
            "staleness_flag": bool(gap.get("staleness_flag")),
            "blocking_reason": status.get("blocking_reason"),
        }
        task["priority_score"] = self._priority_score(status, gap, bool(missing))
        task["priority_level"] = self._priority_level(task["priority_score"])
        task["task_status"] = self._task_status(task)
        task["why"] = self._priority_why(status, gap, bool(missing))
        task["next_step"] = "Open research task loop if any gate is missing."
        return task

    @staticmethod
    def _feature_view(feature: str, payload: dict[str, Any], *, query: str = "", code: str = "") -> dict[str, Any]:
        titles = {
            "risk-center": "风险预警中心",
            "research-tasks": "研究任务闭环",
            "preferences": "偏好模拟",
            "scenarios": "深度情景推演",
            "history-visuals": "历史可视化",
            "review-score": "复盘评分",
            "premarket": "一键盘前流程",
            "search": "全局搜索",
            "security-center": "标的详情中心",
            "weekly-safety": "安全周报",
        }
        if feature == "security-center":
            title = f"标的详情中心 {code}"
        else:
            title = titles.get(feature, feature)
        summary = payload.get("summary") or {}
        cards = DecisionAssistantService._summary_cards(summary)
        table_items = payload.get("items") or payload.get("next_week_priorities") or []
        if feature == "security-center":
            table_items = [
                payload.get("current_status") or {},
                payload.get("task") or {},
                payload.get("history_summary") or {},
            ]
        if feature == "weekly-safety":
            table_items = payload.get("next_week_priorities") or []
        return {
            "feature": feature,
            "title": title,
            "query": query,
            "code": code,
            "summary_cards": cards,
            "items": table_items,
            "sections": payload.get("sections") or [],
            "links": payload.get("links") or [],
            "payload": payload,
            "safety": payload.get("safety") or {},
        }

    @staticmethod
    def _summary_cards(summary: dict[str, Any]) -> list[dict[str, Any]]:
        cards = []
        for key, value in summary.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                cards.append({"label": key, "value": value})
        return cards[:8]

    @staticmethod
    def item_columns(items: list[dict[str, Any]]) -> list[str]:
        columns: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            for key, value in item.items():
                if isinstance(value, (dict, list)):
                    continue
                if key not in columns:
                    columns.append(key)
        preferred = [
            "sequence",
            "kind",
            "category",
            "label",
            "code",
            "name",
            "bucket",
            "severity",
            "task_status",
            "priority_level",
            "priority_score",
            "score",
            "grade",
            "status",
            "href",
            "why",
            "next_step",
        ]
        selected = [key for key in preferred if key in columns]
        selected.extend(key for key in columns if key not in selected)
        return selected[:10]

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
