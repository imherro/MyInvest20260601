from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..services.database import DatabaseService


class SubjectStatusRepository:
    def __init__(self, session: Session):
        self.db = DatabaseService(session)

    def list_subject_status_rows(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
                WITH latest_positions AS (
                    SELECT pp.subject_id, pp.bucket, pp.position_pct
                    FROM portfolio_positions pp
                    JOIN (
                        SELECT subject_id, MAX(id) AS max_id
                        FROM portfolio_positions
                        GROUP BY subject_id
                    ) latest ON latest.max_id = pp.id
                )
                SELECT
                    s.code,
                    s.name,
                    s.subject_type,
                    COALESCE(lp.bucket, s.bucket) AS bucket,
                    s.status AS subject_status,
                    p.status AS profile_status_raw,
                    p.generated_at AS profile_generated_at,
                    p.basis_date AS profile_basis_date,
                    pa.path AS profile_source_path,
                    v.valuation_status AS valuation_status_raw,
                    v.generated_at AS valuation_generated_at,
                    v.basis_date AS valuation_basis_date,
                    va.path AS valuation_source_path,
                    lg.liquidity_status AS liquidity_status_raw,
                    lg.valuation_status AS liquidity_valuation_status_raw,
                    lg.duration_boundary_confirmed,
                    lg.interest_rate_risk_disclosed,
                    lg.credit_risk_disclosed,
                    lg.liquidity_risk_disclosed,
                    lg.generated_at AS liquidity_generated_at,
                    lpa.path AS liquidity_profile_source_path,
                    lva.path AS liquidity_valuation_source_path,
                    rfi.id AS research_first_item_id,
                    rfi.missing_profile,
                    rfi.missing_valuation,
                    rfi.missing_liquidity,
                    rfi.missing_theme_binding,
                    rfi.allowed_conclusion,
                    rfi.blocking_reason
                FROM subjects s
                LEFT JOIN latest_positions lp ON lp.subject_id = s.id
                LEFT JOIN profiles p ON p.subject_id = s.id
                LEFT JOIN artifacts pa ON pa.id = p.source_artifact_id
                LEFT JOIN valuations v ON v.subject_id = s.id
                LEFT JOIN artifacts va ON va.id = v.valuation_source_artifact_id
                LEFT JOIN liquidity_gates lg ON lg.subject_id = s.id
                LEFT JOIN artifacts lpa ON lpa.id = lg.source_profile_artifact_id
                LEFT JOIN artifacts lva ON lva.id = lg.source_valuation_artifact_id
                LEFT JOIN research_first_items rfi ON rfi.subject_id = s.id
                ORDER BY s.code
                """
        )

    def get_subject_status_row(self, code: str) -> dict[str, Any] | None:
        for row in self.list_subject_status_rows():
            if row.get("code") == code:
                return row
        return None
