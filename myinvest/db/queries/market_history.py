"""Read-only market history queries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..connection import connect


def query_market_history(db_path: str | Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT
          run_id, generated_at, basis_trade_date, market_state,
          opportunity_score, crowding_penalty_score, market_position_score,
          equity_range_low_pct, equity_range_high_pct,
          bond_cash_range_low_pct, bond_cash_range_high_pct,
          offensive_bucket_status, one_line_conclusion, artifact_path
        FROM v_market_position_history
        ORDER BY generated_at
    """
    params: list[Any] = []
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    conn = connect(db_path, create_parent=False)
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def format_json(rows: list[dict[str, Any]]) -> str:
    return json.dumps(
        {
            "note": "market history contains allocation ranges and scores only",
            "rows": rows,
        },
        ensure_ascii=False,
        indent=2,
    )
