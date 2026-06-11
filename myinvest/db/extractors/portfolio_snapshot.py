"""Normalized extraction for portfolio_snapshot artifacts."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from ..ingest import ArtifactPlan, stable_digest
from ..normalize import normalize_security_code


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


def security_id_for(ts_code: str | None, code_short: str | None, name: str | None) -> str:
    key = ts_code or f"{code_short or 'unknown'}|{name or ''}"
    return f"security_{stable_digest(key)[:20]}"


def ensure_security(conn, code: Any, name: Any, asset_type: Any, generated_at: str) -> str:
    normalized = normalize_security_code(str(code) if code is not None else None, str(name) if name is not None else None)
    security_id = security_id_for(normalized["ts_code"], normalized["code_short"], str(name) if name is not None else None)
    code_short = normalized["code_short"] or str(code or "unknown")
    conn.execute(
        """
        INSERT OR IGNORE INTO securities(
          security_id, ts_code, code_short, exchange, name, asset_type, first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            security_id,
            normalized["ts_code"],
            code_short,
            normalized["exchange"],
            str(name) if name is not None else None,
            str(asset_type).lower() if asset_type is not None else None,
            generated_at,
            generated_at,
        ),
    )
    conn.execute(
        """
        UPDATE securities
        SET last_seen_at = CASE WHEN last_seen_at IS NULL OR last_seen_at < ? THEN ? ELSE last_seen_at END,
            name = COALESCE(name, ?),
            asset_type = COALESCE(asset_type, ?)
        WHERE security_id = ?
        """,
        (
            generated_at,
            generated_at,
            str(name) if name is not None else None,
            str(asset_type).lower() if asset_type is not None else None,
            security_id,
        ),
    )
    for alias in normalized["alias_candidates"]:
        conn.execute(
            "INSERT OR IGNORE INTO security_aliases(alias, security_id, alias_type) VALUES (?, ?, 'portfolio_snapshot')",
            (alias, security_id),
        )
    return security_id


def ensure_bucket(conn, bucket_key: str | None) -> None:
    if not bucket_key:
        return
    conn.execute(
        "INSERT OR IGNORE INTO buckets(bucket_key, bucket_label, bucket_type) VALUES (?, ?, 'portfolio')",
        (bucket_key, bucket_key),
    )


def slot_code_for(bucket_key: str | None, code_short: str | None, code_raw: str | None) -> str:
    bucket = (bucket_key or "unknown").upper()
    code = code_short or code_raw or "unknown"
    return f"PS-{bucket}-{code}"


