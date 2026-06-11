"""Normalized extraction for market_score artifacts."""

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


def nested_score(scores: dict[str, Any], key: str) -> float | None:
    value = scores.get(key)
    if isinstance(value, dict):
        return as_float(value.get("score"))
    return as_float(value)


def write_market_score(conn, plan: ArtifactPlan) -> dict[str, int]:
    data = plan.data
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    scores = data.get("scores") if isinstance(data.get("scores"), dict) else {}
    equity_low, equity_high = parse_pct_range(summary.get("equity_allocation_range"))
    bond_low, bond_high = parse_pct_range(summary.get("bond_cash_allocation_range"))
    market_score_run_id = f"market_score_{stable_digest(plan.artifact_id)[:20]}"
    counts = {
        "market_score_runs_inserted": 0,
        "market_score_components_inserted": 0,
        "market_hard_constraints_inserted": 0,
        "market_trigger_adjustments_inserted": 0,
    }
    result = conn.execute(
        """
        INSERT OR IGNORE INTO market_score_runs(
          market_score_run_id, run_id, market_state, opportunity_score,
          crowding_penalty_score, market_position_score, equity_range_low_pct,
          equity_range_high_pct, bond_cash_range_low_pct, bond_cash_range_high_pct,
          offensive_bucket_status, one_line_conclusion, source_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            market_score_run_id,
            plan.run_id,
            summary.get("market_state"),
            as_float(summary.get("opportunity_score")) or nested_score(scores, "opportunity_score"),
            as_float(summary.get("crowding_penalty")) or nested_score(scores, "crowding_penalty"),
            as_float(summary.get("market_position_score")) or nested_score(scores, "market_position_score"),
            equity_low,
            equity_high,
            bond_low,
            bond_high,
            summary.get("offensive_bucket_status"),
            summary.get("one_line_conclusion"),
            json_text(data.get("data_sources")),
        ),
    )
    counts["market_score_runs_inserted"] += result.rowcount

    for key, value in sorted(scores.items()):
        if isinstance(value, dict):
            score = as_float(value.get("score"))
            weight = as_float(value.get("weight"))
            evidence = value.get("evidence")
            raw = value
        else:
            score = as_float(value)
            weight = None
            evidence = None
            raw = value
        result = conn.execute(
            """
            INSERT OR IGNORE INTO market_score_components(
              component_id, market_score_run_id, component_key, score, weight, evidence_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                f"market_component_{stable_digest(f'{market_score_run_id}|{key}')[:20]}",
                market_score_run_id,
                str(key),
                score,
                weight,
                json_text(evidence if evidence is not None else raw),
            ),
        )
        counts["market_score_components_inserted"] += result.rowcount

    for index, item in enumerate(data.get("hard_constraints") or []):
        if isinstance(item, dict):
            key = item.get("constraint") or item.get("name") or f"constraint_{index}"
            status = "triggered" if item.get("triggered") else "not_triggered"
            reason = item.get("impact") or item.get("reason")
            raw = item
        else:
            key = f"constraint_{index}"
            status = "unknown"
            reason = str(item)
            raw = item
        result = conn.execute(
            """
            INSERT OR IGNORE INTO market_hard_constraints(
              constraint_id, market_score_run_id, constraint_key, status, reason, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                f"market_constraint_{stable_digest(f'{market_score_run_id}|{index}|{key}')[:20]}",
                market_score_run_id,
                str(key),
                status,
                reason,
                json_text(raw),
            ),
        )
        counts["market_hard_constraints_inserted"] += result.rowcount

    for index, item in enumerate(data.get("trigger_based_adjustments") or []):
        if isinstance(item, dict):
            trigger_key = item.get("trigger_condition") or f"trigger_{index}"
            reason = item.get("allocation_action") or item.get("allocation_review") or item.get("reverse_condition")
            raw = item
        else:
            trigger_key = f"trigger_{index}"
            reason = str(item)
            raw = item
        result = conn.execute(
            """
            INSERT OR IGNORE INTO market_trigger_adjustments(
              adjustment_id, market_score_run_id, trigger_key, adjustment_pp, reason, raw_json
            ) VALUES (?, ?, ?, NULL, ?, ?)
            """,
            (
                f"market_adjustment_{stable_digest(f'{market_score_run_id}|{index}|{trigger_key}')[:20]}",
                market_score_run_id,
                str(trigger_key),
                reason,
                json_text(raw),
            ),
        )
        counts["market_trigger_adjustments_inserted"] += result.rowcount

    return counts
