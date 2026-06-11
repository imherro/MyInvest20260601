"""Read-only theme history queries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..connection import connect


def query_theme_history(db_path: str | Path, theme_name: str | None = None) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ""
    if theme_name:
        where = "WHERE tri.theme_name = ?"
        params.append(theme_name)
    conn = connect(db_path, create_parent=False)
    try:
        rows = conn.execute(
            f"""
            SELECT rr.generated_at, rr.basis_trade_date, tri.theme_name,
                   tri.strategic_rating, tri.trading_rating, tri.phase,
                   tri.prior_rating, tri.rating_change_reason
            FROM theme_review_items tri
            JOIN theme_review_runs trr ON trr.theme_review_run_id = tri.theme_review_run_id
            JOIN research_runs rr ON rr.run_id = trr.run_id
            {where}
            ORDER BY rr.generated_at, tri.theme_name
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def format_json(rows: list[dict[str, Any]], theme_name: str | None = None) -> str:
    return json.dumps({"theme": theme_name, "rows": rows}, ensure_ascii=False, indent=2)
