from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.orm import Session

from ..config import ROOT
from .current_state import CurrentStateService
from .ratio_only import RatioOnlyService
from .system_check import SystemCheckService
from .target_allocation_generation import TargetAllocationGenerationService


EXPORT_DIR = ROOT / "temp" / "web_exports"
ZIP_FILES = {
    "manifest.json",
    "shadow_target_allocation.json",
    "compare_result.json",
    "provenance.json",
    "system_checks.json",
}


class TargetAllocationControlledExportService:
    def __init__(self, session: Session):
        self.session = session
        self.current = CurrentStateService(session)
        self.shadow = TargetAllocationGenerationService(session)

    def build_export_payload(self) -> dict[str, Any]:
        shadow = self.shadow.generate_shadow_current()
        compare = self.shadow.compare_with_current_json()
        system_checks = self._system_check_summary()
        status = self._status(compare)
        payload = {
            "module": "target_allocation_shadow_controlled_export",
            "export_type": "shadow_target_allocation",
            "export_mode": "controlled_shadow",
            "generated_at": datetime.now().strftime("%Y-%m-%d_%H%M%S"),
            "basis_trade_date": shadow.get("basis_trade_date"),
            "current_only": True,
            "status": status,
            "shadow": shadow,
            "compare": compare,
            "provenance": self._provenance(compare),
            "safety": {
                "ratio_only": True,
                "research_first_unchanged": True,
                "writes_research_files": False,
                "updates_latest_index": False,
                "updates_current_modules": False,
                "generates_action_plan": False,
                "trading_feature": False,
                "execution_feature": False,
            },
            "system_checks": system_checks,
        }
        sanitized = RatioOnlyService.sanitize(payload)
        RatioOnlyService.assert_safe(sanitized)
        if not compare.get("matched") or compare.get("diffs"):
            raise ValueError("shadow target allocation differs from current reference")
        return sanitized

    def build_json_bytes(self, payload: dict[str, Any] | None = None) -> bytes:
        payload = payload or self.build_export_payload()
        RatioOnlyService.assert_safe(payload)
        return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")

    def build_zip_bytes(self, payload: dict[str, Any] | None = None) -> bytes:
        payload = payload or self.build_export_payload()
        files = {
            "manifest.json": {
                "module": payload["module"],
                "export_type": payload["export_type"],
                "export_mode": payload["export_mode"],
                "generated_at": payload["generated_at"],
                "current_only": payload["current_only"],
                "status": payload["status"],
                "files": sorted(name for name in ZIP_FILES if name != "manifest.json"),
            },
            "shadow_target_allocation.json": payload["shadow"],
            "compare_result.json": payload["compare"],
            "provenance.json": payload["provenance"],
            "system_checks.json": payload["system_checks"],
        }
        if set(files) != ZIP_FILES:
            raise ValueError("controlled export zip file list mismatch")
        RatioOnlyService.assert_safe(files)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name, json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True))
        return buffer.getvalue()

    def write_to_temp(self, format: Literal["json", "zip"] = "zip") -> str:
        payload = self.build_export_payload()
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        suffix = "json" if format == "json" else "zip"
        path = EXPORT_DIR / f"target_allocation_shadow_export_{payload['generated_at']}.{suffix}"
        content = self.build_json_bytes(payload) if format == "json" else self.build_zip_bytes(payload)
        path.write_bytes(content)
        try:
            self._assert_export_file_safe(path, format)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return path.relative_to(ROOT).as_posix()

    def _provenance(self, compare: dict[str, Any]) -> dict[str, Any]:
        modules = {
            "target_allocation": self.current.source_for_module("target_allocation"),
            "market_score": self.current.source_for_module("market_score"),
            "portfolio_snapshot": self.current.source_for_module("portfolio_snapshot"),
            "bucket_registry": self.current.source_for_module("bucket_registry"),
            "market_position_mapping": self.current.source_for_module("market_position_mapping"),
        }
        return {
            "latest_index_path": "research/latest_index.json",
            "target_allocation_reference_path": compare.get("source_reference"),
            "market_score_source": (modules["market_score"] or {}).get("path"),
            "portfolio_snapshot_source": (modules["portfolio_snapshot"] or {}).get("path"),
            "bucket_registry_source": (modules["bucket_registry"] or {}).get("path"),
            "market_position_mapping_source": (modules["market_position_mapping"] or {}).get("path"),
        }

    def _system_check_summary(self) -> dict[str, Any]:
        checks = SystemCheckService(self.session).current()
        project = next((item for item in checks.get("checks", []) if item.get("check_name") == "project_check_current_only"), {})
        return {
            "ratio_only": "OK",
            "research_first_gate": "OK" if (checks.get("research_first_gate") or {}).get("status") == "ok" else "FAIL",
            "allocation_consistency": "OK" if (checks.get("allocation_consistency") or {}).get("status") == "ok" else "FAIL",
            "project_check_current_only": "OK" if project.get("status") == "ok" else "FAIL",
        }

    @staticmethod
    def _status(compare: dict[str, Any]) -> str:
        if not compare.get("matched") or compare.get("diffs"):
            return "diffs_found"
        if compare.get("unsupported_fields"):
            return "unsupported_fields"
        return "matched"

    @staticmethod
    def _assert_export_file_safe(path: Path, format: str) -> None:
        if not path.resolve().is_relative_to(EXPORT_DIR.resolve()):
            raise ValueError("controlled export path must stay under temp/web_exports")
        if format == "json":
            data = json.loads(path.read_text(encoding="utf-8"))
            RatioOnlyService.assert_safe(data)
            return
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if names != ZIP_FILES:
                raise ValueError(f"zip file list mismatch: {sorted(names)}")
            for name in names:
                data = json.loads(archive.read(name).decode("utf-8"))
                RatioOnlyService.assert_safe(data)
