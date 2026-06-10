from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..config import DB_PATH
from ..db import get_session
from ..services.allocation_drilldown import AllocationDrilldownService
from ..services.allocation_consistency import AllocationConsistencyService
from ..services.current_state import CurrentStateService
from ..services.dashboard import DashboardService
from ..services.export_package import ReviewPackageExportService
from ..services.history_snapshot import HistorySnapshotService
from ..services.market_position import MarketPositionService
from ..services.ratio_only import RatioOnlyService, RatioOnlyViolation
from ..services.research_first_gate import ResearchFirstGateService
from ..services.subject_gap import SubjectGapService
from ..services.subject_status import SubjectStatusService
from ..services.system_check import SystemCheckService
from ..services.target_allocation_candidate_audit import TargetAllocationCandidateAuditService
from ..services.target_allocation_export import TargetAllocationControlledExportService
from ..services.target_allocation_generation import TargetAllocationGenerationService
from ..services.theme_status import ThemeStatusService


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
        "database": "temp/web_db/myinvest.sqlite",
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
            "market_position": MarketPositionService(session).get_current_market_position(),
            "action_plan": service.action_plan(),
            "target_allocation": service.target_allocation(),
            "portfolio": service.portfolio(),
            "intraday_rules": service.intraday_rules(),
            "system_check": SystemCheckService(session).current(),
        },
        source={"path": "research/latest_index.json"},
    )


@router.get("/dashboard/current")
def dashboard_current(session: Session = Depends(get_session)) -> dict[str, Any]:
    return respond(DashboardService(session).current_dashboard(), source={"path": "db.DashboardService"})


@router.get("/modules/current")
def current_modules(session: Session = Depends(get_session)) -> dict[str, Any]:
    service = CurrentStateService(session)
    return respond({"modules": service.current_modules()}, source={"path": "research/latest_index.json"})


@router.get("/subjects/status")
def subject_statuses(session: Session = Depends(get_session)) -> dict[str, Any]:
    service = SubjectStatusService(session)
    return respond(service.list_statuses(), source={"path": "db.subjects"})


@router.get("/subjects/status/{code}")
def subject_status(code: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    service = SubjectStatusService(session)
    try:
        data = service.get_status(code)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="subject status not found") from exc
    return respond({"subject": data}, source={"path": "db.subjects"})


@router.get("/subjects/freshness")
def subject_freshness(session: Session = Depends(get_session)) -> dict[str, Any]:
    return respond(SubjectGapService(session).freshness(), source={"path": "db.subjects"})


@router.get("/subjects/gap")
def subject_gap(session: Session = Depends(get_session)) -> dict[str, Any]:
    return respond(SubjectGapService(session).gap(), source={"path": "db.subjects"})


@router.get("/themes/status")
def theme_statuses(session: Session = Depends(get_session)) -> dict[str, Any]:
    return respond(ThemeStatusService(session).status(), source={"path": "db.artifacts.theme_registry"})


@router.get("/themes/status/{theme_name}")
def theme_status(theme_name: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    try:
        data = ThemeStatusService(session).get_theme(theme_name)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="theme status not found") from exc
    return respond({"theme": data}, source={"path": "db.artifacts.theme_registry"})


@router.get("/buckets/drilldown")
def bucket_drilldown(
    bucket: str | None = None,
    detail: Literal["summary", "full"] = "summary",
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        data = AllocationDrilldownService(session).buckets(bucket=bucket, detail=detail)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="bucket drilldown not found") from exc
    return respond(data, source={"path": "db.AllocationDrilldownService"})


@router.get("/subjects/drilldown")
def subject_drilldown(
    subject: str | None = None,
    detail: Literal["summary", "full"] = "summary",
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        data = AllocationDrilldownService(session).subjects(subject=subject, detail=detail)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="subject drilldown not found") from exc
    return respond(data, source={"path": "db.AllocationDrilldownService"})


@router.get("/market-position/mapping")
def market_position_mapping(session: Session = Depends(get_session)) -> dict[str, Any]:
    service = MarketPositionService(session)
    return respond(
        {"mappings": service.get_active_mapping()},
        source={"path": MarketPositionService.source},
    )


@router.get("/market-position/current")
def current_market_position(session: Session = Depends(get_session)) -> dict[str, Any]:
    service = MarketPositionService(session)
    try:
        position = service.get_current_market_position()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="current market score is missing") from exc
    return respond({"market_position": position}, source={"path": MarketPositionService.source})


