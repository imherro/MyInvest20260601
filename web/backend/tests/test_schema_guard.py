from __future__ import annotations

from pathlib import Path
from typing import Any

from web.backend.app.db import SessionLocal
from web.backend.app.routers.current import respond
from web.backend.app.services.ratio_only import RatioOnlyService
from web.backend.app.services.schema_guard import EXPECTED_SCHEMA_NAME, EXPECTED_SCHEMA_VERSION, REQUIRED_SCHEMA
from web.backend.app.services.schema_guard import SchemaGuardService


ROOT = Path(__file__).resolve().parents[3]


class FakeSchemaGuardRepository:
    def __init__(
        self,
        *,
        tables: set[str] | None = None,
        columns: dict[str, set[str]] | None = None,
        version_record: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        fail: bool = False,
    ):
        self.tables = tables if tables is not None else set(REQUIRED_SCHEMA)
        self.columns = columns if columns is not None else {table: set(cols) for table, cols in REQUIRED_SCHEMA.items()}
        self.version_record = version_record
        self.metadata = metadata or {}
        self.fail = fail

    def list_tables(self) -> list[str]:
        if self.fail:
            raise RuntimeError("schema unavailable")
        return sorted(self.tables)

    def table_columns(self, table: str) -> list[str]:
        return sorted(self.columns.get(table, set()))

    def schema_version_record(self) -> dict[str, Any] | None:
        return self.version_record

    def schema_metadata(self) -> dict[str, Any]:
        return self.metadata


def test_schema_guard_current_db_missing_version_table_is_degraded(web_db):
    with SessionLocal() as session:
        payload = SchemaGuardService(session).status()

    assert payload["status"] == "degraded"
    assert payload["ok"] is True
    assert payload["schema_version_table_present"] is False
    assert payload["required_tables_present"] is True
    assert payload["required_columns_present"] is True
    assert payload["missing_required_tables"] == []
    assert payload["missing_required_columns"] == {}
    assert "missing_version_table" in payload["diagnostics_warnings"]
    RatioOnlyService.assert_safe(payload)


def test_schema_guard_missing_required_table_is_mismatch():
    repository = FakeSchemaGuardRepository(tables=set(REQUIRED_SCHEMA) - {"subjects"})

    payload = SchemaGuardService(session=None, repository=repository).status()  # type: ignore[arg-type]

    assert payload["status"] == "mismatch"
    assert payload["ok"] is False
    assert payload["required_tables_present"] is False
    assert payload["missing_required_tables"] == ["subjects"]


def test_schema_guard_missing_required_column_is_mismatch():
    columns = {table: set(cols) for table, cols in REQUIRED_SCHEMA.items()}
    columns["current_modules"] = {"module", "artifact_id"}
    repository = FakeSchemaGuardRepository(columns=columns)

    payload = SchemaGuardService(session=None, repository=repository).status()  # type: ignore[arg-type]

    assert payload["status"] == "mismatch"
    assert payload["ok"] is False
    assert payload["required_columns_present"] is False
    assert payload["missing_required_columns"] == {"current_modules": ["updated_at"]}


def test_schema_guard_version_match_is_ok():
    columns = {table: set(cols) for table, cols in REQUIRED_SCHEMA.items()}
    columns["schema_version"] = {"id", "schema_name", "schema_version", "schema_fingerprint", "created_at", "source"}
    repository = FakeSchemaGuardRepository(
        tables=set(REQUIRED_SCHEMA) | {"schema_version"},
        columns=columns,
        version_record={
            "schema_name": EXPECTED_SCHEMA_NAME,
            "schema_version": EXPECTED_SCHEMA_VERSION,
            "schema_fingerprint": "test-fingerprint",
            "created_at": "2026-06-11T00:00:00Z",
            "source": "web/docs/DATABASE_SCHEMA.md",
        },
    )

    payload = SchemaGuardService(session=None, repository=repository).status()  # type: ignore[arg-type]

    assert payload["status"] == "ok"
    assert payload["ok"] is True
    assert payload["observed_schema_name"] == EXPECTED_SCHEMA_NAME
    assert payload["observed_schema_version"] == EXPECTED_SCHEMA_VERSION
    assert payload["version_source"] == "schema_version"
    assert payload["diagnostics_warnings"] == []
    RatioOnlyService.assert_safe(payload)


