from __future__ import annotations

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .config import TEMPLATE_DIR
from .db import get_session
from .routers.current import router as current_router
from .services.current_state import CurrentStateService
from .services.system_check import SystemCheckService


app = FastAPI(title="MyInvest Web", version="0.2.0")
app.include_router(current_router, prefix="/api")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


def page_context(request: Request, page: str, **extra):
    context = {"request": request, "page": page}
    context.update(extra)
    return context


def service(session: Session) -> CurrentStateService:
    return CurrentStateService(session)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    current = service(session)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        page_context(
            request,
            "dashboard",
            modules=current.current_modules(),
            plan=current.action_plan(),
            target=current.target_allocation(),
            portfolio=current.portfolio(),
            market=current.market_score(),
            checks=SystemCheckService(session).current(),
        ),
    )


@app.get("/action-plan", response_class=HTMLResponse)
def action_plan_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "action_plan.html",
        page_context(request, "action-plan", action_plan=service(session).action_plan()),
    )


@app.get("/target-allocation", response_class=HTMLResponse)
def target_allocation_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "target_allocation.html",
        page_context(request, "target-allocation", target_allocation=service(session).target_allocation()),
    )


@app.get("/research-first", response_class=HTMLResponse)
def research_first_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "research_first.html",
        page_context(request, "research-first", items=service(session).research_first_items()),
    )


@app.get("/portfolio", response_class=HTMLResponse)
def portfolio_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "portfolio.html",
        page_context(request, "portfolio", portfolio=service(session).portfolio()),
    )


@app.get("/intraday-rules", response_class=HTMLResponse)
def intraday_rules_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "intraday_rules.html",
        page_context(request, "intraday-rules", intraday_rules=service(session).intraday_rules()),
    )


@app.get("/decision-log", response_class=HTMLResponse)
def decision_log_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "decision_log.html",
        page_context(request, "decision-log", entries=service(session).decision_log_entries()),
    )


@app.get("/system-checks", response_class=HTMLResponse)
def system_checks_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "system_checks.html",
        page_context(request, "system-checks", checks=SystemCheckService(session).current()),
    )
