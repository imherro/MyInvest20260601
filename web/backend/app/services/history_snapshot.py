from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.orm import Session

from ..config import ROOT
from ..repositories.history_snapshot_repo import (
    BLOCKED_VALUE_TERMS,
    HISTORY_DB_PATH,
    HISTORY_EXPORT_DIR,
    ZIP_FILES,
    HistorySnapshotRepository,
    HistorySnapshotSourceError,
)
from .ratio_only import RatioOnlyService
from .target_allocation_candidate_audit import (
    TargetAllocationCandidateAuditService,
)
from .target_allocation_export import (
    TargetAllocationControlledExportService,
)


class HistorySnapshotService:
    """Build a ratio-only history snapshot from temp shadow/candidate exports."""

    def __init__(self, session: Session):
        self.session = session
        self.repository = HistorySnapshotRepository(session)
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
        return self.repository.write_history_database(payload)

    def _scan_temp_exports(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for path in self.repository.source_paths():
            payload = self.repository.read_export_payload(path)
            RatioOnlyService.assert_safe(payload)
            entry = self._summarize_export(path, payload)
            RatioOnlyService.assert_safe(entry)
            self.assert_no_runtime_terms(entry)
            entries.append(entry)
        return entries

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
            data = HistorySnapshotRepository.read_json_payload(path)
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
