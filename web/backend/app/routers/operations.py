from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..services.ratio_only import RatioOnlyService, RatioOnlyViolation
from ..services.tool_console import ToolConsoleService


router = APIRouter(prefix="/ops")


def respond(data: Any) -> dict[str, Any]:
    payload = {"ok": True, "data": data, "warnings": [], "errors": []}
    try:
        RatioOnlyService.assert_safe(payload)
    except RatioOnlyViolation as exc:
        raise HTTPException(status_code=500, detail="ratio-only sanitizer rejected response") from exc
    return payload


@router.get("/tools")
def tools() -> dict[str, Any]:
    return respond(ToolConsoleService().list_tools())


@router.post("/run/{tool_id}")
def run_tool(tool_id: str) -> dict[str, Any]:
    try:
        return respond(ToolConsoleService().run_tool(tool_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="tool not found") from exc
