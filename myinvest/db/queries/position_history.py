"""Read-only portfolio position history queries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..connection import connect
from ..normalize import normalize_security_code


def query_position_history(db_path: str | Path, *, code: str | None = None, bucket: str | None = None) -> list[dict[str, Any]]:
    if not code and not bucket:
        raise ValueError("Use code or bucket")
    params: list[Any] = []
    where: list[str] = []
    if code:
        normalized = normalize_security_code(code)
        where.append("(ts_code = ? OR code_short = ?)")
        params.extend([normalized["ts_code"], normalized["code_short"] or code])
    if bucket:
        where.append("(slot_bucket_key = ? OR snapshot_bucket_key = ?)")
        params.extend([bucket, bucket])
    conn = connect(db_path, create_parent=False)
    try:
        rows = conn.execute(
            f"""
            SELECT
              slot_code, ts_code, name, slot_bucket_key, snapshot_bucket_key,
              category, snapshot_at, basis_trade_date, weight_pct,
              day_change_pct, reference_pnl_pct, lifecycle_status, snapshot_id
            FROM v_position_slot_history
            WHERE {' AND '.join(where)}
            ORDER BY snapshot_at
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def format_json(rows: list[dict[str, Any]], *, code: str | None = None, bucket: str | None = None) -> str:
    return json.dumps(
        {
            "code": code,
            "bucket": bucket,
            "note": "portfolio history stores ratios and percentage points only",
            "rows": rows,
        },
        ensure_ascii=False,
        indent=2,
    )
