from __future__ import annotations

from fastapi import APIRouter

from ..services.history_workbench import HistoryWorkbenchService
from ..services.valuation_history import ValuationHistoryService
from .current import respond


router = APIRouter()


@router.get("/securities/{code}/valuation-history")
def security_valuation_history(code: str) -> dict:
    return respond(
        ValuationHistoryService().history(code),
        source={"path": "temp/history_db/myinvest_history.sqlite3", "view": "v_valuation_zone_drift"},
    )


@router.get("/securities/{code}/history")
def security_history(code: str) -> dict:
    return respond(
        HistoryWorkbenchService().security_history(code),
        source={"path": "temp/history_db/myinvest_history.sqlite3", "provider": "HistoryWorkbenchService"},
    )


@router.get("/market/history")
def market_history(limit: int = 100) -> dict:
    return respond(
        HistoryWorkbenchService().market_history(limit=limit),
        source={"path": "temp/history_db/myinvest_history.sqlite3", "view": "v_market_position_history"},
    )


@router.get("/positions/history")
def position_history(code: str | None = None, bucket: str | None = None, limit: int = 100) -> dict:
    return respond(
        HistoryWorkbenchService().position_history(code=code, bucket=bucket, limit=limit),
        source={"path": "temp/history_db/myinvest_history.sqlite3", "view": "v_position_slot_history"},
    )


@router.get("/actions/history")
def action_history(code: str | None = None, action_type: str | None = None, limit: int = 100) -> dict:
    return respond(
        HistoryWorkbenchService().action_history(code=code, action_type=action_type, limit=limit),
        source={"path": "temp/history_db/myinvest_history.sqlite3", "view": "v_action_history"},
    )


@router.get("/history/quality")
def history_quality() -> dict:
    return respond(
        HistoryWorkbenchService().quality(),
        source={"path": "temp/history_db/myinvest_history.sqlite3", "provider": "HistoryWorkbenchService"},
    )


@router.get("/history/coverage")
def history_coverage() -> dict:
    return respond(
        HistoryWorkbenchService().coverage(),
        source={"path": "temp/history_db/myinvest_history.sqlite3", "provider": "HistoryWorkbenchService"},
    )
