"""Read-only action history queries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..connection import connect
from ..normalize import normalize_security_code


def query_action_history(
    db_path: str | Path,
    *,
    code: str | None = None,
    action_type: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    where: list[str] = []
    if code:
        normalized = normalize_security_code(code)
        code_short = normalized["code_short"] or code
        where.append("(subject_code = ? OR subject_code = ?)")
        params.extend([code, code_short])
    if action_type:
        where.append("action_type = ?")
        params.append(action_type)
    sql = """
        SELECT
          generated_at, basis_trade_date, session, action_state, priority,
          action_type, subject_type, subject_code, subject_name, bucket_key,
          slot_code, current_position_text, suggested_change_text,
          suggested_change_low_pp, suggested_change_high_pp,
          target_position_text, recommendation_strength,
          needs_manual_confirmation, one_line_conclusion, artifact_path
        FROM v_action_history
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY generated_at, priority, subject_code"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    conn = connect(db_path, create_parent=False)
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def format_json(
    rows: list[dict[str, Any]],
    *,
    code: str | None = None,
    action_type: str | None = None,
) -> str:
    return json.dumps(
        {
            "code": code,
            "action_type": action_type,
            "note": "action history is ratio-only and requires manual confirmation; it is not automatic trading",
            "rows": rows,
        },
        ensure_ascii=False,
        indent=2,
    )
