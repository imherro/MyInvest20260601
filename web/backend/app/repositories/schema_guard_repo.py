from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..services.database import DatabaseService


SCHEMA_VERSION_COLUMNS = [
    "id",
    "schema_name",
    "schema_version",
    "schema_fingerprint",
    "created_at",
    "source",
]
SCHEMA_METADATA_KEYS = {
    "schema_name",
    "schema_version",
    "schema_fingerprint",
    "schema_source",
}


class SchemaGuardRepository:
    def __init__(self, session: Session):
        self.db = DatabaseService(session)

    def list_tables(self) -> list[str]:
        rows = self.db.fetch_all(
            """
                SELECT name
                FROM sqlite_master
                WHERE type = :object_type
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """,
            {"object_type": "table"},
        )
        return [str(row.get("name")) for row in rows if row.get("name")]

    def table_columns(self, table: str) -> list[str]:
        rows = self.db.table_info(table)
        return [str(row.get("name")) for row in rows if row.get("name")]

    def schema_version_record(self) -> dict[str, Any] | None:
        columns = set(self.table_columns("schema_version"))
        selected = [column for column in SCHEMA_VERSION_COLUMNS if column in columns]
        if not selected:
            return None
        sql = f"SELECT {', '.join(selected)} FROM schema_version"
        if "id" in columns:
            sql = f"{sql} WHERE id = :schema_row_id LIMIT 1"
            return self.db.fetch_one(sql, {"schema_row_id": 1})
        return self.db.fetch_one(f"{sql} LIMIT 1")

    def schema_metadata(self) -> dict[str, Any]:
        columns = set(self.table_columns("schema_metadata"))
        if not {"key", "value"}.issubset(columns):
            return {}
        rows = self.db.fetch_all(
            """
                SELECT key, value
                FROM schema_metadata
                WHERE key IN ('schema_name', 'schema_version', 'schema_fingerprint', 'schema_source')
                """
        )
        return {
            str(row.get("key")): row.get("value")
            for row in rows
            if row.get("key") in SCHEMA_METADATA_KEYS
        }
