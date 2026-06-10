from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from ..config import ROOT
from .current_state import CurrentStateService
from .ratio_only import RatioOnlyService
from .subject_status import SubjectStatusService


ACTION_STATUSES = {"buy", "add", "reduce", "sell"}


class ThemeStatusService:
    def __init__(self, session: Session):
        self.current = CurrentStateService(session)
        self.subject_status = SubjectStatusService(session)

    def status(self) -> dict[str, Any]:
        theme_registry = self._module_payload("theme_registry")
        theme_leaders = self._module_payload("theme_leaders")
        etf_registry = self._module_payload("etf_registry")
        stock_registry = self._module_payload("stock_registry")
        subject_rows = self.subject_status.list_statuses().get("subjects") or []
        subjects = {row.get("code"): row for row in subject_rows}
        etfs = {row.get("code"): row for row in (etf_registry.get("etfs") or []) if row.get("code")}
        stocks = self._stock_maps(stock_registry.get("stocks") or [])

        themes = [
            self._theme_row(theme, theme_leaders, etfs, stocks, subjects)
            for theme in theme_registry.get("themes") or []
            if isinstance(theme, dict)
        ]
        payload = {
            "module": "theme_research_status",
            "current_only": True,
            "generated_at": self._generated_at(theme_registry, theme_leaders),
            "summary": self._summary(themes),
            "themes": themes,
            "safety": {"ratio_only": True, "current_only": True},
        }
        RatioOnlyService.assert_safe(payload)
        return RatioOnlyService.sanitize(payload)

    def get_theme(self, theme_name: str) -> dict[str, Any]:
        for theme in self.status().get("themes") or []:
            if theme.get("theme_name") == theme_name:
                return theme
        raise LookupError(theme_name)

    def _module_payload(self, module: str) -> dict[str, Any]:
        artifact = self.current.current_artifact(module)
        if not artifact:
            return {}
        raw_json = artifact.get("raw_json")
        metadata: dict[str, Any] = {}
        if raw_json:
            try:
                loaded = json.loads(raw_json)
            except json.JSONDecodeError:
                loaded = {}
            metadata = loaded if isinstance(loaded, dict) else {}
            if self._has_module_payload(module, metadata):
                return metadata
        path = artifact.get("path") or metadata.get("path")
        if not path:
            return {}
        source_path = (ROOT / str(path)).resolve()
        if ROOT.resolve() not in source_path.parents:
            return {}
        try:
            payload = json.loads(source_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _has_module_payload(module: str, payload: dict[str, Any]) -> bool:
        expected_keys = {
            "theme_registry": "themes",
            "theme_leaders": "themes",
            "etf_registry": "etfs",
            "stock_registry": "stocks",
        }
        key = expected_keys.get(module)
        return bool(key and isinstance(payload.get(key), list))

    def _theme_row(
        self,
        theme: dict[str, Any],
        theme_leaders: dict[str, Any],
        etfs: dict[str, dict[str, Any]],
        stocks: dict[str, dict[str, dict[str, Any]]],
        subjects: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        theme_name = str(theme.get("name") or "")
        leader_theme = self._leader_theme(theme_leaders, theme_name)
        associated_etfs = [self._associated_etf(code, etfs, subjects) for code in theme.get("related_etfs") or []]
        associated_stocks = [
            self._associated_stock(name, stocks, subjects)
            for name in theme.get("representative_stocks") or []
        ]
        leaders = self._leaders(theme_leaders, theme_name)
        conflicts = self._conflicts(theme, leader_theme)
        data_quality_status = "fresh" if theme else "missing"
        status = self._status(theme, leader_theme, data_quality_status, conflicts)
        payload = {
            "theme_name": theme_name,
            "strategic_rating": theme.get("strategic_rating") or theme.get("rating") or leader_theme.get("strategic_rating"),
            "tactical_rating": theme.get("tactical_rating") or leader_theme.get("tactical_rating"),
            "stage": theme.get("stage") or theme.get("current_a_share_trading_stage") or leader_theme.get("stage"),
            "status": status,
            "basis_trade_date": theme.get("data_basis"),
            "generated_at": theme.get("updated_at") or theme_leaders.get("generated_at"),
            "associated_etfs": associated_etfs,
            "associated_stocks": associated_stocks,
            "leaders": leaders,
            "conflicts": conflicts,
            "data_quality_status": data_quality_status,
        }
        return RatioOnlyService.sanitize(payload)

    @staticmethod
    def _associated_etf(code: Any, etfs: dict[str, dict[str, Any]], subjects: dict[str, dict[str, Any]]) -> dict[str, Any]:
        code_text = str(code or "")
        registry = etfs.get(code_text) or {}
        subject = subjects.get(code_text) or {}
        return {
            "code": code_text,
            "name": subject.get("name") or registry.get("name"),
            "profile_status": subject.get("profile_status") or ThemeStatusService._profile_status(registry),
            "valuation_status": subject.get("valuation_status") or "unknown",
            "liquidity_status": subject.get("liquidity_status") or "unknown",
            "gate_conclusion": ThemeStatusService._safe_gate(subject.get("gate_conclusion") or registry.get("action_rating") or "watch"),
        }

    @staticmethod
    def _associated_stock(name: Any, stocks: dict[str, dict[str, dict[str, Any]]], subjects: dict[str, dict[str, Any]]) -> dict[str, Any]:
        name_text = str(name or "")
        registry = stocks["by_name"].get(name_text) or stocks["by_code"].get(name_text) or {}
        code = registry.get("code")
        subject = (subjects.get(code) or {}) if code else {}
        return {
            "code": code,
            "name": subject.get("name") or registry.get("name") or name_text,
            "profile_status": subject.get("profile_status") or ThemeStatusService._profile_status(registry),
            "valuation_status": subject.get("valuation_status") or "unknown",
            "liquidity_status": subject.get("liquidity_status") or "unknown",
            "gate_conclusion": ThemeStatusService._safe_gate(subject.get("gate_conclusion") or registry.get("action_rating") or "watch"),
        }

    @staticmethod
    def _profile_status(row: dict[str, Any]) -> str:
        return "pass" if row.get("status") == "profile_generated" else "missing"

    @staticmethod
    def _safe_gate(value: Any) -> str:
        candidate = str(value or "unknown").strip().lower()
        return "watch" if candidate in ACTION_STATUSES else (candidate or "unknown")

    @staticmethod
    def _leader_theme(theme_leaders: dict[str, Any], theme_name: str) -> dict[str, Any]:
        for row in theme_leaders.get("themes") or []:
            if row.get("name") == theme_name:
                return row
        return {}

    @staticmethod
    def _leaders(theme_leaders: dict[str, Any], theme_name: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for group in ["ready_for_review", "research_first", "watch_only"]:
            for item in theme_leaders.get(group) or []:
                if item.get("theme") == theme_name:
                    rows.append(
                        RatioOnlyService.sanitize(
                            {
                                "type": item.get("type"),
                                "code": item.get("code"),
                                "name": item.get("name"),
                                "route": item.get("route") or group,
                            }
                        )
                    )
        return rows

    @staticmethod
    def _conflicts(theme: dict[str, Any], leader_theme: dict[str, Any]) -> list[dict[str, str]]:
        conflicts: list[dict[str, str]] = []
        if leader_theme.get("confirmed") and str(theme.get("status") or "").lower() == "watch":
            conflicts.append({"type": "status_mismatch", "detail": "leader confirmed while registry is watch"})
        if leader_theme and leader_theme.get("tactical_rating") != theme.get("tactical_rating"):
            conflicts.append({"type": "rating_mismatch", "detail": "leader tactical rating differs from registry"})
        return conflicts

    @staticmethod
    def _status(theme: dict[str, Any], leader_theme: dict[str, Any], data_quality_status: str, conflicts: list[dict[str, str]]) -> str:
        if data_quality_status == "missing":
            return "unknown"
        if conflicts:
            return "conflict"
        if leader_theme.get("confirmed"):
            return "confirmed"
        raw_status = str(theme.get("status") or leader_theme.get("status") or "").lower()
        stage = str(theme.get("stage") or leader_theme.get("stage") or "").lower()
        tactical = str(theme.get("tactical_rating") or leader_theme.get("tactical_rating") or "").upper()
        if raw_status == "watch" or stage == "decline" or tactical in {"C", "D"}:
            return "watch"
        if raw_status in {"active", "confirmed"} and tactical in {"A", "A-", "B+"}:
            return "confirmed"
        return "watch" if raw_status == "active" else "unknown"

    @staticmethod
    def _stock_maps(stocks: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
        return {
            "by_code": {row.get("code"): row for row in stocks if row.get("code")},
            "by_name": {row.get("name"): row for row in stocks if row.get("name")},
        }

    @staticmethod
    def _summary(themes: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "theme_count": len(themes),
            "confirmed_count": sum(1 for item in themes if item.get("status") == "confirmed"),
            "watch_count": sum(1 for item in themes if item.get("status") == "watch"),
            "research_first_count": sum(1 for item in themes if item.get("status") == "research_first"),
            "stale_count": sum(1 for item in themes if item.get("status") == "stale"),
            "conflict_count": sum(1 for item in themes if item.get("status") == "conflict"),
        }

    @staticmethod
    def _generated_at(theme_registry: dict[str, Any], theme_leaders: dict[str, Any]) -> str | None:
        return theme_leaders.get("generated_at") or theme_registry.get("last_updated")
