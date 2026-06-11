from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy import Select, select, text
from sqlalchemy.orm import Session

from ..config import ROOT
from ..models.current_state import Artifact, CurrentModule


READ_ONLY_SQL = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
WRITE_SQL = re.compile(
    r"\b(ALTER|ATTACH|CREATE|DELETE|DETACH|DROP|INSERT|PRAGMA|REINDEX|REPLACE|UPDATE|VACUUM)\b",
    re.IGNORECASE,
)
SQL_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

ALLOWED_COUNT_TABLES = {
    "artifacts",
    "current_modules",
    "market_scores",
    "market_position_mappings",
    "subjects",
    "profiles",
    "valuations",
    "liquidity_gates",
    "portfolio_snapshots",
    "portfolio_positions",
    "target_allocations",
    "bucket_allocations",
    "action_plans",
    "action_items",
    "research_first_items",
    "intraday_rules",
    "intraday_bucket_rules",
    "decision_log_entries",
    "system_check_results",
}


class DatabaseService:
    """Read-only database facade for current Web state."""

    def __init__(self, session: Session):
        self.session = session

    def fetch_all(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self._assert_read_only_sql(sql)
        return [dict(row) for row in self.session.execute(text(sql), params or {}).mappings().all()]

    def fetch_one(self, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        self._assert_read_only_sql(sql)
        row = self.session.execute(text(sql), params or {}).mappings().first()
        return dict(row) if row else None

    def fetch_orm_all(self, statement: Select[Any]) -> list[dict[str, Any]]:
        return [dict(row) for row in self.session.execute(statement).mappings().all()]

    def fetch_orm_one(self, statement: Select[Any]) -> dict[str, Any] | None:
        row = self.session.execute(statement).mappings().first()
        return dict(row) if row else None

    def count_table(self, table: str) -> int:
        if table not in ALLOWED_COUNT_TABLES:
            raise ValueError(f"unsupported table: {table}")
        return int(self.session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one())

    def table_info(self, table: str) -> list[dict[str, Any]]:
        if not SQL_IDENTIFIER.fullmatch(table):
            raise ValueError(f"unsupported table identifier: {table}")
        return [dict(row) for row in self.session.execute(text(f'PRAGMA table_info("{table}")')).mappings().all()]

    def current_modules(self) -> list[dict[str, Any]]:
        statement = (
            select(
                CurrentModule.module,
                Artifact.path,
                Artifact.generated_at,
                Artifact.basis_trade_date,
                Artifact.sha256,
                Artifact.subject_code,
            )
            .join(Artifact, Artifact.id == CurrentModule.artifact_id)
            .order_by(CurrentModule.module)
        )
        return self.fetch_orm_all(statement)

    def source_for_module(self, module: str) -> dict[str, Any] | None:
        statement = (
            select(
                CurrentModule.module,
                Artifact.path,
                Artifact.generated_at,
                Artifact.basis_trade_date,
                Artifact.sha256,
            )
            .join(Artifact, Artifact.id == CurrentModule.artifact_id)
            .where(CurrentModule.module == module)
        )
        return self.fetch_orm_one(statement)

    def latest_index(self) -> dict[str, Any]:
        modules = self.current_modules()
        generated = [item["generated_at"] for item in modules if item.get("generated_at")]
        return {"generated_at": max(generated) if generated else None, "modules": modules}

    def current_artifact(self, module: str) -> dict[str, Any] | None:
        statement = (
            select(
                Artifact.module,
                Artifact.subject_code,
                Artifact.artifact_type,
                Artifact.path,
                Artifact.generated_at,
                Artifact.basis_trade_date,
                Artifact.sha256,
                Artifact.raw_json,
            )
            .join(CurrentModule, CurrentModule.artifact_id == Artifact.id)
            .where(CurrentModule.module == module)
        )
        return self.fetch_orm_one(statement)

    def current_artifact_payload(self, module: str, expected_key: str | None = None) -> dict[str, Any]:
        artifact = self.current_artifact(module)
        if not artifact:
            return {}
        raw_payload = self._loads_dict(artifact.get("raw_json"))
        if self._has_expected_payload(raw_payload, expected_key):
            return raw_payload
        path = artifact.get("path") or raw_payload.get("path")
        if not path:
            return {}
        return self._read_current_module_json(path)

    @staticmethod
    def _assert_read_only_sql(sql: str) -> None:
        if not READ_ONLY_SQL.search(sql) or WRITE_SQL.search(sql):
            raise ValueError("DatabaseService only allows read-only SELECT/WITH queries")

    @staticmethod
    def _loads_dict(value: Any) -> dict[str, Any]:
        if not value:
            return {}
        if isinstance(value, dict):
            return value
        try:
            data = json.loads(str(value))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _has_expected_payload(payload: dict[str, Any], expected_key: str | None) -> bool:
        if not payload:
            return False
        if expected_key is None:
            return True
        return isinstance(payload.get(expected_key), list)

    @staticmethod
    def _read_current_module_json(path: Any) -> dict[str, Any]:
        text_path = str(path or "").strip()
        if not text_path:
            return {}
        repo_path = Path(text_path)
        if repo_path.is_absolute() or ".." in repo_path.parts:
            return {}
        source_path = (ROOT / repo_path).resolve()
        if source_path != ROOT.resolve() and ROOT.resolve() not in source_path.parents:
            return {}
        try:
            data = json.loads(source_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}
