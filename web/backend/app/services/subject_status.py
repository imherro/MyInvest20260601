from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..repositories.subject_status_repo import SubjectStatusRepository
from .ratio_only import RatioOnlyService


PASS_VALUES = {"pass", "ok", "complete", "completed", "profile_generated", "generated"}
ALLOWED_GATE_CONCLUSIONS = {
    "eligible_for_review",
    "research_first",
    "watch",
    "hold",
    "no_action",
    "unknown",
    "blocked",
}
ACTION_CONCLUSIONS = {"buy", "add", "reduce", "sell"}


class SubjectStatusService:
    def __init__(self, session: Session):
        self.repo = SubjectStatusRepository(session)

    def list_statuses(self) -> dict[str, Any]:
        subjects = [self._normalize(row) for row in self.repo.list_subject_status_rows()]
        payload = {
            "current_only": True,
            "resolver": "research/latest_index.json modules via SQLite current state",
            "subjects": subjects,
            "summary": self._summary(subjects),
        }
        RatioOnlyService.assert_safe(payload)
        return payload

    def get_status(self, code: str) -> dict[str, Any]:
        row = self.repo.get_subject_status_row(code)
        if row is None:
            raise LookupError(code)
        payload = self._normalize(row)
        RatioOnlyService.assert_safe(payload)
        return payload

    def _normalize(self, row: dict[str, Any]) -> dict[str, Any]:
        profile_status = self._normalize_profile_status(row.get("profile_status_raw"))
        valuation_status = self._normalize_status(row.get("valuation_status_raw"))
        liquidity_status = self._normalize_status(row.get("liquidity_status_raw"))
        missing_profile = profile_status != "pass"
        missing_valuation = valuation_status != "pass"
        missing_liquidity = liquidity_status != "pass"

        if row.get("missing_profile") is not None:
            missing_profile = bool(row.get("missing_profile"))
        if row.get("missing_valuation") is not None:
            missing_valuation = bool(row.get("missing_valuation"))
        if row.get("missing_liquidity") is not None:
            missing_liquidity = bool(row.get("missing_liquidity"))
        missing_theme_binding = bool(row.get("missing_theme_binding") or False)

        research_first_status = self._research_first_status(
            missing_profile=missing_profile,
            missing_valuation=missing_valuation,
            missing_liquidity=missing_liquidity,
            missing_theme_binding=missing_theme_binding,
            blocking_reason=row.get("blocking_reason"),
        )
        gate_conclusion = self._gate_conclusion(
            row.get("allowed_conclusion"),
            research_first_status=research_first_status,
            subject_status=row.get("subject_status"),
        )

        payload = {
            "code": row.get("code"),
            "name": row.get("name"),
            "subject_type": self._display_subject_type(row),
            "bucket": self._display_bucket(row),
            "profile_status": profile_status,
            "valuation_status": valuation_status,
            "liquidity_status": liquidity_status,
            "research_first_status": research_first_status,
            "gate_conclusion": gate_conclusion,
            "blocking_reason": row.get("blocking_reason") or self._blocking_reason(
                missing_profile=missing_profile,
                missing_valuation=missing_valuation,
                missing_liquidity=missing_liquidity,
                missing_theme_binding=missing_theme_binding,
            ),
            "source_paths": self._source_paths(row),
            "generated_at": self._latest_text(
                row.get("profile_generated_at"),
                row.get("valuation_generated_at"),
                row.get("liquidity_generated_at"),
            ),
            "basis_trade_date": self._latest_text(row.get("profile_basis_date"), row.get("valuation_basis_date")),
            "missing_profile": missing_profile,
            "missing_valuation": missing_valuation,
            "missing_liquidity": missing_liquidity,
            "missing_theme_binding": missing_theme_binding,
        }
        return RatioOnlyService.sanitize(payload)

    @staticmethod
    def _normalize_status(value: Any) -> str:
        if value is None:
            return "missing"
        status = str(value).strip().lower()
        if status in PASS_VALUES:
            return "pass"
        return status or "unknown"

    def _normalize_profile_status(self, value: Any) -> str:
        return self._normalize_status(value)

    @staticmethod
    def _display_subject_type(row: dict[str, Any]) -> str | None:
        code = str(row.get("code") or "")
        bucket = str(row.get("bucket") or "")
        if code == "511360.SH" or bucket in {"cash_short", "bond_cash"}:
            return "cash_equivalent"
        return row.get("subject_type")

    @staticmethod
    def _display_bucket(row: dict[str, Any]) -> str | None:
        bucket = row.get("bucket")
        if bucket == "bond_cash":
            return "cash_short"
        return bucket

    @staticmethod
    def _research_first_status(
        *,
        missing_profile: bool,
        missing_valuation: bool,
        missing_liquidity: bool,
        missing_theme_binding: bool,
        blocking_reason: Any,
    ) -> str:
        if blocking_reason:
            return "blocked"
        if any([missing_profile, missing_valuation, missing_liquidity, missing_theme_binding]):
            return "research_first"
        return "pass"

    @staticmethod
    def _gate_conclusion(allowed_conclusion: Any, *, research_first_status: str, subject_status: Any) -> str:
        candidate = str(allowed_conclusion or "").strip().lower()
        if candidate in ACTION_CONCLUSIONS:
            return "blocked"
        if candidate in ALLOWED_GATE_CONCLUSIONS:
            return candidate
        if research_first_status in {"blocked", "research_first"}:
            return research_first_status
        subject_candidate = str(subject_status or "").strip().lower()
        if subject_candidate in ALLOWED_GATE_CONCLUSIONS:
            return subject_candidate
        return "eligible_for_review" if research_first_status == "pass" else "unknown"

    @staticmethod
    def _blocking_reason(
        *,
        missing_profile: bool,
        missing_valuation: bool,
        missing_liquidity: bool,
        missing_theme_binding: bool,
    ) -> str:
        missing = []
        if missing_profile:
            missing.append("profile")
        if missing_valuation:
            missing.append("valuation")
        if missing_liquidity:
            missing.append("liquidity")
        if missing_theme_binding:
            missing.append("theme_binding")
        return "missing " + ", ".join(missing) if missing else ""

    @staticmethod
    def _source_paths(row: dict[str, Any]) -> dict[str, str]:
        paths: dict[str, str] = {}
        for key, label in [
            ("profile_source_path", "profile"),
            ("valuation_source_path", "valuation"),
            ("liquidity_profile_source_path", "liquidity_profile"),
            ("liquidity_valuation_source_path", "liquidity_valuation"),
        ]:
            value = row.get(key)
            if value:
                paths[label] = str(value).replace(chr(92), "/")
        return paths

    @staticmethod
    def _latest_text(*values: Any) -> str | None:
        candidates = [str(value) for value in values if value]
        return max(candidates) if candidates else None

    @staticmethod
    def _summary(subjects: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "subject_count": len(subjects),
            "pass_count": sum(1 for item in subjects if item.get("research_first_status") == "pass"),
            "research_first_count": sum(1 for item in subjects if item.get("research_first_status") == "research_first"),
            "blocked_count": sum(1 for item in subjects if item.get("research_first_status") == "blocked"),
        }
