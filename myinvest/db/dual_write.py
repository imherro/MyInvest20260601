"""Shared helpers for optional generator dual-write into the history DB."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .ingest import ingest_artifacts


def ingest_generated_json(db_path: str | Path | None, paths: Iterable[Path]) -> dict[str, Any] | None:
    """Ingest generated JSON artifacts when a generator is called with --db."""

    if not db_path:
        return None
    json_paths = [Path(path) for path in paths]
    if not json_paths:
        return {
            "status": "ok",
            "planned_artifacts": 0,
            "privacy_blocked_raw_json": 0,
            "privacy_finding_count": 0,
            "modules": [],
        }
    return ingest_artifacts(db_path, json_paths)
