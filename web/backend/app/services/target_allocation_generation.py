from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from .market_position import MarketPositionService
from .ratio_only import RatioOnlyService


BUCKET_ORDER = ["cash_short", "core_base", "attack_mainline", "defense", "legacy_watch"]
CORE_FIELDS = ["market_score", "equity_range", "cash_short_range"]
BUCKET_FIELDS = ["actual_pct", "target_pct", "gap_pct"]
ROOT = Path(__file__).resolve().parents[4]


class TargetAllocationGenerationService:
    shadow_source = "db.TargetAllocationGenerationService.shadow"

    def __init__(self, session: Session):
        self.session = session
        self.market_position = MarketPositionService(session)

    def generate_shadow_current(self) -> dict[str, Any]:
        market = self.market_position.get_current_market_position()
        registry = self._current_source_json("bucket_registry") or {}
        portfolio = self._current_portfolio()
        if not portfolio:
            raise LookupError("current portfolio snapshot is missing")

        equity_min = float(market["equity_min_pct"])
        equity_max = float(market["equity_max_pct"])
        cash_min = float(market["cash_min_pct"])
        cash_max = float(market["cash_max_pct"])
        equity_center = round((equity_min + equity_max) / 2, 2)
        cash_center = round((cash_min + cash_max) / 2, 2)
        segments = self._build_segments(equity_center, cash_center, registry)
        actual = self._actual_by_bucket(portfolio["snapshot_id"], portfolio["cash_short_pct"])
        buckets = self._build_buckets(segments, actual)

        result = {
            "module": "target_allocation_shadow",
            "mode": "shadow",
            "market_score": market["score"],
            "market_state": market["label"],
            "market_score_state": market.get("market_score_state"),
            "basis_trade_date": market.get("basis_trade_date"),
            "equity_range": {"min_pct": equity_min, "max_pct": equity_max, "center_pct": equity_center},
            "cash_short_range": {"min_pct": cash_min, "max_pct": cash_max, "center_pct": cash_center},
            "target_equity_pct": equity_center,
            "target_cash_short_pct": cash_center,
            "actual_equity_pct": round(sum(actual.get(key, 0.0) for key in ["core_base", "attack_mainline", "defense", "legacy_watch"]), 4),
            "actual_cash_short_pct": round(actual.get("cash_short", 0.0), 4),
            "segments": segments,
            "buckets": buckets,
            "unsupported_fields": [],
            "source": self.shadow_source,
            "inputs": {
                "market_position": "db.market_position_mappings",
                "market_score": "db.market_scores",
                "portfolio": "db.portfolio_snapshots",
                "bucket_registry": "db.current_modules.bucket_registry",
            },
            "constraints": [
                "shadow_only",
                "does_not_write_research_allocation",
                "does_not_replace_current_modules",
                "does_not_generate_action_plan",
            ],
        }
        RatioOnlyService.assert_safe(result)
        return result

    @classmethod
    def generate_shadow_from_inputs(
        cls,
        *,
        market_score: dict[str, Any],
        market_position_mapping: list[dict[str, Any]],
        actual_by_bucket: dict[str, Any],
        bucket_registry: dict[str, Any] | None = None,
        scenario_name: str | None = None,
        missing_bucket_policy: str = "zero",
    ) -> dict[str, Any]:
        """Build shadow allocation from explicit test inputs without reading current state."""

        position = cls._position_from_mapping(float(market_score["score"]), market_position_mapping)
        equity_min = float(position["equity_min_pct"])
        equity_max = float(position["equity_max_pct"])
        cash_min = float(position["cash_min_pct"])
        cash_max = float(position["cash_max_pct"])
        equity_center = round((equity_min + equity_max) / 2, 2)
        cash_center = round((cash_min + cash_max) / 2, 2)
        segments = cls._build_segments_from_registry(equity_center, cash_center, bucket_registry or {})
        actual, warnings = cls._normalize_actual_by_bucket(actual_by_bucket, missing_bucket_policy)
        buckets = cls._build_buckets_from_actual(segments, actual, "fixture.TargetAllocationGenerationService.shadow_replay")
        result = {
            "module": "target_allocation_shadow_replay",
            "mode": "shadow_replay",
            "scenario": scenario_name,
            "market_score": float(market_score["score"]),
            "market_state": position["label"],
            "market_score_state": market_score.get("state"),
            "basis_trade_date": market_score.get("basis_trade_date"),
            "equity_range": {"min_pct": equity_min, "max_pct": equity_max, "center_pct": equity_center},
            "cash_short_range": {"min_pct": cash_min, "max_pct": cash_max, "center_pct": cash_center},
            "target_equity_pct": equity_center,
            "target_cash_short_pct": cash_center,
            "actual_equity_pct": round(sum(actual.get(key, 0.0) for key in ["core_base", "attack_mainline", "defense", "legacy_watch"]), 4),
            "actual_cash_short_pct": round(actual.get("cash_short", 0.0), 4),
            "segments": segments,
            "buckets": buckets,
            "warnings": warnings,
            "unsupported_fields": [],
            "source": "fixture.TargetAllocationGenerationService.shadow_replay",
            "inputs": {
                "market_position": "fixture.market_position_mapping",
                "market_score": "fixture.market_score",
                "portfolio": "fixture.portfolio_bucket_actual",
                "bucket_registry": "fixture.bucket_registry",
            },
            "constraints": [
                "shadow_only",
                "fixture_only",
                "does_not_write_research_allocation",
                "does_not_replace_current_modules",
                "does_not_generate_action_plan",
            ],
        }
        RatioOnlyService.assert_safe(result)
        return result

    def compare_with_current_json(self) -> dict[str, Any]:
        shadow = self.generate_shadow_current()
        reference_artifact = self._current_artifact("target_allocation")
        if not reference_artifact:
            raise LookupError("current target allocation artifact is missing")
        reference = self._read_repo_json(reference_artifact["path"])
        compared_fields: list[str] = []
        diffs: list[dict[str, Any]] = []

        self._compare_value(shadow["market_score"], (reference.get("summary") or {}).get("market_position_score"), "market_score", compared_fields, diffs)
        reference_equity = self._parse_range((reference.get("summary") or {}).get("recommended_equity_range"))
        reference_cash = self._parse_range((reference.get("summary") or {}).get("recommended_bond_cash_range"))
        self._compare_range(shadow["equity_range"], reference_equity, "equity_range", compared_fields, diffs)
        self._compare_range(shadow["cash_short_range"], reference_cash, "cash_short_range", compared_fields, diffs)

        reference_buckets = {
            item.get("key"): item for item in ((reference.get("actual_allocation_overlay") or {}).get("buckets") or [])
        }
        shadow_buckets = {item["key"]: item for item in shadow["buckets"]}
        for bucket in BUCKET_ORDER:
            for field in BUCKET_FIELDS:
                self._compare_value(
                    (shadow_buckets.get(bucket) or {}).get(field),
                    (reference_buckets.get(bucket) or {}).get(field),
                    f"buckets.{bucket}.{field}",
                    compared_fields,
                    diffs,
                )

        result = {
            "matched": not diffs,
            "diffs": diffs,
            "compared_fields": compared_fields,
            "unsupported_fields": shadow["unsupported_fields"],
            "source_shadow": self.shadow_source,
            "source_reference": reference_artifact["path"],
        }
        RatioOnlyService.assert_safe(result)
        return result

    def get_shadow_summary(self) -> dict[str, Any]:
        shadow = self.generate_shadow_current()
        return {
            "mode": shadow["mode"],
            "market_score": shadow["market_score"],
            "market_state": shadow["market_state"],
            "equity_range": shadow["equity_range"],
            "cash_short_range": shadow["cash_short_range"],
            "buckets": shadow["buckets"],
            "unsupported_fields": shadow["unsupported_fields"],
            "source": shadow["source"],
        }

    def _build_segments(self, equity_center: float, cash_center: float, registry: dict[str, Any]) -> list[dict[str, Any]]:
        return self._build_segments_from_registry(equity_center, cash_center, registry)

    @staticmethod
    def _build_segments_from_registry(equity_center: float, cash_center: float, registry: dict[str, Any]) -> list[dict[str, Any]]:
        buckets = registry.get("buckets") if isinstance(registry.get("buckets"), dict) else {}
        targets = {
            "cash_short": round(cash_center, 2),
            "core_base": round(equity_center * 0.57, 2),
            "attack_mainline": round(equity_center * 0.14, 2),
            "legacy_watch": 0.0,
        }
        targets["defense"] = round(equity_center - targets["core_base"] - targets["attack_mainline"], 2)
        basis = {
            "cash_short": "Risk-off anchor from market-position mapping.",
            "core_base": "Keep core equity exposure, but do not add while total equity is above target.",
            "attack_mainline": "Pause new offensive exposure until market and theme gates recover.",
            "defense": "Defensive equity remains equity exposure and cannot replace cash/short-duration anchors.",
            "legacy_watch": "No ideal target; this bucket is a deviation cleanup candidate.",
        }
        return [
            {
                "key": key,
                "label": (buckets.get(key) or {}).get("label") or key,
                "color": (buckets.get(key) or {}).get("color"),
                "target_pct": targets[key],
                "basis": basis[key],
            }
            for key in BUCKET_ORDER
        ]

    def _build_buckets(self, segments: list[dict[str, Any]], actual: dict[str, float]) -> list[dict[str, Any]]:
        return self._build_buckets_from_actual(segments, actual, self.shadow_source)

    @staticmethod
    def _build_buckets_from_actual(segments: list[dict[str, Any]], actual: dict[str, float], source: str) -> list[dict[str, Any]]:
        rows = []
        for item in segments:
            key = item["key"]
            target = float(item["target_pct"])
            current = float(actual.get(key, 0.0))
            rows.append(
                {
                    "key": key,
                    "label": item["label"],
                    "color": item.get("color"),
                    "target_pct": round(target, 4),
                    "actual_pct": round(current, 4),
                    "gap_pct": round(current - target, 4),
                    "source": source,
                }
            )
        return rows

    @classmethod
    def _normalize_actual_by_bucket(cls, actual_by_bucket: dict[str, Any], missing_bucket_policy: str) -> tuple[dict[str, float], list[dict[str, str]]]:
        if missing_bucket_policy not in {"zero", "fail"}:
            raise ValueError("missing_bucket_policy must be zero or fail")
        actual: dict[str, float] = {}
        warnings: list[dict[str, str]] = []
        for key in BUCKET_ORDER:
            if key in actual_by_bucket:
                actual[key] = round(float(actual_by_bucket.get(key) or 0.0), 4)
                continue
            if missing_bucket_policy == "fail":
                raise ValueError(f"missing bucket actual for {key}")
            actual[key] = 0.0
            warnings.append(
                {
                    "code": "missing_bucket_actual",
                    "bucket": key,
                    "message": "bucket actual missing; treated as 0 pct",
                }
            )
        return actual, warnings

    @staticmethod
    def _position_from_mapping(score: float, mapping: list[dict[str, Any]]) -> dict[str, Any]:
        if not 0 <= score <= 100:
            raise ValueError("score must be between 0 and 100")
        for row in mapping:
            low = float(row["score_min"])
            high = float(row["score_max"])
            if low <= score <= high:
                equity_min, equity_max = TargetAllocationGenerationService._range_pair(
                    row,
                    "equity_min_pct",
                    "equity_max_pct",
                    "equity_allocation_range",
                )
                cash_min, cash_max = TargetAllocationGenerationService._range_pair(
                    row,
                    "cash_min_pct",
                    "cash_max_pct",
                    "bond_cash_allocation_range",
                )
                return {
                    "score_min": low,
                    "score_max": high,
                    "label": row.get("label") or row.get("market_state"),
                    "equity_min_pct": equity_min,
                    "equity_max_pct": equity_max,
                    "cash_min_pct": cash_min,
                    "cash_max_pct": cash_max,
                }
        raise ValueError(f"market position mapping not found for score={score:g}")

    @staticmethod
    def _range_pair(row: dict[str, Any], min_key: str, max_key: str, range_key: str) -> tuple[float, float]:
        if row.get(min_key) is not None and row.get(max_key) is not None:
            return float(row[min_key]), float(row[max_key])
        text_value = str(row.get(range_key) or "").replace("%", "")
        try:
            left, right = text_value.split("-", 1)
            return float(left), float(right)
        except ValueError as exc:
            raise ValueError(f"mapping range missing for {range_key}") from exc

    def _actual_by_bucket(self, snapshot_id: int, cash_short_pct: float | None) -> dict[str, float]:
        rows = self.session.execute(
            text(
                """
                SELECT bucket, SUM(position_pct) AS pct
                FROM portfolio_positions
                WHERE snapshot_id = :snapshot_id
                GROUP BY bucket
                """
            ),
            {"snapshot_id": snapshot_id},
        ).mappings()
        result = {key: 0.0 for key in BUCKET_ORDER}
        for row in rows:
            key = row.get("bucket") if row.get("bucket") in result else "legacy_watch"
            result[key] += float(row.get("pct") or 0)
        if cash_short_pct is not None:
            result["cash_short"] = float(cash_short_pct)
        return {key: round(value, 4) for key, value in result.items()}

    def _current_portfolio(self) -> dict[str, Any] | None:
        row = self.session.execute(
            text(
                """
                SELECT id AS snapshot_id, equity_pct, cash_short_pct, basis_trade_date, generated_at
                FROM portfolio_snapshots
                ORDER BY id DESC
                LIMIT 1
                """
            )
        ).mappings().first()
        return dict(row) if row else None

    def _current_artifact(self, module: str) -> dict[str, Any] | None:
        row = self.session.execute(
            text(
                """
                SELECT a.path, a.raw_json
                FROM current_modules cm
                JOIN artifacts a ON a.id = cm.artifact_id
                WHERE cm.module = :module
                """
            ),
            {"module": module},
        ).mappings().first()
        return dict(row) if row else None

    def _current_artifact_json(self, module: str) -> dict[str, Any] | None:
        artifact = self._current_artifact(module)
        return self._load_json(artifact.get("raw_json")) if artifact else None

    def _current_source_json(self, module: str) -> dict[str, Any] | None:
        artifact = self._current_artifact(module)
        if not artifact:
            return None
        return self._read_repo_json(artifact["path"])

    @staticmethod
    def _read_repo_json(path: str) -> dict[str, Any]:
        repo_path = ROOT / path
        try:
            data = json.loads(repo_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _load_json(value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            data = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _parse_range(value: Any) -> dict[str, float | None]:
        text_value = str(value or "").replace("%", "")
        try:
            left, right = text_value.split("-", 1)
            low = float(left)
            high = float(right)
        except ValueError:
            return {"min_pct": None, "max_pct": None, "center_pct": None}
        return {"min_pct": low, "max_pct": high, "center_pct": round((low + high) / 2, 2)}

    @classmethod
    def _compare_range(
        cls,
        actual: dict[str, Any],
        expected: dict[str, Any],
        path: str,
        compared_fields: list[str],
        diffs: list[dict[str, Any]],
    ) -> None:
        for field in ["min_pct", "max_pct", "center_pct"]:
            cls._compare_value(actual.get(field), expected.get(field), f"{path}.{field}", compared_fields, diffs)

    @staticmethod
    def _compare_value(
        actual: Any,
        expected: Any,
        path: str,
        compared_fields: list[str],
        diffs: list[dict[str, Any]],
    ) -> None:
        compared_fields.append(path)
        if actual is None or expected is None:
            if actual != expected:
                diffs.append({"field": path, "shadow": actual, "reference": expected})
            return
        try:
            matched = abs(float(actual) - float(expected)) <= 0.0001
        except (TypeError, ValueError):
            matched = actual == expected
        if not matched:
            diffs.append({"field": path, "shadow": actual, "reference": expected})
