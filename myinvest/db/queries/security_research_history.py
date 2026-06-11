"""Read-only security profile history queries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..connection import connect
from ..normalize import normalize_security_code


def query_security_research_history(db_path: str | Path, code: str) -> list[dict[str, Any]]:
    normalized = normalize_security_code(code)
    conn = connect(db_path, create_parent=False)
    try:
        rows = conn.execute(
            """
            SELECT rr.generated_at, rr.basis_trade_date, s.ts_code, s.code_short, s.name,
                   spr.profile_type, spr.action_rating, spr.overall_score,
                   spr.target_position_range, spr.research_first_status
            FROM security_profile_runs spr
            JOIN research_runs rr ON rr.run_id = spr.run_id
            JOIN securities s ON s.security_id = spr.security_id
            WHERE s.ts_code = ? OR s.code_short = ?
            ORDER BY rr.generated_at
            """,
            (normalized["ts_code"], normalized["code_short"] or code),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def format_json(rows: list[dict[str, Any]], code: str) -> str:
    return json.dumps({"code": code, "rows": rows}, ensure_ascii=False, indent=2)
