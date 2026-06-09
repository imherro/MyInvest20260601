from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import DB_PATH
from ..db import get_session
from ..services.allocation_consistency import AllocationConsistencyService
from ..services.current_state import CurrentStateService
from ..services.ratio_only import RatioOnlyService, RatioOnlyViolation
from ..services.system_check import SystemCheckService


router = APIRouter()


def respond(data: Any, source: dict[str, Any] | None = None, warnings: list[Any] | None = None) -> dict[str, Any]:
    payload = {"ok": True, "data": data, "warnings": warnings or [], "errors": [], "source": source}
    try:
        RatioOnlyService.assert_safe(payload)
    except RatioOnlyViolation as exc:
        raise HTTPException(status_code=500, detail="ratio-only sanitizer rejected response") from exc
    return payload


@router.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": DB_PATH.exists(),
        "app": "MyInvest Web",
        "mode": "read-only",
        "current_only": True,
        "database": "temp/web_db/myinvest_web.sqlite",
    }


@router.get("/latest-index")
def latest_index(session: Session = Depends(get_session)) -> dict[str, Any]:
    service = CurrentStateService(session)
    return respond(service.latest_index(), source={"path": "research/latest_index.json"})


@router.get("/current")
def current(session: Session = Depends(get_session)) -> dict[str, Any]:
    service = CurrentStateService(session)
    return respond(
        {
            "latest_index": service.latest_index(),
            "market_score": service.market_score(),
            "action_plan": service.action_plan(),
            "target_allocation": service.target_allocation(),
            "portfolio": service.portfolio(),
            "intraday_rules": service.intraday_rules(),
        },
        source={"path": "research/latest_index.json"},
    )


@router.get("/action-plan/current")
def action_plan(session: Session = Depends(get_session)) -> dict[str, Any]:
    service = CurrentStateService(session)
    return respond({"action_plan": service.action_plan()}, source=service.source_for_module("action_plan"))


@router.get("/target-allocation/current")
def target_allocation(session: Session = Depends(get_session)) -> dict[str, Any]:
    service = CurrentStateService(session)
    return respond({"target_allocation": service.target_allocation()}, source=service.source_for_module("target_allocation"))


@router.get("/research-first/current")
def research_first(session: Session = Depends(get_session)) -> dict[str, Any]:
    service = CurrentStateService(session)
    return respond({"items": service.research_first_items()}, source=service.source_for_module("action_plan"))


@router.get("/portfolio/current")
def portfolio(session: Session = Depends(get_session)) -> dict[str, Any]:
    service = CurrentStateService(session)
    return respond({"portfolio": service.portfolio()}, source=service.source_for_module("portfolio_snapshot"))


@router.get("/intraday-rules/current")
def intraday_rules(session: Session = Depends(get_session)) -> dict[str, Any]:
    service = CurrentStateService(session)
    return respond({"intraday_rules": service.intraday_rules()}, source=service.source_for_module("intraday_rules"))


@router.get("/system-check/current")
def system_check(session: Session = Depends(get_session)) -> dict[str, Any]:
    return respond(SystemCheckService(session).current(), source={"path": "temp/web_db/myinvest_web.sqlite"})


@router.get("/decision-log/current")
def decision_log(session: Session = Depends(get_session)) -> dict[str, Any]:
    service = CurrentStateService(session)
    return respond({"entries": service.decision_log_entries()}, source={"path": "research/logs/decision_log.md"})


@router.get("/allocation-consistency/current")
def allocation_consistency(session: Session = Depends(get_session)) -> dict[str, Any]:
    service = CurrentStateService(session)
    return respond(AllocationConsistencyService(session).check(), source=service.source_for_module("intraday_rules"))