@router.get("/market-position/score/{score}")
def market_position_for_score(score: float, session: Session = Depends(get_session)) -> dict[str, Any]:
    service = MarketPositionService(session)
    try:
        position = service.get_position_for_score(score)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="market position mapping not found for score") from exc
    return respond({"market_position": position}, source={"path": MarketPositionService.source})


@router.get("/action-plan/current")
def action_plan(session: Session = Depends(get_session)) -> dict[str, Any]:
    service = CurrentStateService(session)
    return respond({"action_plan": service.action_plan()}, source=service.source_for_module("action_plan"))


@router.get("/target-allocation/current")
def target_allocation(session: Session = Depends(get_session)) -> dict[str, Any]:
    service = CurrentStateService(session)
    return respond({"target_allocation": service.target_allocation()}, source=service.source_for_module("target_allocation"))


@router.get("/target-allocation/shadow")
def target_allocation_shadow(session: Session = Depends(get_session)) -> dict[str, Any]:
    service = TargetAllocationGenerationService(session)
    return respond(
        {"target_allocation_shadow": service.get_shadow_summary()},
        source={"path": TargetAllocationGenerationService.shadow_source},
    )


@router.get("/target-allocation/shadow/compare")
def target_allocation_shadow_compare(session: Session = Depends(get_session)) -> dict[str, Any]:
    service = TargetAllocationGenerationService(session)
    return respond(
        {"comparison": service.compare_with_current_json()},
        source={"path": TargetAllocationGenerationService.shadow_source},
    )


@router.get("/target-allocation/shadow/export", response_model=None)
def target_allocation_shadow_export(
    format: Literal["zip", "json"] = "zip",
    session: Session = Depends(get_session),
) -> Any:
    service = TargetAllocationControlledExportService(session)
    payload = service.build_export_payload()
    if format == "json":
        return respond(payload, source={"path": "db.TargetAllocationControlledExportService"})
    content = service.build_zip_bytes(payload)
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="target_allocation_shadow_export.zip"'},
    )


@router.get("/target-allocation/candidate-audit", response_model=None)
def target_allocation_candidate_audit(
    format: Literal["json", "zip"] = "json",
    session: Session = Depends(get_session),
) -> Any:
    service = TargetAllocationCandidateAuditService(session)
    payload = service.build_audit_payload()
    if format == "json":
        return respond(payload, source={"path": "db.TargetAllocationCandidateAuditService"})
    content = service.build_zip_bytes(payload)
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="target_allocation_candidate_audit.zip"'},
    )


@router.get("/history/export", response_model=None)
def history_snapshot_export(
    format: Literal["json", "zip"] = "json",
    session: Session = Depends(get_session),
) -> Any:
    service = HistorySnapshotService(session)
    try:
        payload = service.build_history_snapshot()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="history snapshot source scan failed") from exc
    if format == "json":
        return respond(payload, source={"path": "db.HistorySnapshotService"})
    try:
        content = service.build_zip_bytes(payload)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="history snapshot export failed") from exc
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="history_snapshot.zip"'},
    )


@router.get("/research-first/current")
def research_first(session: Session = Depends(get_session)) -> dict[str, Any]:
    service = CurrentStateService(session)
    return respond(
        {"gate": ResearchFirstGateService(session).check(), "items": service.research_first_items()},
        source=service.source_for_module("action_plan"),
    )


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
    return respond(SystemCheckService(session).current(), source={"path": "temp/web_db/myinvest.sqlite"})


@router.get("/decision-log/current")
def decision_log(session: Session = Depends(get_session)) -> dict[str, Any]:
    service = CurrentStateService(session)
    return respond({"entries": service.decision_log_entries()}, source={"path": "research/logs/decision_log.md"})


@router.get("/allocation-consistency/current")
def allocation_consistency(session: Session = Depends(get_session)) -> dict[str, Any]:
    service = CurrentStateService(session)
    return respond(AllocationConsistencyService(session).check(), source=service.source_for_module("intraday_rules"))


@router.get("/export/review_package", response_model=None)
def export_review_package(
    format: Literal["zip", "json"] = "zip",
    session: Session = Depends(get_session),
) -> Any:
    service = ReviewPackageExportService(session)
    payload = service.payload()
    if format == "json":
        return respond(payload, source={"path": "research/latest_index.json"})
    content = service.zip_bytes(payload)
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="myinvest_current_review_package.zip"'},
    )
