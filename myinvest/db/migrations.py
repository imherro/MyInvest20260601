"""Migration runner for the MyInvest history database."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .connection import ROOT, connect, resolve_db_path


MIGRATIONS_DIR = ROOT / "migrations"
BOOTSTRAP_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d_%H%M%S','now','localtime')),
  checksum TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class MigrationFile:
    version: str
    path: Path
    checksum: str


def migration_files() -> list[MigrationFile]:
    """List migration files in apply order."""

    files: list[MigrationFile] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        files.append(
            MigrationFile(
                version=path.stem,
                path=path,
                checksum=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    return files


def bootstrap_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(BOOTSTRAP_SQL)
    conn.commit()


def applied_migrations(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT version, checksum FROM schema_migrations").fetchall()
    return {str(row["version"]): str(row["checksum"]) for row in rows}


def assert_checksums(applied: dict[str, str], files: list[MigrationFile]) -> list[dict[str, str]]:
    mismatches: list[dict[str, str]] = []
    expected = {item.version: item.checksum for item in files}
    for version, checksum in applied.items():
        if version in expected and checksum != expected[version]:
            mismatches.append(
                {
                    "version": version,
                    "applied_checksum": checksum,
                    "file_checksum": expected[version],
                }
            )
    return mismatches


def check_migrations(db_path: str | Path | None = None) -> dict[str, Any]:
    """Check migration state without modifying the database."""

    path = resolve_db_path(db_path)
    files = migration_files()
    if not path.exists():
        return {
            "db": path.as_posix(),
            "status": "missing_database",
            "applied": [],
            "pending": [item.version for item in files],
            "mismatches": [],
        }

    conn = connect(path, create_parent=False)
    try:
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone()
        if not table_exists:
            applied: dict[str, str] = {}
        else:
            applied = applied_migrations(conn)
        mismatches = assert_checksums(applied, files)
        pending = [item.version for item in files if item.version not in applied]
        status = "ok" if not pending and not mismatches else "out_of_date"
        return {
            "db": path.as_posix(),
            "status": status,
            "applied": sorted(applied),
            "pending": pending,
            "mismatches": mismatches,
        }
    finally:
        conn.close()


def is_under_temp(path: Path) -> bool:
    try:
        path.resolve().relative_to((ROOT / "temp").resolve())
        return True
    except ValueError:
        return False


def reset_database(path: Path, *, allow_outside_temp: bool = False) -> list[str]:
    """Delete a SQLite database and sidecar files with a conservative path guard."""

    if not allow_outside_temp and not is_under_temp(path):
        raise ValueError("--reset is only allowed under temp/ without explicit confirmation")

    removed: list[str] = []
    for candidate in [path, Path(f"{path}-wal"), Path(f"{path}-shm")]:
        if candidate.exists():
            candidate.unlink()
            removed.append(candidate.as_posix())
    return removed


def apply_migrations(
    db_path: str | Path | None = None,
    *,
    reset: bool = False,
    allow_reset_outside_temp: bool = False,
) -> dict[str, Any]:
    """Apply pending migrations and return a JSON-serializable summary."""

    path = resolve_db_path(db_path)
    removed: list[str] = []
    if reset:
        removed = reset_database(path, allow_outside_temp=allow_reset_outside_temp)

    path.parent.mkdir(parents=True, exist_ok=True)
    files = migration_files()
    applied_now: list[str] = []
    skipped: list[str] = []

    conn = connect(path)
    try:
        bootstrap_schema(conn)
        applied = applied_migrations(conn)
        mismatches = assert_checksums(applied, files)
        if mismatches:
            raise ValueError(f"migration checksum mismatch: {mismatches}")

        for item in files:
            if item.version in applied:
                skipped.append(item.version)
                continue

            sql = item.path.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations(version, checksum) VALUES (?, ?)",
                (item.version, item.checksum),
            )
            conn.commit()
            applied_now.append(item.version)

        final_state = check_migrations(path)
        final_state.update(
            {
                "status": "ok" if final_state["status"] == "ok" else final_state["status"],
                "applied_now": applied_now,
                "skipped": skipped,
                "reset": reset,
                "removed": removed,
            }
        )
        return final_state
    finally:
        conn.close()
