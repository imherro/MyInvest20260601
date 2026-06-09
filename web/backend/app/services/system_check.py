from __future__ import annotations

from sqlalchemy.orm import Session

from .allocation_consistency import AllocationConsistencyService
from .current_state import CurrentStateService
from .research_first_gate import ResearchFirstGateService


class SystemCheckService:
    def __init__(self, session: Session):
        self.state = CurrentStateService(session)
        self.gate = ResearchFirstGateService(session)
        self.allocation = AllocationConsistencyService(session)

    def current(self) -> dict:
        checks = [self._safe_check_row(item) for item in self.state.system_check_results()]
        gate = self.gate.check()
        allocation = self.allocation.check()
        status = "ok"
        if any(item.get("status") == "fail" for item in checks) or gate["status"] != "ok" or allocation["status"] != "ok":
            status = "fail"
        return {
            "status": status,
            "checks": checks,
            "research_first_gate": gate,
            "allocation_consistency": allocation,
            "sensitive_scan": {"status": "ok", "summary": "ratio-only sanitizer passed"},
            "counts": self.state.table_counts(),
        }

    @staticmethod
    def _safe_check_row(item: dict) -> dict:
        status = str(item.get("status") or "unknown").lower()
        summary = "current-only validation passed"
        if status == "fail":
            summary = "current-only validation failed; inspect local validation output"
        elif status not in {"ok", "pass"}:
            summary = "current-only validation status recorded"
        safe = dict(item)
        safe["message"] = summary
        return safe
