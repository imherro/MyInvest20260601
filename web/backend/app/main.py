from __future__ import annotations

from urllib.parse import quote, urlencode

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .config import STATIC_DIR, TEMPLATE_DIR
from .db import get_session
from .routers.current import router as current_router
from .routers.history import router as history_router
from .routers.operations import router as operations_router
from .services.allocation_drilldown import AllocationDrilldownService
from .services.audit_bundle_service import AuditBundleService
from .services.current_state import CurrentStateService
from .services.bucket_explorer import BucketExplorerService
from .services.dashboard import DashboardService
from .services.decision_timeline import DecisionTimelineService
from .services.environment_status import EnvironmentStatusService
from .services.history_gap_dashboard import HistoryGapDashboardService
from .services.history_workbench import HistoryWorkbenchService
from .services.historical_metrics import HistoricalMetricsService
from .services.subject_gap import SubjectGapService
from .services.subject_status import SubjectStatusService
from .services.system_check import SystemCheckService
from .services.theme_status import ThemeStatusService
from .services.tool_console import ToolConsoleService
from .services.user_preferences import UserPreferencesService
from .services.valuation_history import ValuationHistoryService
from .services.workbench_readiness import WorkbenchReadinessService


app = FastAPI(title="MyInvest Web", version="0.2.0")
app.include_router(current_router, prefix="/api")
app.include_router(history_router, prefix="/api")
app.include_router(operations_router)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


def page_context(request: Request, page: str, api_path: str, **extra):
    context = {
        "request": request,
        "page": page,
        "api_path": api_path,
        "subtitle": "Read-only current state from latest_index.modules.",
    }
    context.update(extra)
    return context


def service(session: Session) -> CurrentStateService:
    return CurrentStateService(session)


def query_api_path(base: str, params: dict[str, object]) -> str:
    clean = {key: value for key, value in params.items() if value not in (None, "")}
    return base + ("?" + urlencode(clean) if clean else "")


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    dashboard = DashboardService(session).current_dashboard()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        page_context(
            request,
            "dashboard",
            "/api/dashboard/current",
            dashboard=dashboard,
        ),
    )


@app.get("/settings", response_class=HTMLResponse)
@app.get("/environment", response_class=HTMLResponse)
def environment_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "environment.html",
        page_context(
            request,
            "environment",
            "/api/environment/status",
            environment=EnvironmentStatusService().status(),
        ),
    )


@app.get("/preferences", response_class=HTMLResponse)
def preferences_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "preferences.html",
        page_context(
            request,
            "preferences",
            "/api/user/preferences",
            preferences=UserPreferencesService(session).preferences(),
        ),
    )


@app.get("/audit", response_class=HTMLResponse)
def audit_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "audit.html",
        page_context(
            request,
            "audit",
            "/api/audit/bundle",
            audit_bundle=AuditBundleService(session).bundle(),
        ),
    )


@app.get("/readiness", response_class=HTMLResponse)
def readiness_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "readiness.html",
        page_context(
            request,
            "readiness",
            "/api/readiness/summary",
            readiness=WorkbenchReadinessService(session).summary(),
        ),
    )


@app.get("/action-plan", response_class=HTMLResponse)
def action_plan_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "action_plan.html",
        page_context(request, "action-plan", "/api/action-plan/current", action_plan=service(session).action_plan()),
    )


@app.get("/target-allocation", response_class=HTMLResponse)
def target_allocation_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "target_allocation.html",
        page_context(request, "target-allocation", "/api/target-allocation/current", target_allocation=service(session).target_allocation()),
    )


@app.get("/research-first", response_class=HTMLResponse)
def research_first_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "research_first.html",
        page_context(request, "research-first", "/api/research-first/current", items=service(session).research_first_items()),
    )


@app.get("/subjects", response_class=HTMLResponse)
def subjects_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    subject_status = SubjectStatusService(session).list_statuses()
    return templates.TemplateResponse(
        request,
        "subjects.html",
        page_context(
            request,
            "subjects",
            "/api/subjects/status",
            subjects=subject_status["subjects"],
            summary=subject_status["summary"],
        ),
    )


