"""Read-only valuation history queries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..connection import connect
from ..normalize import normalize_security_code


VALUATION_COLUMNS = [
    "generated_at",
    "basis_date",
    "current_value",
    "current_zone_label",
    "reasonable_min",
    "reasonable_max",
    "crowded_min",
    "current_vs_reasonable_mid_pct",
    "artifact_path",
]


def query_valuation_history(db_path: str | Path, code: str) -> list[dict[str, Any]]:
    normalized = normalize_security_code(code)
    ts_code = normalized["ts_code"]
    code_short = normalized["code_short"] or code
    conn = connect(db_path, create_parent=False)
    try:
        rows = conn.execute(
            """
            SELECT
              generated_at, basis_date, current_value, current_zone_label,
              reasonable_min, reasonable_max, crowded_min,
              current_vs_reasonable_mid_pct, artifact_path, ts_code, code_short, name,
              current_zone_key, confidence, not_portfolio_action
            FROM v_valuation_zone_drift
            WHERE ts_code = ? OR code_short = ?
            ORDER BY generated_at
            """,
            (ts_code, code_short),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def format_markdown(rows: list[dict[str, Any]], code: str) -> str:
    lines = [
        f"# Valuation History: {code}",
        "",
        "估值区间是标的级研究状态，不是组合级买卖建议。",
        "",
        "| generated_at | basis_date | current_value | zone | reasonable | crowded_min | vs_reasonable_mid_pct | artifact |",
        "|---|---:|---:|---|---|---:|---:|---|",
    ]
    for row in rows:
        reasonable = ""
        if row.get("reasonable_min") is not None or row.get("reasonable_max") is not None:
            reasonable = f"{row.get('reasonable_min') or ''}-{row.get('reasonable_max') or ''}"
        lines.append(
            "| {generated_at} | {basis_date} | {current_value} | {current_zone_label} | {reasonable} | {crowded_min} | {current_vs_reasonable_mid_pct} | {artifact_path} |".format(
                reasonable=reasonable,
                **{key: row.get(key, "") for key in VALUATION_COLUMNS},
            )
        )
    return "\n".join(lines) + "\n"


def format_json(rows: list[dict[str, Any]], code: str) -> str:
    return json.dumps(
        {
            "code": code,
            "note": "valuation zones are security-level research state, not portfolio actions",
            "rows": rows,
        },
        ensure_ascii=False,
        indent=2,
    )