def write_portfolio_snapshot(conn, plan: ArtifactPlan) -> dict[str, int]:
    data = plan.data
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    holdings = data.get("holdings") if isinstance(data.get("holdings"), list) else []
    snapshot_id = f"portfolio_snapshot_{stable_digest(plan.artifact_id)[:20]}"
    basis_trade_date = plan.basis_trade_date or str(data.get("date") or plan.basis_date or "")
    counts = {
        "portfolio_snapshots_inserted": 0,
        "portfolio_positions_inserted": 0,
        "portfolio_bucket_exposures_inserted": 0,
        "portfolio_category_exposures_inserted": 0,
        "position_slots_inserted": 0,
    }

    result = conn.execute(
        """
        INSERT OR IGNORE INTO portfolio_snapshots(
          snapshot_id, run_id, basis_trade_date, equity_weight_pct,
          bond_cash_weight_pct, cash_uninvested_pct, weight_sum_pct,
          privacy_policy, package_redaction_json, source_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot_id,
            plan.run_id,
            basis_trade_date or None,
            as_float(summary.get("equity_weight_pct")),
            as_float(summary.get("bond_cash_weight_pct")),
            as_float(summary.get("cash_uninvested_pct")),
            as_float(summary.get("weight_sum_pct")),
            json_text(data.get("privacy_policy")),
            json_text(data.get("package_redaction")),
            json_text(data.get("source")),
        ),
    )
    counts["portfolio_snapshots_inserted"] += result.rowcount

    bucket_weights: dict[str, float] = defaultdict(float)
    for index, holding in enumerate(holdings):
        if not isinstance(holding, dict):
            continue
        code = holding.get("ts_code") or holding.get("code")
        name = holding.get("name")
        bucket_key = holding.get("allocation_bucket")
        category = holding.get("category")
        weight_pct = as_float(holding.get("weight_pct"))
        if bucket_key:
            bucket_weights[str(bucket_key)] += weight_pct or 0.0
        ensure_bucket(conn, str(bucket_key) if bucket_key is not None else None)
        security_id = ensure_security(conn, code, name, holding.get("type"), plan.generated_at)
        normalized = normalize_security_code(str(code) if code is not None else None, str(name) if name is not None else None)
        slot_code = slot_code_for(str(bucket_key) if bucket_key is not None else None, normalized["code_short"], str(holding.get("code") or ""))
        position_slot_id = f"position_slot_{stable_digest(slot_code)[:20]}"
        result = conn.execute(
            """
            INSERT OR IGNORE INTO position_slots(
              position_slot_id, security_id, slot_code, bucket_key, lifecycle_status, created_run_id
            ) VALUES (?, ?, ?, ?, 'active', ?)
            """,
            (position_slot_id, security_id, slot_code, str(bucket_key) if bucket_key is not None else None, plan.run_id),
        )
        counts["position_slots_inserted"] += result.rowcount
        if bucket_key:
            conn.execute(
                """
                INSERT OR IGNORE INTO bucket_assignment_history(
                  assignment_id, security_id, bucket_key, run_id, effective_at, reason, source_artifact_id
                ) VALUES (?, ?, ?, ?, ?, 'portfolio_snapshot', ?)
                """,
                (
                    f"bucket_assignment_{stable_digest(f'{security_id}|{bucket_key}|{plan.generated_at}')[:20]}",
                    security_id,
                    str(bucket_key),
                    plan.run_id,
                    plan.generated_at,
                    plan.artifact_id,
                ),
            )
        safe_position_json = {
            "code": holding.get("code"),
            "ts_code": holding.get("ts_code"),
            "name": holding.get("name"),
            "type": holding.get("type"),
            "weight_pct": holding.get("weight_pct"),
            "day_change_pct": holding.get("day_change_pct"),
            "reference_pnl_pct": holding.get("reference_pnl_pct"),
            "category": category,
            "allocation_bucket": bucket_key,
        }
        result = conn.execute(
            """
            INSERT OR IGNORE INTO portfolio_positions(
              position_id, snapshot_id, security_id, position_slot_id, code_raw,
              name_raw, allocation_bucket, category, weight_pct, day_change_pct,
              reference_pnl_pct, research_status, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"portfolio_position_{stable_digest(f'{snapshot_id}|{index}|{code}|{name}')[:20]}",
                snapshot_id,
                security_id,
                position_slot_id,
                str(code) if code is not None else None,
                str(name) if name is not None else None,
                str(bucket_key) if bucket_key is not None else None,
                str(category) if category is not None else None,
                weight_pct,
                as_float(holding.get("day_change_pct")),
                as_float(holding.get("reference_pnl_pct")),
                holding.get("research_status"),
                json_text(safe_position_json),
            ),
        )
        counts["portfolio_positions_inserted"] += result.rowcount

    for bucket_key, weight_pct in sorted(bucket_weights.items()):
        result = conn.execute(
            """
            INSERT OR IGNORE INTO portfolio_bucket_exposures(
              bucket_exposure_id, snapshot_id, bucket_key, weight_pct
            ) VALUES (?, ?, ?, ?)
            """,
            (
                f"portfolio_bucket_{stable_digest(f'{snapshot_id}|{bucket_key}')[:20]}",
                snapshot_id,
                bucket_key,
                weight_pct,
            ),
        )
        counts["portfolio_bucket_exposures_inserted"] += result.rowcount

    category_summary = data.get("category_summary") if isinstance(data.get("category_summary"), dict) else {}
    for category, weight in sorted(category_summary.items()):
        result = conn.execute(
            """
            INSERT OR IGNORE INTO portfolio_category_exposures(
              category_exposure_id, snapshot_id, category, weight_pct
            ) VALUES (?, ?, ?, ?)
            """,
            (
                f"portfolio_category_{stable_digest(f'{snapshot_id}|{category}')[:20]}",
                snapshot_id,
                str(category),
                as_float(weight),
            ),
        )
        counts["portfolio_category_exposures_inserted"] += result.rowcount

    return counts
