from __future__ import annotations

import json
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..config import ROOT
from ..services.database import DatabaseService
from ..services.target_allocation_candidate_audit import ZIP_FILES as CANDIDATE_AUDIT_ZIP_FILES
from ..services.target_allocation_export import EXPORT_DIR as CONTROLLED_EXPORT_DIR
from ..services.target_allocation_export import ZIP_FILES as CONTROLLED_EXPORT_ZIP_FILES
from ..services.target_allocation_promotion import CANDIDATE_EXPORT_DIR


HISTORY_EXPORT_DIR = ROOT / "temp" / "history_exports"
HISTORY_RUNTIME_DIR = ROOT / "temp" / "web_runtime"
HISTORY_DB_PATH = HISTORY_RUNTIME_DIR / "history_snapshot.sqlite"

ZIP_FILES = {
    "manifest.json",
    "history_snapshot.json",
    "history_entries.json",
    "live_current_summary.json",
    "safety_checks.json",
}

BLOCKED_VALUE_TERMS = [
    ".env",
    "temp/",
    "web_runtime",
    ".sqlite",
    ".sqlite3",
    ".db",
    "__pycache__",
    ".pytest_cache",
    ".zip",
    ".log",
]


class HistorySnapshotSourceError(ValueError):
    pass


class HistorySnapshotRepository:
    """Safe file/runtime repository for ignored history snapshot artifacts."""

    def __init__(self, session: Session):
        self.db = DatabaseService(session)

    def source_paths(self) -> list[Path]:
        entries: list[Path] = []
        for directory in [CONTROLLED_EXPORT_DIR, CANDIDATE_EXPORT_DIR]:
            if not directory.exists():
                continue
            entries.extend(
                path
                for path in sorted(directory.iterdir())
                if path.suffix.lower() in {".json", ".zip"} and path.is_file()
            )
        return entries

    def read_export_payload(self, path: Path) -> dict[str, Any]:
        self._assert_temp_source(path)
        source_id = path.stem
        if path.suffix.lower() == ".json":
            try:
                return self.read_json_payload(path)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise HistorySnapshotSourceError(f"history source {source_id} JSON is invalid") from exc
        try:
            return self.read_zip_payload(path)
        except zipfile.BadZipFile as exc:
            raise HistorySnapshotSourceError(f"history source {source_id} ZIP is invalid") from exc

    @staticmethod
    def read_json_payload(path: Path) -> dict[str, Any]:
        return json.loads(path.read_bytes().decode("utf-8"))

    @staticmethod
    def read_zip_payload(path: Path) -> dict[str, Any]:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if names == CONTROLLED_EXPORT_ZIP_FILES:
                files = {name: json.loads(archive.read(name).decode("utf-8")) for name in names}
                manifest = files["manifest.json"]
                return {
                    "module": manifest.get("module"),
                    "export_type": manifest.get("export_type"),
                    "export_mode": manifest.get("export_mode"),
                    "generated_at": manifest.get("generated_at"),
                    "current_only": manifest.get("current_only"),
                    "status": manifest.get("status"),
                    "shadow": files.get("shadow_target_allocation.json"),
                    "compare": files.get("compare_result.json"),
                    "provenance": files.get("provenance.json"),
                    "system_checks": files.get("system_checks.json"),
                }
            if names == CANDIDATE_AUDIT_ZIP_FILES:
                files = {name: json.loads(archive.read(name).decode("utf-8")) for name in names}
                manifest = files["manifest.json"]
                safety = files.get("safety_checks.json") or {}
                return {
                    "module": manifest.get("module"),
                    "export_type": manifest.get("export_type"),
                    "export_mode": manifest.get("export_mode"),
                    "generated_at": manifest.get("generated_at"),
                    "current_only": manifest.get("current_only"),
                    "status": manifest.get("status"),
                    "candidate": files.get("candidate_target_allocation.json"),
                    "compare": files.get("compare_result.json"),
                    "replay_summary": files.get("replay_summary.json"),
                    "promotion_mode": files.get("promotion_mode.json"),
                    "safety": safety.get("safety"),
                    "system_checks": safety.get("system_checks"),
                    "provenance": files.get("provenance.json"),
                }
            raise ValueError(f"unsupported history export archive file list: {sorted(names)}")

    @staticmethod
    def write_history_database(payload: dict[str, Any]) -> str:
        HistorySnapshotRepository.assert_history_database_path()
        HISTORY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(HISTORY_DB_PATH)) as connection:
            connection.execute("DROP TABLE IF EXISTS history_snapshot_metadata")
            connection.execute("DROP TABLE IF EXISTS history_export_entries")
            connection.execute("DROP TABLE IF EXISTS history_safety_checks")
            connection.execute(
                """
                CREATE TABLE history_snapshot_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE history_export_entries (
                    source_id TEXT NOT NULL,
                    export_kind TEXT NOT NULL,
                    source_format TEXT NOT NULL,
                    generated_at TEXT,
                    status TEXT,
                    matched INTEGER,
                    diff_count INTEGER NOT NULL,
                    replay_failed INTEGER,
                    official_allowed INTEGER,
                    PRIMARY KEY (source_id, source_format)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE history_safety_checks (
                    check_name TEXT PRIMARY KEY,
                    status TEXT NOT NULL
                )
                """
            )
            connection.executemany(
                "INSERT INTO history_snapshot_metadata (key, value) VALUES (?, ?)",
                [
                    ("module", payload["module"]),
                    ("generated_at", payload["generated_at"]),
                    ("current_only", str(payload["current_only"])),
                    ("source_export_count", str(payload["source_export_count"])),
                ],
            )
            connection.executemany(
                """
                INSERT INTO history_export_entries (
                    source_id,
                    export_kind,
                    source_format,
                    generated_at,
                    status,
                    matched,
                    diff_count,
                    replay_failed,
                    official_allowed
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        entry["source_id"],
                        entry["export_kind"],
                        entry["source_format"],
                        entry.get("generated_at"),
                        entry.get("status"),
                        HistorySnapshotRepository._bool_to_db(entry.get("matched")),
                        int(entry.get("diff_count") or 0),
                        HistorySnapshotRepository._optional_int(entry.get("replay_failed")),
                        HistorySnapshotRepository._bool_to_db(entry.get("official_allowed")),
                    )
                    for entry in payload["history_entries"]
                ],
            )
            connection.executemany(
                "INSERT INTO history_safety_checks (check_name, status) VALUES (?, ?)",
                [(key, "OK" if value is True or value == "OK" else str(value)) for key, value in payload["safety"].items()],
            )
        return HISTORY_DB_PATH.relative_to(ROOT).as_posix()

    @staticmethod
    def runtime_summary() -> dict[str, Any]:
        HistorySnapshotRepository.assert_history_database_path()
        return {
            "available": HISTORY_DB_PATH.exists(),
            "history_entry_count": 0,
            "matched_entry_count": 0,
            "generated_at": None,
        }

    @staticmethod
    def assert_history_database_path(path: Path = HISTORY_DB_PATH) -> None:
        runtime_root = HISTORY_RUNTIME_DIR.resolve()
        resolved_path = path.resolve()
        if not resolved_path.is_relative_to(runtime_root):
            raise ValueError("history runtime database must stay under temp/web_runtime")
        if path.name != "history_snapshot.sqlite":
            raise ValueError("history runtime database filename must be history_snapshot.sqlite")
        if path.suffix != ".sqlite":
            raise ValueError("history runtime database must use .sqlite suffix")

    @staticmethod
    def _assert_temp_source(path: Path) -> None:
        if not path.resolve().is_relative_to(ROOT.resolve() / "temp"):
            raise ValueError("history source must stay under temp")

    @staticmethod
    def _bool_to_db(value: Any) -> int | None:
        if value is None:
            return None
        return 1 if value is True else 0

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None:
            return None
        return int(value)
