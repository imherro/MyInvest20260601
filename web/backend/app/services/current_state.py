from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from ..repositories.current_state import CurrentStateRepository
from .database import DatabaseService


class CurrentStateService:
    def __init__(self, session: Session):
        self.db = DatabaseService(session)
        self.repo = CurrentStateRepository(session)

    def current_modules(self) -> list[dict[str, Any]]:
        return self.db.current_modules()

    def source_for_module(self, module: str) -> dict[str, Any] | None:
        return self.db.source_for_module(module)

    def latest_index(self) -> dict[str, Any]:
        return self.db.latest_index()

    def market_score(self) -> dict[str, Any] | None:
        return self.repo.one(
            """
            SELECT score, state, basis_trade_date, generated_at, equity_min_pct, equity_max_pct,
                   cash_min_pct, cash_max_pct
            FROM market_scores
            ORDER BY id DESC
            LIMIT 1
            """
        )

    def market_position_mapping(self) -> list[dict[str, Any]]:
        return self.repo.all(
            """
            SELECT score_min, score_max, equity_min_pct, equity_max_pct, cash_min_pct,
                   cash_max_pct, label, is_active
            FROM market_position_mappings
            ORDER BY id
            """
        )

    def current_artifact(self, module: str) -> dict[str, Any] | None:
        return self.db.current_artifact(module)

    def current_artifact_payload(self, module: str, expected_key: str | None = None) -> dict[str, Any]:
        return self.db.current_artifact_payload(module, expected_key)

    def target_allocation(self) -> dict[str, Any] | None:
        target = self.repo.one(
            """
            SELECT id, generated_at, basis_trade_date, equity_min_pct, equity_max_pct,
                   cash_min_pct, cash_max_pct
            FROM target_allocations
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if not target:
            return None
        target["buckets"] = self.repo.all(
            """
            SELECT bucket, actual_pct, target_pct, gap_pct
            FROM bucket_allocations
            WHERE target_allocation_id = :id
            ORDER BY id
            """,
            {"id": target["id"]},
        )
        return target

    def portfolio(self) -> dict[str, Any] | None:
        snapshot = self.repo.one(
            """
            SELECT id, generated_at, basis_trade_date, equity_pct, cash_short_pct
            FROM portfolio_snapshots
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if not snapshot:
            return None
        snapshot["positions"] = self.repo.all(
            """
            SELECT s.code, s.name, pp.bucket, pp.position_pct, pp.reference_only_flag
            FROM portfolio_positions pp
            LEFT JOIN subjects s ON s.id = pp.subject_id
            WHERE pp.snapshot_id = :id
            ORDER BY pp.position_pct DESC
            """,
            {"id": snapshot["id"]},
        )
        return snapshot

    def intraday_rules(self) -> dict[str, Any] | None:
        rules = self.repo.one(
            """
            SELECT id, generated_at, basis_trade_date, status, stale_flag, degraded_flag, risk_mode, raw_json
            FROM intraday_rules
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if not rules:
            return None
        rules["buckets"] = self.repo.all(
            """
            SELECT bucket, actual_pct, target_pct, gap_pct
            FROM intraday_bucket_rules
            WHERE intraday_rules_id = :id
            ORDER BY id
            """,
            {"id": rules["id"]},
        )
        raw = self._load_json(rules.pop("raw_json", None))
        rules["disabled_triggers"] = raw.get("disabled_triggers", [])
        return rules

    @staticmethod
    def _load_json(value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            data = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def action_plan(self) -> dict[str, Any] | None:
        plan = self.repo.one(
            """
            SELECT id, generated_at, basis_trade_date, market_state, status
            FROM action_plans
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if not plan:
            return None
        plan["actions"] = self.repo.all(
            """
            SELECT ai.sequence, ai.action_type, ai.bucket, ai.current_position_pct,
                   ai.target_range_min_pct, ai.target_range_max_pct, ai.suggested_change_min_pp,
                   ai.suggested_change_max_pp, ai.reason, ai.requires_manual_confirmation,
                   s.code, s.name, s.subject_type
            FROM action_items ai
            LEFT JOIN subjects s ON s.id = ai.subject_id
            WHERE ai.action_plan_id = :id
            ORDER BY ai.sequence
            """,
            {"id": plan["id"]},
        )
        plan["research_first"] = self.research_first_items(plan["id"])
        return plan

    def research_first_items(self, action_plan_id: int | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        where = ""
        if action_plan_id is not None:
            where = "WHERE rfi.action_plan_id = :id"
            params["id"] = action_plan_id
        return self.repo.all(
            f"""
            SELECT s.code, s.name, s.subject_type, rfi.missing_profile, rfi.missing_valuation,
                   rfi.missing_liquidity, rfi.missing_theme_binding, rfi.allowed_conclusion,
                   rfi.blocking_reason
            FROM research_first_items rfi
            LEFT JOIN subjects s ON s.id = rfi.subject_id
            {where}
            ORDER BY rfi.id
            """,
            params,
        )

    def decision_log_entries(self, limit: int = 30) -> list[dict[str, Any]]:
        return self.repo.all(
            """
            SELECT entry_time, entry_type, summary, reason, ratio_only_text
            FROM decision_log_entries
            ORDER BY id DESC
            LIMIT :limit
            """,
            {"limit": limit},
        )

    def system_check_results(self) -> list[dict[str, Any]]:
        return self.repo.all(
            """
            SELECT check_name, status, message, generated_at
            FROM system_check_results
            ORDER BY id
            """
        )

    def table_counts(self) -> dict[str, int]:
        tables = [
            "artifacts",
            "current_modules",
            "market_scores",
            "market_position_mappings",
            "subjects",
            "profiles",
            "valuations",
            "liquidity_gates",
            "portfolio_snapshots",
            "portfolio_positions",
            "target_allocations",
            "bucket_allocations",
            "action_plans",
            "action_items",
            "research_first_items",
            "intraday_rules",
            "intraday_bucket_rules",
            "decision_log_entries",
            "system_check_results",
        ]
        return {table: self.db.count_table(table) for table in tables}
