from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..services.database import DatabaseService


class SubjectGapRepository:
    def __init__(self, session: Session):
        self.db = DatabaseService(session)

    def list_subject_gap_rows(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            WITH latest_snapshot AS (
                SELECT id, generated_at, basis_trade_date
                FROM portfolio_snapshots
                ORDER BY id DESC
                LIMIT 1
            ),
            latest_target AS (
                SELECT id, generated_at, basis_trade_date
                FROM target_allocations
                ORDER BY id DESC
                LIMIT 1
            ),
            latest_subject_artifacts AS (
                SELECT a.subject_code, a.generated_at, a.basis_trade_date, a.path
                FROM artifacts a
                JOIN (
                    SELECT subject_code, MAX(id) AS artifact_id
                    FROM artifacts
                    WHERE subject_code IS NOT NULL
                    GROUP BY subject_code
                ) latest ON latest.artifact_id = a.id
            )
            SELECT
                s.code,
                s.name,
                s.subject_type,
                COALESCE(pp.bucket, s.bucket) AS bucket,
                pp.position_pct,
                ba.actual_pct,
                ba.target_pct,
                ba.gap_pct,
                ls.generated_at AS portfolio_generated_at,
                ls.basis_trade_date AS portfolio_basis_trade_date,
                lt.generated_at AS target_generated_at,
                lt.basis_trade_date AS target_basis_trade_date,
                lsa.generated_at AS subject_generated_at,
                lsa.basis_trade_date AS subject_basis_trade_date,
                lsa.path AS subject_source_path
            FROM subjects s
            LEFT JOIN latest_snapshot ls
            LEFT JOIN portfolio_positions pp ON pp.snapshot_id = ls.id AND pp.subject_id = s.id
            LEFT JOIN latest_target lt
            LEFT JOIN bucket_allocations ba
                ON ba.target_allocation_id = lt.id
                AND ba.bucket = COALESCE(pp.bucket, CASE WHEN s.bucket = 'bond_cash' THEN 'cash_short' ELSE s.bucket END)
            LEFT JOIN latest_subject_artifacts lsa ON lsa.subject_code = s.code
            ORDER BY COALESCE(pp.position_pct, 0) DESC, s.code
            """
        )