@app.get("/subjects/gap", response_class=HTMLResponse)
def subjects_gap_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    subject_gap = SubjectGapService(session).gap()
    return templates.TemplateResponse(
        request,
        "subjects_gap.html",
        page_context(
            request,
            "subjects-gap",
            "/api/subjects/gap",
            rows=subject_gap["rows"],
            summary=subject_gap["summary"],
        ),
    )


@app.get("/themes", response_class=HTMLResponse)
def themes_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    themes = ThemeStatusService(session).status()
    return templates.TemplateResponse(
        request,
        "themes.html",
        page_context(
            request,
            "themes",
            "/api/themes/status",
            themes=themes["themes"],
            summary=themes["summary"],
        ),
    )


@app.get("/history/gap-dashboard", response_class=HTMLResponse)
def history_gap_dashboard_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    dashboard = HistoryGapDashboardService(session).summary()
    return templates.TemplateResponse(
        request,
        "history_gap_dashboard.html",
        page_context(
            request,
            "history-gap-dashboard",
            "/api/history/gap-summary",
            dashboard=dashboard,
        ),
    )


@app.get("/buckets", response_class=HTMLResponse)
def buckets_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    buckets = BucketExplorerService(session).status()
    return templates.TemplateResponse(
        request,
        "buckets.html",
        page_context(
            request,
            "buckets",
            "/api/buckets/status",
            buckets=buckets["buckets"],
            summary=buckets["summary"],
        ),
    )


@app.get("/buckets/drilldown", response_class=HTMLResponse)
def buckets_drilldown_page(request: Request, bucket: str | None = None, session: Session = Depends(get_session)) -> HTMLResponse:
    drilldown = AllocationDrilldownService(session).buckets(bucket=bucket, detail="full")
    api_path = "/api/buckets/drilldown?detail=full"
    if bucket:
        api_path += "&bucket=" + quote(bucket, safe="")
    return templates.TemplateResponse(
        request,
        "buckets_drilldown.html",
        page_context(
            request,
            "buckets-drilldown",
            api_path,
            drilldown=drilldown,
        ),
    )


@app.get("/subjects/drilldown", response_class=HTMLResponse)
def subjects_drilldown_page(request: Request, subject: str | None = None, session: Session = Depends(get_session)) -> HTMLResponse:
    drilldown = AllocationDrilldownService(session).subjects(subject=subject, detail="full")
    api_path = "/api/subjects/drilldown?detail=full"
    if subject:
        api_path += "&subject=" + quote(subject, safe="")
    return templates.TemplateResponse(
        request,
        "subjects_drilldown.html",
        page_context(
            request,
            "subjects-drilldown",
            api_path,
            drilldown=drilldown,
        ),
    )


@app.get("/portfolio", response_class=HTMLResponse)
def portfolio_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "portfolio.html",
        page_context(request, "portfolio", "/api/portfolio/current", portfolio=service(session).portfolio()),
    )


@app.get("/intraday-rules", response_class=HTMLResponse)
def intraday_rules_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "intraday_rules.html",
        page_context(request, "intraday-rules", "/api/intraday-rules/current", intraday_rules=service(session).intraday_rules()),
    )


@app.get("/decision-log", response_class=HTMLResponse)
def decision_log_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "decision_log.html",
        page_context(request, "decision-log", "/api/decision-log/current", entries=service(session).decision_log_entries()),
    )


@app.get("/decision-timeline", response_class=HTMLResponse)
def decision_timeline_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    timeline = DecisionTimelineService(session).timeline()
    return templates.TemplateResponse(
        request,
        "decision_timeline.html",
        page_context(
            request,
            "decision-timeline",
            "/api/decision-timeline",
            timeline=timeline,
        ),
    )


@app.get("/historical-metrics", response_class=HTMLResponse)
def historical_metrics_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    metrics = HistoricalMetricsService(session).metrics()
    return templates.TemplateResponse(
        request,
        "historical_metrics.html",
        page_context(
            request,
            "historical-metrics",
            "/api/historical-metrics",
            metrics=metrics,
        ),
    )


