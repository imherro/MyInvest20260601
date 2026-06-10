from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..config import ROOT
from .ratio_only import RatioOnlyService
from .target_allocation_generation import BUCKET_FIELDS, BUCKET_ORDER, CORE_FIELDS, TargetAllocationGenerationService
from .target_allocation_mode import get_target_allocation_mode


CANDIDATE_EXPORT_DIR = ROOT / "temp" / "candidate_exports"
CANDIDATE_SOURCE = "db.TargetAllocationGenerationService.candidate_simulation"
SHADOW_SOURCE = TargetAllocationGenerationService.shadow_source


class TargetAllocationPromotionSimulationService:
    """Simulate promotion modes without changing current research state."""

    def __init__(self, session: Session):
        self.session = session
        self.generator = TargetAllocationGenerationService(session)

    def build_candidate_payload(self) -> dict[str, Any]:
        inputs = self._current_replay_inputs()
        candidate = TargetAllocationGenerationService.generate_shadow_from_inputs(
            market_score=inputs["market_score"],
            market_position_mapping=inputs["market_position_mapping"],
            actual_by_bucket=inputs["actual_by_bucket"],
            bucket_registry=inputs["bucket_registry"],
            scenario_name="current_candidate_promotion_simulation",
        )
        candidate = self._candidate_from_replay(candidate)
        shadow = self.generator.generate_shadow_current()
        compare = self._compare_candidate_to_shadow(candidate, shadow)
        payload = {
            "module": "target_allocation_promotion_simulation",
            "simulation_mode": "candidate",
            "generated_at": datetime.now().strftime("%Y-%m-%d_%H%M%S"),
            "current_only": True,
            "status": "candidate_ready_for_temp_export",
            "mode_status": get_target_allocation_mode("candidate").as_dict(),
            "target_allocation": candidate,
            "golden_compare": compare,
            "safety": self._safety(write_candidate_temp=True),
        }
        RatioOnlyService.assert_safe(payload)
        if not compare.get("matched") or compare.get("diffs"):
            raise ValueError("candidate target allocation differs from shadow baseline")
        return payload

    def write_candidate_to_temp(self) -> str:
        payload = self.build_candidate_payload()
        CANDIDATE_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path = CANDIDATE_EXPORT_DIR / f"target_allocation_candidate_export_{payload['generated_at']}.json"
        if "candidate" not in path.name:
            raise ValueError("candidate export filename must include candidate")
        if not path.resolve().is_relative_to(CANDIDATE_EXPORT_DIR.resolve()):
            raise ValueError("candidate export path must stay under temp/candidate_exports")
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            RatioOnlyService.assert_safe(data)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return path.relative_to(ROOT).as_posix()

    def build_official_block_report(self) -> dict[str, Any]:
        report = {
            "module": "target_allocation_promotion_simulation",
            "simulation_mode": "official",
            "current_only": True,
            "status": "blocked",
            "mode_status": get_target_allocation_mode("official").as_dict(),
            "reason": "official promotion is blocked in Phase 5F and cannot write current research state",
            "output_path": None,
            "safety": self._safety(write_candidate_temp=False),
        }
        RatioOnlyService.assert_safe(report)
        return report

    def build_mode_summary(self) -> dict[str, Any]:
        modes = ["reference", "shadow", "controlled_export", "candidate", "official", "unknown"]
        summary = {
            "module": "target_allocation_promotion_mode_summary",
            "current_only": True,
            "modes": [get_target_allocation_mode(mode).as_dict() for mode in modes],
        }
        RatioOnlyService.assert_safe(summary)
        return summary

    def _current_replay_inputs(self) -> dict[str, Any]:
        market = self.generator.market_position.get_current_market_position()
        portfolio = self.generator._current_portfolio()
        if not portfolio:
            raise LookupError("current portfolio snapshot is missing")
        inputs = {
            "market_score": {
                "score": market["score"],
                "state": market.get("market_score_state"),
                "basis_trade_date": market.get("basis_trade_date"),
            },
            "market_position_mapping": self.generator.market_position.get_active_mapping(),
            "actual_by_bucket": self.generator._actual_by_bucket(portfolio["snapshot_id"], portfolio["cash_short_pct"]),
            "bucket_registry": self._safe_bucket_registry(self.generator._current_source_json("bucket_registry") or {}),
        }
        RatioOnlyService.assert_safe(inputs)
        return inputs

    @staticmethod
    def _safe_bucket_registry(registry: dict[str, Any]) -> dict[str, Any]:
        buckets = registry.get("buckets") if isinstance(registry.get("buckets"), dict) else {}
        result = {
            "buckets": {
                key: {
                    "label": (item or {}).get("label"),
                    "color": (item or {}).get("color"),
                }
                for key, item in buckets.items()
                if isinstance(item, dict)
            }
        }
        RatioOnlyService.assert_safe(result)
        return result

    @staticmethod
    def _candidate_from_replay(replay: dict[str, Any]) -> dict[str, Any]:
        candidate = dict(replay)
        candidate["module"] = "target_allocation_candidate_simulation"
        candidate["mode"] = "candidate"
        candidate["source"] = CANDIDATE_SOURCE
        candidate["inputs"] = {
            "market_position": "db.market_position_mappings",
            "market_score": "db.market_scores",
            "portfolio": "db.portfolio_snapshots",
            "bucket_registry": "db.current_modules.bucket_registry",
        }
        candidate["constraints"] = [
            "candidate_simulation_only",
            "writes_temp_candidate_exports_only",
            "does_not_write_research_allocation",
            "does_not_replace_current_modules",
            "does_not_update_latest_index",
            "does_not_generate_action_plan",
        ]
        RatioOnlyService.assert_safe(candidate)
        return candidate

    @staticmethod
    def _compare_candidate_to_shadow(candidate: dict[str, Any], shadow: dict[str, Any]) -> dict[str, Any]:
        compared_fields: list[str] = []
        diffs: list[dict[str, Any]] = []
        for field in [*CORE_FIELDS, "market_state", "target_equity_pct", "target_cash_short_pct", "actual_equity_pct", "actual_cash_short_pct"]:
            TargetAllocationPromotionSimulationService._compare_value(
                candidate.get(field),
                shadow.get(field),
                field,
                compared_fields,
                diffs,
            )
        candidate_buckets = {item["key"]: item for item in candidate["buckets"]}
        shadow_buckets = {item["key"]: item for item in shadow["buckets"]}
        for bucket in BUCKET_ORDER:
            for field in BUCKET_FIELDS:
                TargetAllocationPromotionSimulationService._compare_value(
                    (candidate_buckets.get(bucket) or {}).get(field),
                    (shadow_buckets.get(bucket) or {}).get(field),
                    f"buckets.{bucket}.{field}",
                    compared_fields,
                    diffs,
                )
        report = {
            "matched": not diffs,
            "diffs": diffs,
            "compared_fields": compared_fields,
            "source_candidate": CANDIDATE_SOURCE,
            "source_shadow": SHADOW_SOURCE,
        }
        RatioOnlyService.assert_safe(report)
        return report

    @staticmethod
    def _compare_value(
        left: Any,
        right: Any,
        path: str,
        compared_fields: list[str],
        diffs: list[dict[str, Any]],
    ) -> None:
        compared_fields.append(path)
        try:
            matched = abs(float(left) - float(right)) <= 0.0001
        except (TypeError, ValueError):
            matched = left == right
        if not matched:
            diffs.append({"field": path, "candidate": left, "shadow": right})

    @staticmethod
    def _safety(*, write_candidate_temp: bool) -> dict[str, Any]:
        return {
            "ratio_only": True,
            "current_only": True,
            "writes_candidate_temp_export": write_candidate_temp,
            "writes_research_files": False,
            "updates_latest_index": False,
            "updates_current_modules": False,
            "generates_action_plan": False,
            "trading_feature": False,
            "execution_feature": False,
        }