def test_schema_guard_version_mismatch_is_mismatch():
    columns = {table: set(cols) for table, cols in REQUIRED_SCHEMA.items()}
    columns["schema_version"] = {"id", "schema_name", "schema_version", "schema_fingerprint", "created_at", "source"}
    repository = FakeSchemaGuardRepository(
        tables=set(REQUIRED_SCHEMA) | {"schema_version"},
        columns=columns,
        version_record={
            "schema_name": EXPECTED_SCHEMA_NAME,
            "schema_version": "web_read_model_future",
            "schema_fingerprint": "test-fingerprint",
            "created_at": "2026-06-11T00:00:00Z",
            "source": "web/docs/DATABASE_SCHEMA.md",
        },
    )

    payload = SchemaGuardService(session=None, repository=repository).status()  # type: ignore[arg-type]

    assert payload["status"] == "mismatch"
    assert payload["ok"] is False
    assert payload["observed_schema_version"] == "web_read_model_future"
    assert "schema_version_mismatch" in payload["diagnostics_warnings"]


def test_schema_guard_metadata_fallback_reads_only_safe_values():
    columns = {table: set(cols) for table, cols in REQUIRED_SCHEMA.items()}
    columns["schema_metadata"] = {"key", "value", "updated_at"}
    repository = FakeSchemaGuardRepository(
        tables=set(REQUIRED_SCHEMA) | {"schema_metadata"},
        columns=columns,
        metadata={
            "schema_name": EXPECTED_SCHEMA_NAME,
            "schema_version": EXPECTED_SCHEMA_VERSION,
        },
    )

    payload = SchemaGuardService(session=None, repository=repository).status()  # type: ignore[arg-type]

    assert payload["status"] == "ok"
    assert payload["schema_metadata_table_present"] is True
    assert payload["version_source"] == "schema_metadata"


def test_schema_guard_unavailable_status_is_safe():
    repository = FakeSchemaGuardRepository(fail=True)

    payload = SchemaGuardService(session=None, repository=repository).status()  # type: ignore[arg-type]

    assert payload["status"] == "unavailable"
    assert payload["ok"] is False
    assert payload["diagnostics_warnings"] == ["schema_introspection_unavailable"]
    RatioOnlyService.assert_safe(payload)


def test_schema_guard_api_get_is_safe(client):
    response = client.get("/api/diagnostics/schema")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    guard = payload["data"]["schema_guard"]
    assert guard["status"] in {"ok", "degraded", "mismatch", "unavailable"}
    assert guard["expected_schema_version"] == EXPECTED_SCHEMA_VERSION
    RatioOnlyService.assert_safe(payload)


def test_schema_guard_repository_has_no_direct_write_sql():
    source = (ROOT / "web" / "backend" / "app" / "repositories" / "schema_guard_repo.py").read_text(encoding="utf-8")

    assert "DatabaseService" in source
    assert ".fetch_all(" in source
    assert ".fetch_one(" in source
    assert ".table_info(" in source
    assert ".execute(" not in source
    for token in ["CREATE ", "INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "VACUUM", "REPLACE "]:
        assert token not in source


def test_schema_guard_payload_passes_api_wrapper_sanitizer():
    payload = {
        "schema_guard": SchemaGuardService(session=None, repository=FakeSchemaGuardRepository()).status()  # type: ignore[arg-type]
    }

    wrapped = respond(payload, source={"path": "db.SchemaGuardRepository"})

    assert wrapped["ok"] is True
    RatioOnlyService.assert_safe(wrapped)
