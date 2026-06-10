from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.orm import Session

from ..config import ROOT
from .ratio_only import RatioOnlyService
from .system_check import SystemCheckService
from .target_allocation_generation import BUCKET_FIELDS, BUCKET_ORDER, CORE_FIELDS, TargetAllocationGenerationService
from .target_allocation_mode import get_target_allocation_mode
from .target_allocation_promotion import (
    CANDIDATE_EXPORT_DIR,
    CANDIDATE_SOURCE,
    SHADOW_SOURCE,
    TargetAllocationPromotionSimulationService,
)


FIXTURE_DIR = ROOT / "web" / "backend" / "tests" / "fixtures" / "target_allocation_scenarios"
ZIP_FILES = {
    "manifest.json",
    "candidate_target_allocation.json",
    "compare_result.json",
    "replay_summary.json",
    "promotion_mode.json",
    "safety_checks.json",
    "provenance.json",
}


class TargetAllocationCandidateAuditService:
    def __init__(self, session: Session):
        self.session = session
        self.generator = TargetAllocationGenerationService(session)
        self.promotion = TargetAllocationPromotionSimulationService(session)

    def build_audit_payload(self) -> dict[str, Any]:
        candidate_payload = self.promotion.build_candidate_payload()
        shadow_compare = self.generator.compare_with_current_json()
        replay_summary = self._replay_summary()
        promotion_mode = self._promotion_mode_summary()
        compare = self._compare_summary(candidate_payload["golden_compare"], shadow_compare)
        system_checks = self._system_check_summary()
        status = "matched"
        if not compare["matched"] or replay_summary["failed"] > 0 or promotion_mode["official_allowed"]:
            status = "blocked_by_safety"
        payload = {
            "module": "target_allocation_candidate_audit_bundle",
            "export_type": "candidate_audit",
            "export_mode": "candidate_simulation",
            "generated_at": datetime.now().strftime("%Y-%m-%d_%H%M%S"),
            "current_only": True,
            "status": status,
            "candidate": candidate_payload["target_allocation"],
            "reference": {
                "source": "latest_index.modules.target_allocation.path",
                "path": shadow_compare.get("source_reference"),
            },
            "compare": compare,
            "replay_summary": replay_summary,
            "promotion_mode": promotion_mode,
            "safety": self._safety(),
            "system_checks": system_checks,
            "provenance": self._provenance(shadow_compare),
        }
        sanitized = RatioOnlyService.sanitize(payload)
        RatioOnlyService.assert_safe(sanitized)
        return sanitized

    def build_json_bytes(self, payload: dict[str, Any] | None = None) -> bytes:
        payload = payload or self.build_audit_payload()
        self.assert_exportable(payload)
        RatioOnlyService.assert_safe(payload)
        return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")

    def build_zip_bytes(self, payload: dict[str, Any] | None = None) -> bytes:
        payload = payload or self.build_audit_payload()
        self.assert_exportable(payload)
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
            "candidate_target_allocation.json": payload["candidate"],
            "compare_result.json": payload["compare"],
            "replay_summary.json": payload["replay_summary"],
            "promotion_mode.json": payload["promotion_mode"],
            "safety_checks.json": {"safety": payload["safety"], "system_checks": payload["system_checks"]},
            "provenance.json": payload["provenance"],
        }
        if set(files) != ZIP_FILES:
            raise ValueError("candidate audit zip file list mismatch")
        RatioOnlyService.assert_safe(files)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name, json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True))
        return buffer.getvalue()

    def write_to_temp(self, format: Literal["json", "zip"] = "zip") -> str:
        payload = self.build_audit_payload()
        CANDIDATE_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        suffix = "json" if format == "json" else "zip"
        path = CANDIDATE_EXPORT_DIR / f"target_allocation_candidate_audit_{payload['generated_at']}.{suffix}"
        if "candidate_audit" not in path.name:
            raise ValueError("candidate audit filename must include candidate_audit")
        if not path.resolve().is_relative_to(CANDIDATE_EXPORT_DIR.resolve()):
            raise ValueError("candidate audit path must stay under temp/candidate_exports")
        content = self.build_json_bytes(payload) if format == "json" else self.build_zip_bytes(payload)
        path.write_bytes(content)
        try:
            self._assert_export_file_safe(path, format)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return path.relative_to(ROOT).as_posix()

    def _compare_summary(self, candidate_compare: dict[str, Any], shadow_compare: dict[str, Any]) -> dict[str, Any]:
        matched = bool(candidate_compare.get("matched")) and bool(shadow_compare.get("matched"))
        diffs = []
        if candidate_compare.get("diffs"):
            diffs.append({"source": "candidate_vs_shadow", "diffs": candidate_compare.get("diffs")})
        if shadow_compare.get("diffs"):
            diffs.append({"source": "shadow_vs_reference", "diffs": shadow_compare.get("diffs")})
        summary = {
            "matched": matched and not diffs,
            "diffs": diffs,
            "unsupported_fields": shadow_compare.get("unsupported_fields") or [],
            "compared_fields": sorted(set((candidate_compare.get("compared_fields") or []) + (shadow_compare.get("compared_fields") or []))),
            "candidate_vs_shadow": candidate_compare,
            "shadow_vs_reference": shadow_compare,
        }
        RatioOnlyService.assert_safe(summary)
        return summary

    def _replay_summary(self) -> dict[str, Any]:
        scenarios = []
        failed = 0
        for path in sorted(FIXTURE_DIR.glob("*.json")):
            scenario = json.loads(path.read_text(encoding="utf-8"))
            shadow = TargetAllocationGenerationService.generate_shadow_from_inputs(
                market_score=scenario["market_score"],
                market_position_mapping=scenario["market_position_mapping"],
                actual_by_bucket=scenario["portfolio_bucket_actual"],
                bucket_registry=scenario["bucket_registry"],
                scenario_name=scenario["name"],
            )
            diffs = self._fixture_diffs(shadow, scenario["expected"])
            if diffs:
                failed += 1
            scenarios.append(
                {
                    "name": scenario["name"],
                    "fixture": path.relative_to(ROOT).as_posix(),
                    "status": "failed" if diffs else "passed",
                    "diff_count": len(diffs),
                }
            )
        summary = {
            "scenario_count": len(scenarios),
            "passed": len(scenarios) - failed,
            "failed": failed,
            "scenarios": scenarios,
        }
        RatioOnlyService.assert_safe(summary)
        return summary

    def _fixture_diffs(self, actual: dict[str, Any], expected: dict[str, Any]) -> list[dict[str, Any]]:
        diffs: list[dict[str, Any]] = []
        for field in [
            *CORE_FIELDS,
            "market_state",
            "target_equity_pct",
            "target_cash_short_pct",
            "actual_equity_pct",
            "actual_cash_short_pct",
            "warnings",
        ]:
            self._compare_value(actual.get(field), expected.get(field), field, diffs)
        actual_buckets = {row["key"]: row for row in actual["buckets"]}
        expected_buckets = {row["key"]: row for row in expected["buckets"]}
        for bucket in BUCKET_ORDER:
            for field in BUCKET_FIELDS:
                self._compare_value(
                    (actual_buckets.get(bucket) or {}).get(field),
                    (expected_buckets.get(bucket) or {}).get(field),
                    f"buckets.{bucket}.{field}",
                    diffs,
                )
        RatioOnlyService.assert_safe(diffs)
        return diffs

    @staticmethod
    def _compare_value(left: Any, right: Any, path: str, diffs: list[dict[str, Any]]) -> None:
        try:
            matched = abs(float(left) - float(right)) <= 0.0001
        except (TypeError, ValueError):
            matched = left == right
        if not matched:
            diffs.append({"field": path, "candidate": left, "reference": right})

    def _promotion_mode_summary(self) -> dict[str, Any]:
        candidate = get_target_allocation_mode("candidate").as_dict()
        official = get_target_allocation_mode("official").as_dict()
        summary = {
            "candidate_allowed": candidate["status"] == "allowed",
            "official_allowed": official["status"] == "allowed",
            "candidate_status": "blocked_or_simulation_only" if candidate["status"] == "blocked" else candidate["status"],
            "official_status": official["status"],
            "candidate_mode": candidate,
            "official_mode": official,
        }
        RatioOnlyService.assert_safe(summary)
        return summary

    def _system_check_summary(self) -> dict[str, Any]:
        checks = SystemCheckService(self.session).current()
        project = next((item for item in checks.get("checks", []) if item.get("check_name") == "project_check_current_only"), {})
        summary = {
            "ratio_only": "OK",
            "research_first_gate": "OK" if (checks.get("research_first_gate") or {}).get("status") == "ok" else "FAIL",
            "allocation_consistency": "OK" if (checks.get("allocation_consistency") or {}).get("status") == "ok" else "FAIL",
            "project_check_current_only": "OK" if project.get("status") == "ok" else "FAIL",
        }
        RatioOnlyService.assert_safe(summary)
        return summary

    def _provenance(self, shadow_compare: dict[str, Any]) -> dict[str, Any]:
        provenance = {
            "latest_index_path": "research/latest_index.json",
            "current_resolver": "latest_index.modules",
            "target_allocation_reference_path": shadow_compare.get("source_reference"),
            "candidate_source": CANDIDATE_SOURCE,
            "shadow_source": SHADOW_SOURCE,
            "replay_fixture_dir": FIXTURE_DIR.relative_to(ROOT).as_posix(),
            "export_policy": "candidate audit temp export only; not current state",
        }
        RatioOnlyService.assert_safe(provenance)
        return provenance

    @staticmethod
    def _safety() -> dict[str, Any]:
        safety = {
            "ratio_only": True,
            "current_only": True,
            "writes_research_files": False,
            "updates_latest_index": False,
            "updates_current_modules": False,
            "generates_action_plan": False,
            "trading_feature": False,
            "execution_feature": False,
            "official_blocked": True,
        }
        RatioOnlyService.assert_safe(safety)
        return safety

    @staticmethod
    def assert_exportable(payload: dict[str, Any]) -> None:
        compare = payload.get("compare") or {}
        replay = payload.get("replay_summary") or {}
        promotion = payload.get("promotion_mode") or {}
        if payload.get("status") != "matched":
            raise ValueError("candidate audit payload is not matched")
        if compare.get("matched") is not True or compare.get("diffs"):
            raise ValueError("candidate audit compare failed")
        if compare.get("unsupported_fields"):
            raise ValueError("candidate audit has unsupported fields")
        if replay.get("failed") != 0:
            raise ValueError("candidate audit replay summary has failures")
        if promotion.get("official_allowed"):
            raise ValueError("official promotion is not blocked")

    @staticmethod
    def _assert_export_file_safe(path: Path, format: str) -> None:
        if not path.resolve().is_relative_to(CANDIDATE_EXPORT_DIR.resolve()):
            raise ValueError("candidate audit path must stay under temp/candidate_exports")
        if "candidate_audit" not in path.name:
            raise ValueError("candidate audit filename must include candidate_audit")
        if format == "json":
            data = json.loads(path.read_text(encoding="utf-8"))
            RatioOnlyService.assert_safe(data)
            return
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if names != ZIP_FILES:
                raise ValueError(f"candidate audit zip file list mismatch: {sorted(names)}")
            for name in names:
                data = json.loads(archive.read(name).decode("utf-8"))
                RatioOnlyService.assert_safe(data)
