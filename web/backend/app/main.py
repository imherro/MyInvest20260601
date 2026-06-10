from __future__ import annotations

from urllib.parse import quote

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .config import STATIC_DIR, TEMPLATE_DIR
from .db import get_session
from .routers.current import router as current_router
from .services.allocation_drilldown import AllocationDrilldownService
from .services.current_state import CurrentStateService
from .services.dashboard import DashboardService
from .services.subject_gap import SubjectGapService
from .services.subject_status import SubjectStatusService
from .services.system_check import SystemCheckService
from .services.theme_status import ThemeStatusService


app = FastAPI(title="MyInvest Web", version="0.2.0")
app.include_router(current_router, prefix="/api")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


def page_context(request: Request, page: str, api_path: str, **extra):
    context = {"request": request, "page": page, "api_path": api_path}
    context.update(extra)
    return context


def service(session: Session) -> CurrentStateService:
    return CurrentStateService(session)


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


@app.get("/system-checks", response_class=HTMLResponse)
def system_checks_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "system_checks.html",
        page_context(request, "system-checks", "/api/system-check/current", checks=SystemCheckService(session).current()),
    )
