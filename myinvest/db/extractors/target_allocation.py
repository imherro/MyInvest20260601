"""Normalized extraction for target_allocation artifacts."""

from __future__ import annotations

import json
from typing import Any

from ..ingest import ArtifactPlan, stable_digest
from ..normalize import parse_pct_range


def as_float(value: Any) -> float | None:
    try:
        text = str(value).replace("%", "").replace(",", "").strip()
        if not text or text.lower() in {"none", "null", "nan", "n/a"}:
            return None
        result = float(text)
    except (TypeError, ValueError):
        return None
    if result != result or result in {float("inf"), float("-inf")}:
        return None
    return result


def json_text(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def write_target_allocation(conn, plan: ArtifactPlan) -> dict[str, int]:
    data = plan.data
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    equity_low, equity_high = parse_pct_range(summary.get("recommended_equity_range"))
    bond_low, bond_high = parse_pct_range(summary.get("recommended_bond_cash_range"))
    target_allocation_id = f"target_allocation_{stable_digest(plan.artifact_id)[:20]}"
    counts = {
        "target_allocation_runs_inserted": 0,
        "target_allocation_buckets_inserted": 0,
        "target_transition_targets_inserted": 0,
    }
    result = conn.execute(
        """
        INSERT OR IGNORE INTO target_allocation_runs(
          target_allocation_id, run_id, basis_trade_date, equity_target_low_pct,
          equity_target_high_pct, bond_cash_target_low_pct, bond_cash_target_high_pct,
          one_line_conclusion, source_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            target_allocation_id,
            plan.run_id,
            plan.basis_trade_date,
            equity_low,
            equity_high,
            bond_low,
            bond_high,
            summary.get("one_line_conclusion"),
            json_text(data.get("data_sources") or data.get("dependencies")),
        ),
    )
    counts["target_allocation_runs_inserted"] += result.rowcount

    overlay = data.get("actual_allocation_overlay") if isinstance(data.get("actual_allocation_overlay"), dict) else {}
    buckets = overlay.get("buckets") if isinstance(overlay.get("buckets"), list) else []
    for index, bucket in enumerate(buckets):
        if not isinstance(bucket, dict):
            continue
        key = str(bucket.get("key") or bucket.get("bucket_key") or f"bucket_{index}")
        conn.execute(
            "INSERT OR IGNORE INTO buckets(bucket_key, bucket_label, bucket_type) VALUES (?, ?, 'target_allocation')",
            (key, bucket.get("label") or key),
        )
        target_pct = as_float(bucket.get("target_pct"))
        result = conn.execute(
            """
            INSERT OR IGNORE INTO target_allocation_buckets(
              target_bucket_id, target_allocation_id, bucket_key, target_low_pct,
              target_high_pct, target_center_pct, actual_pct, gap_pct, raw_json
            ) VALUES (?, ?, ?, NULL, NULL, ?, ?, ?, ?)
            """,
            (
                f"target_bucket_{stable_digest(f'{target_allocation_id}|{key}')[:20]}",
                target_allocation_id,
                key,
                target_pct,
                as_float(bucket.get("actual_pct")),
                as_float(bucket.get("gap_pct")),
                json_text(bucket),
            ),
        )
        counts["target_allocation_buckets_inserted"] += result.rowcount

    for index, item in enumerate(data.get("transition_targets") or []):
        if not isinstance(item, dict):
            continue
        target_low, target_high = parse_pct_range(item.get("target_position") or item.get("target_range"))
        result = conn.execute(
            """
            INSERT OR IGNORE INTO target_transition_targets(
              transition_target_id, target_allocation_id, subject_code, subject_name,
              bucket_key, target_low_pct, target_high_pct, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"target_transition_{stable_digest(f'{target_allocation_id}|{index}')[:20]}",
                target_allocation_id,
                item.get("code"),
                item.get("name"),
                item.get("bucket_key") or item.get("bucket_role"),
                target_low,
                target_high,
                item.get("reason") or item.get("principle"),
            ),
        )
        counts["target_transition_targets_inserted"] += result.rowcount

    return counts
