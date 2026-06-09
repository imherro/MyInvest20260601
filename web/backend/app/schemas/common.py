from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ApiResponse(BaseModel):
    ok: bool
    data: Any = None
    warnings: list[Any] = []
    errors: list[Any] = []
    source: dict[str, Any] | None = None
