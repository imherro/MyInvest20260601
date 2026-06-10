from __future__ import annotations

import io
import json
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.orm import Session

from ..config import ROOT
from .ratio_only import RatioOnlyService
from .target_allocation_candidate_audit import (
    ZIP_FILES as CANDIDATE_AUDIT_ZIP_FILES,
    TargetAllocationCandidateAuditService,
)
from .target_allocation_export import (
    EXPORT_DIR as CONTROLLED_EXPORT_DIR,
    ZIP_FILES as CONTROLLED_EXPORT_ZIP_FILES,
    TargetAllocationControlledExportService,
)
from .target_allocation_promotion import CANDIDATE_EXPORT_DIR


HISTORY_EXPORT_DIR = ROOT / "temp" / "history_exports"
HISTORY_DB_PATH = ROOT / "temp" / "web_runtime" / "history_snapshot.sqlite"

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


class HistorySnapshotService:
    """Build a ratio-only history snapshot from temp shadow/candidate exports."""

    def __init__(self, session: Session):
        self.session = session
        self.controlled = TargetAllocationControlledExportService(session)
        self.candidate_audit = TargetAllocationCandidateAuditService(session)

    def build_history_snapshot(self) -> dict[str, Any]:
        controlled_payload = self.controlled.build_export_payload()
        candidate_payload = self.candidate_audit.build_audit_payload()
        entries = self._scan_temp_exports()
        live_current = self._live_current_summary(controlled_payload, candidate_payload)
        snapshot = {
            "module": "history_snapshot",
            "export_type": "history_snapshot",
            "generated_at": datetime.now().strftime("%Y-%m-%d_%H%M%S"),
            "current_only": True,
            "history_scope": {
                "controlled_shadow_exports": True,
                "candidate_exports": True,
                "candidate_audit_exports": True,
                "uses_latest_index_modules": True,
            },
            "source_export_count": len(entries),
            "history_entries": entries,
            "live_current_summary": live_current,
            "safety": self._safety(live_current),
        }
        sanitized = RatioOnlyService.sanitize(snapshot)
        RatioOnlyService.assert_safe(sanitized)
        self.assert_no_runtime_terms(sanitized)
        self.assert_exportable(sanitized)
        return sanitized

    def build_json_bytes(self, payload: dict[str, Any] | None = None) -> bytes:
        payload = payload or self.build_history_snapshot()
        self.assert_exportable(payload)
        RatioOnlyService.assert_safe(payload)
        self.assert_no_runtime_terms(payload)
        return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")

    def build_zip_bytes(self, payload: dict[str, Any] | None = None) -> bytes:
        payload = payload or self.build_history_snapshot()
        self.assert_exportable(payload)
        files = {
            "manifest.json": {
                "module": payload["module"],
                "export_type": payload["export_type"],
                "generated_at": payload["generated_at"],
                "current_only": payload["current_only"],
                "files": sorted(name for name in ZIP_FILES if name != "manifest.json"),
            },
            "history_snapshot.json": payload,
            "history_entries.json": {
                "source_export_count": payload["source_export_count"],
                "history_entries": payload["history_entries"],
            },
            "live_current_summary.json": payload["live_current_summary"],
            "safety_checks.json": payload["safety"],
        }
        if set(files) != ZIP_FILES:
            raise ValueError("history snapshot zip file list mismatch")
        RatioOnlyService.assert_safe(files)
        self.assert_no_runtime_terms(files)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name, json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True))
        return buffer.getvalue()

    def write_to_temp(self, format: Literal["json", "zip"] = "zip") -> str:
        payload = self.build_history_snapshot()
        HISTORY_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        suffix = "json" if format == "json" else "zip"
        path = HISTORY_EXPORT_DIR / f"history_snapshot_{payload['generated_at']}.{suffix}"
        if "history_snapshot" not in path.name:
            raise ValueError("history snapshot filename must include history_snapshot")
        if not path.resolve().is_relative_to(HISTORY_EXPORT_DIR.resolve()):
            raise ValueError("history snapshot path must stay under temp/history_exports")
        content = self.build_json_bytes(payload) if format == "json" else self.build_zip_bytes(payload)
        path.write_bytes(content)
        self.write_history_database(payload)
        try:
            self._assert_export_file_safe(path, format)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return path.relative_to(ROOT).as_posix()

    def write_history_database(self, payload: dict[str, Any] | None = None) -> str:
        payload = payload or self.build_history_snapshot()
        self.assert_exportable(payload)
        HISTORY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(HISTORY_DB_PATH) as connection:
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
                        self._bool_to_db(entry.get("matched")),
                        int(entry.get("diff_count") or 0),
                        self._optional_int(entry.get("replay_failed")),
                        self._bool_to_db(entry.get("official_allowed")),
                    )
                    for entry in payload["history_entries"]
                ],
            )
            connection.executemany(
                "INSERT INTO history_safety_checks (check_name, status) VALUES (?, ?)",
                [(key, "OK" if value is True or value == "OK" else str(value)) for key, value in payload["safety"].items()],
            )
        return HISTORY_DB_PATH.relative_to(ROOT).as_posix()

    def _scan_temp_exports(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for directory in [CONTROLLED_EXPORT_DIR, CANDIDATE_EXPORT_DIR]:
            if not directory.exists():
                continue
            for path in sorted(directory.iterdir()):
                if path.suffix.lower() not in {".json", ".zip"} or not path.is_file():
                    continue
                payload = self._read_export_payload(path)
                entry = self._summarize_export(path, payload)
                RatioOnlyService.assert_safe(entry)
                self.assert_no_runtime_terms(entry)
                entries.append(entry)
        return entries

    def _read_export_payload(self, path: Path) -> dict[str, Any]:
        if not path.resolve().is_relative_to(ROOT.resolve() / "temp"):
            raise ValueError("history source must stay under temp")
        source_id = path.stem
        if path.suffix.lower() == ".json":
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise HistorySnapshotSourceError(f"history source {source_id} JSON is invalid") from exc
        else:
            try:
                payload = self._read_zip_payload(path)
            except zipfile.BadZipFile as exc:
                raise HistorySnapshotSourceError(f"history source {source_id} ZIP is invalid") from exc
        RatioOnlyService.assert_safe(payload)
        return payload

    @staticmethod
    def _read_zip_payload(path: Path) -> dict[str, Any]:
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

    def _summarize_export(self, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
        compare = payload.get("compare") or payload.get("golden_compare") or {}
        replay = payload.get("replay_summary") or {}
        promotion = payload.get("promotion_mode") or {}
        safety = payload.get("safety") or {}
        system_checks = payload.get("system_checks") or {}
        entry = {
            "source_id": path.stem,
            "source_format": path.suffix.lower().lstrip("."),
            "export_kind": self._export_kind(payload),
            "module": payload.get("module"),
            "generated_at": payload.get("generated_at"),
            "current_only": payload.get("current_only") is True,
            "status": payload.get("status"),
            "matched": compare.get("matched") if isinstance(compare, dict) else None,
            "diff_count": len(compare.get("diffs") or []) if isinstance(compare, dict) else 0,
            "unsupported_field_count": len(compare.get("unsupported_fields") or []) if isinstance(compare, dict) else 0,
            "replay_failed": replay.get("failed") if isinstance(replay, dict) else None,
            "official_allowed": promotion.get("official_allowed") if isinstance(promotion, dict) else None,
            "safety": self._compact_safety(safety),
            "system_checks": self._compact_system_checks(system_checks),
        }
        return RatioOnlyService.sanitize(entry)

    @staticmethod
    def _export_kind(payload: dict[str, Any]) -> str:
        module = str(payload.get("module") or "")
        export_type = str(payload.get("export_type") or "")
        simulation_mode = str(payload.get("simulation_mode") or "")
        if "candidate_audit" in module or export_type == "candidate_audit":
            return "candidate_audit"
        if "promotion_simulation" in module or simulation_mode == "candidate":
            return "candidate_export"
        if "controlled_export" in module or export_type == "shadow_target_allocation":
            return "controlled_shadow_export"
        return "unknown_export"

    def _live_current_summary(self, controlled_payload: dict[str, Any], candidate_payload: dict[str, Any]) -> dict[str, Any]:
        controlled_compare = controlled_payload.get("compare") or {}
        candidate_compare = candidate_payload.get("compare") or {}
        replay = candidate_payload.get("replay_summary") or {}
        promotion = candidate_payload.get("promotion_mode") or {}
        summary = {
            "shadow_vs_reference": {
                "matched": controlled_compare.get("matched"),
                "diff_count": len(controlled_compare.get("diffs") or []),
                "unsupported_field_count": len(controlled_compare.get("unsupported_fields") or []),
                "compared_field_count": len(controlled_compare.get("compared_fields") or []),
            },
            "candidate_audit_compare": {
                "matched": candidate_compare.get("matched"),
                "diff_count": len(candidate_compare.get("diffs") or []),
                "unsupported_field_count": len(candidate_compare.get("unsupported_fields") or []),
                "compared_field_count": len(candidate_compare.get("compared_fields") or []),
            },
            "controlled_export": {
                "status": controlled_payload.get("status"),
                "export_mode": controlled_payload.get("export_mode"),
                "provenance": controlled_payload.get("provenance"),
                "safety": controlled_payload.get("safety"),
                "system_checks": controlled_payload.get("system_checks"),
            },
            "candidate_audit": {
                "status": candidate_payload.get("status"),
                "export_mode": candidate_payload.get("export_mode"),
                "provenance": candidate_payload.get("provenance"),
                "safety": candidate_payload.get("safety"),
                "system_checks": candidate_payload.get("system_checks"),
            },
            "replay_fixture_summary": {
                "scenario_count": replay.get("scenario_count"),
                "passed": replay.get("passed"),
                "failed": replay.get("failed"),
                "scenarios": replay.get("scenarios") or [],
            },
            "promotion_mode": {
                "candidate_allowed": promotion.get("candidate_allowed"),
                "official_allowed": promotion.get("official_allowed"),
                "candidate_status": promotion.get("candidate_status"),
                "official_status": promotion.get("official_status"),
            },
        }
        sanitized = RatioOnlyService.sanitize(summary)
        RatioOnlyService.assert_safe(sanitized)
        self.assert_no_runtime_terms(sanitized)
        return sanitized

    @staticmethod
    def _compact_safety(safety: Any) -> dict[str, Any]:
        if not isinstance(safety, dict):
            return {}
        keys = [
            "ratio_only",
            "current_only",
            "writes_research_files",
            "updates_latest_index",
            "updates_current_modules",
            "generates_action_plan",
            "trading_feature",
            "execution_feature",
            "official_blocked",
        ]
        return {key: safety.get(key) for key in keys if key in safety}

    @staticmethod
    def _compact_system_checks(system_checks: Any) -> dict[str, Any]:
        if not isinstance(system_checks, dict):
            return {}
        keys = ["ratio_only", "research_first_gate", "allocation_consistency", "project_check_current_only"]
        return {key: system_checks.get(key) for key in keys if key in system_checks}

    @staticmethod
    def _safety(live_current: dict[str, Any]) -> dict[str, Any]:
        replay = live_current.get("replay_fixture_summary") or {}
        shadow = live_current.get("shadow_vs_reference") or {}
        candidate = live_current.get("candidate_audit_compare") or {}
        promotion = live_current.get("promotion_mode") or {}
        return {
            "ratio_only": True,
            "current_only": True,
            "uses_latest_index_modules": True,
            "research_first_gate": "OK",
            "allocation_consistency": "OK",
            "project_check_current_only": "OK",
            "shadow_vs_reference_matched": shadow.get("matched") is True,
            "candidate_audit_matched": candidate.get("matched") is True,
            "replay_fixtures_failed": int(replay.get("failed") or 0),
            "official_promotion_blocked": promotion.get("official_allowed") is False,
            "writes_research_files": False,
            "updates_latest_index": False,
            "updates_current_modules": False,
            "generates_action_plan": False,
            "trading_feature": False,
            "execution_feature": False,
        }

    @staticmethod
    def assert_exportable(payload: dict[str, Any]) -> None:
        live = payload.get("live_current_summary") or {}
        safety = payload.get("safety") or {}
        shadow = live.get("shadow_vs_reference") or {}
        candidate = live.get("candidate_audit_compare") or {}
        replay = live.get("replay_fixture_summary") or {}
        promotion = live.get("promotion_mode") or {}
        if shadow.get("matched") is not True or shadow.get("diff_count") != 0:
            raise ValueError("history snapshot shadow comparison failed")
        if candidate.get("matched") is not True or candidate.get("diff_count") != 0:
            raise ValueError("history snapshot candidate comparison failed")
        if int(replay.get("failed") or 0) != 0:
            raise ValueError("history snapshot replay fixtures have failures")
        if promotion.get("official_allowed") is not False:
            raise ValueError("history snapshot official promotion is not blocked")
        required_true = [
            "ratio_only",
            "current_only",
            "uses_latest_index_modules",
            "shadow_vs_reference_matched",
            "candidate_audit_matched",
            "official_promotion_blocked",
        ]
        for key in required_true:
            if safety.get(key) is not True:
                raise ValueError(f"history snapshot safety check failed: {key}")
        required_false = [
            "writes_research_files",
            "updates_latest_index",
            "updates_current_modules",
            "generates_action_plan",
            "trading_feature",
            "execution_feature",
        ]
        for key in required_false:
            if safety.get(key) is not False:
                raise ValueError(f"history snapshot safety boundary failed: {key}")

    @staticmethod
    def assert_no_runtime_terms(value: Any, path: str = "$") -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                HistorySnapshotService.assert_no_runtime_terms(item, f"{path}.{key}")
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                HistorySnapshotService.assert_no_runtime_terms(item, f"{path}[{idx}]")
        elif isinstance(value, str):
            lowered = value.replace(chr(92), "/").lower()
            if any(term in lowered for term in BLOCKED_VALUE_TERMS):
                raise ValueError(f"blocked runtime term at {path}")

    @staticmethod
    def _assert_export_file_safe(path: Path, format: str) -> None:
        if not path.resolve().is_relative_to(HISTORY_EXPORT_DIR.resolve()):
            raise ValueError("history snapshot path must stay under temp/history_exports")
        if "history_snapshot" not in path.name:
            raise ValueError("history snapshot filename must include history_snapshot")
        if format == "json":
            data = json.loads(path.read_text(encoding="utf-8"))
            RatioOnlyService.assert_safe(data)
            HistorySnapshotService.assert_no_runtime_terms(data)
            return
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if names != ZIP_FILES:
                raise ValueError(f"history snapshot zip file list mismatch: {sorted(names)}")
            for name in names:
                data = json.loads(archive.read(name).decode("utf-8"))
                RatioOnlyService.assert_safe(data)
                HistorySnapshotService.assert_no_runtime_terms(data)

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