@app.get("/history", response_class=HTMLResponse)
def history_workbench_page(request: Request) -> HTMLResponse:
    service = HistoryWorkbenchService()
    workbench = {
        "quality": service.quality(),
        "market": service.market_history(limit=5),
        "positions": service.position_history(limit=10),
        "actions": service.action_history(limit=10),
    }
    return templates.TemplateResponse(
        request,
        "history_workbench.html",
        page_context(
            request,
            "history-workbench",
            "/api/history/quality",
            subtitle="Read-only history workspace from temp/history_db.",
            workbench=workbench,
        ),
    )


@app.get("/market/history", response_class=HTMLResponse)
def market_history_page(request: Request, limit: int = 50) -> HTMLResponse:
    history = HistoryWorkbenchService().market_history(limit=limit)
    return templates.TemplateResponse(
        request,
        "market_history.html",
        page_context(
            request,
            "market-history",
            query_api_path("/api/market/history", {"limit": limit}),
            subtitle="Read-only market history from temp/history_db.",
            history=history,
        ),
    )


@app.get("/positions/history", response_class=HTMLResponse)
def position_history_page(request: Request, code: str | None = None, bucket: str | None = None, limit: int = 100) -> HTMLResponse:
    history = HistoryWorkbenchService().position_history(code=code, bucket=bucket, limit=limit)
    return templates.TemplateResponse(
        request,
        "position_history.html",
        page_context(
            request,
            "position-history",
            query_api_path("/api/positions/history", {"code": code, "bucket": bucket, "limit": limit}),
            subtitle="Read-only position history from temp/history_db.",
            history=history,
        ),
    )


@app.get("/actions/history", response_class=HTMLResponse)
def action_history_page(
    request: Request,
    code: str | None = None,
    action_type: str | None = None,
    limit: int = 100,
) -> HTMLResponse:
    history = HistoryWorkbenchService().action_history(code=code, action_type=action_type, limit=limit)
    return templates.TemplateResponse(
        request,
        "action_history.html",
        page_context(
            request,
            "action-history",
            query_api_path("/api/actions/history", {"code": code, "action_type": action_type, "limit": limit}),
            subtitle="Read-only action history from temp/history_db.",
            history=history,
        ),
    )


@app.get("/history/quality", response_class=HTMLResponse)
def history_quality_page(request: Request) -> HTMLResponse:
    quality = HistoryWorkbenchService().quality()
    return templates.TemplateResponse(
        request,
        "history_quality.html",
        page_context(
            request,
            "history-quality",
            "/api/history/quality",
            subtitle="History DB quality checks.",
            quality=quality,
        ),
    )


@app.get("/history/coverage", response_class=HTMLResponse)
def history_coverage_page(request: Request) -> HTMLResponse:
    coverage = HistoryWorkbenchService().coverage()
    return templates.TemplateResponse(
        request,
        "history_coverage.html",
        page_context(
            request,
            "history-coverage",
            "/api/history/coverage",
            subtitle="History DB artifact and normalized coverage.",
            coverage=coverage,
        ),
    )


@app.get("/securities/{code}/history", response_class=HTMLResponse)
def security_history_page(request: Request, code: str) -> HTMLResponse:
    history = HistoryWorkbenchService().security_history(code)
    return templates.TemplateResponse(
        request,
        "security_history.html",
        page_context(
            request,
            "security-history",
            f"/api/securities/{quote(code, safe='')}/history",
            subtitle="Read-only security history from temp/history_db.",
            history=history,
        ),
    )


@app.get("/securities/{code}/valuation", response_class=HTMLResponse)
def security_valuation_history_page(request: Request, code: str) -> HTMLResponse:
    history = ValuationHistoryService().history(code)
    return templates.TemplateResponse(
        request,
        "security_valuation_history.html",
        page_context(
            request,
            "valuation-history",
            f"/api/securities/{quote(code, safe='')}/valuation-history",
            subtitle="Read-only valuation history from temp/history_db.",
            history=history,
        ),
    )


@app.get("/tools", response_class=HTMLResponse)
def tools_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "tools.html",
        page_context(
            request,
            "tools",
            "/ops/tools",
            subtitle="Local whitelisted tools. Script buttons run only fixed repo commands.",
            tools=ToolConsoleService().list_tools(),
        ),
    )


@app.get("/system-checks", response_class=HTMLResponse)
def system_checks_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "system_checks.html",
        page_context(request, "system-checks", "/api/system-check/current", checks=SystemCheckService(session).current()),
    )
