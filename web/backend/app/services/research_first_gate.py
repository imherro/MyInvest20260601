from __future__ import annotations

from sqlalchemy.orm import Session

from ..config import EXECUTABLE_ACTIONS
from ..repositories.current_state import CurrentStateRepository


class ResearchFirstGateService:
    def __init__(self, session: Session):
        self.repo = CurrentStateRepository(session)

    def check(self) -> dict:
        rows = self.repo.all(
            """
            SELECT ai.action_type, s.code, s.name, s.bucket,
                   p.status AS profile_status,
                   v.valuation_status,
                   lg.liquidity_status,
                   lg.duration_boundary_confirmed,
                   lg.interest_rate_risk_disclosed,
                   lg.credit_risk_disclosed,
                   lg.liquidity_risk_disclosed
            FROM action_items ai
            LEFT JOIN subjects s ON s.id = ai.subject_id
            LEFT JOIN profiles p ON p.subject_id = s.id
            LEFT JOIN valuations v ON v.subject_id = s.id
            LEFT JOIN liquidity_gates lg ON lg.subject_id = s.id
            """
        )
        failures = []
        for row in rows:
            action_type = str(row.get("action_type") or "").lower()
            if action_type not in EXECUTABLE_ACTIONS:
                continue
            code = str(row.get("code") or "")
            if not code:
                continue
            profile_ok = str(row.get("profile_status") or "").lower() in {"profile_generated", "pass", "ok"}
            valuation_ok = str(row.get("valuation_status") or "").lower() in {"pass", "ok", "available", "true"}
            liquidity_ok = str(row.get("liquidity_status") or "").lower() in {"pass", "ok", "available", "true"}
            cash_like = code.startswith("511360") or str(row.get("bucket") or "") in {"cash_short", "bond_cash"}
            gate_ok = profile_ok and valuation_ok and liquidity_ok
            if cash_like:
                gate_ok = gate_ok and all(
                    bool(row.get(field))
                    for field in [
                        "duration_boundary_confirmed",
                        "interest_rate_risk_disclosed",
                        "credit_risk_disclosed",
                        "liquidity_risk_disclosed",
                    ]
                )
            if not gate_ok:
                failures.append({"code": code, "name": row.get("name"), "action_type": row.get("action_type")})
        return {"status": "ok" if not failures else "fail", "failures": failures}
