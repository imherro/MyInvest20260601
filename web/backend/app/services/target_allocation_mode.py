from __future__ import annotations

import os
from dataclasses import dataclass

from .ratio_only import RatioOnlyService


ENV_NAME = "MYINVEST_TARGET_ALLOCATION_MODE"
DEFAULT_MODE = "shadow"
ALLOWED_MODES = {"reference", "shadow", "controlled_export"}
BLOCKED_MODES = {"candidate", "official"}


@dataclass(frozen=True)
class TargetAllocationModeStatus:
    mode: str
    status: str
    reason: str
    source: str = ENV_NAME

    def as_dict(self) -> dict[str, str]:
        payload = {
            "mode": self.mode,
            "status": self.status,
            "reason": self.reason,
            "source": self.source,
        }
        RatioOnlyService.assert_safe(payload)
        return payload


def get_target_allocation_mode(value: str | None = None) -> TargetAllocationModeStatus:
    raw = value if value is not None else os.environ.get(ENV_NAME, DEFAULT_MODE)
    mode = str(raw or DEFAULT_MODE).strip().lower()
    if mode in ALLOWED_MODES:
        return TargetAllocationModeStatus(
            mode=mode,
            status="allowed",
            reason="mode is read-only or export-only and cannot write current research state",
        )
    if mode in BLOCKED_MODES:
        return TargetAllocationModeStatus(
            mode=mode,
            status="blocked",
            reason="promotion mode is design-only in this phase and cannot execute",
        )
    return TargetAllocationModeStatus(
        mode=mode,
        status="blocked",
        reason="unknown target allocation mode",
    )
