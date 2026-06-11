"""Normalized extraction for stock_profile and etf_profile artifacts."""

from __future__ import annotations

import json
from typing import Any

from ..ingest import ArtifactPlan, stable_digest
from ..normalize import normalize_security_code, parse_pct_range


def as_float(value: Any) -> float | None:
    try:
        text = str(value).replace("%", "").replace(",", "").strip()
        if not text or text.lower() in {"none", "null", "nan", "n/a"}:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def json_text(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def security_id_for(ts_code: str | None, code_short: str | None, name: str | None) -> str:
    key = ts_code or f"{code_short or 'unknown'}|{name or ''}"
    return f"security_{stable_digest(key)[:20]}"


def ensure_security(conn, plan: ArtifactPlan) -> str:
    normalized = normalize_security_code(plan.code or plan.rel_path, plan.name)
    security_id = security_id_for(normalized["ts_code"], normalized["code_short"], plan.name)
    conn.execute(
        """
        INSERT OR IGNORE INTO securities(
          security_id, ts_code, code_short, exchange, name, asset_type, first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            security_id,
            normalized["ts_code"],
            normalized["code_short"] or plan.code or "unknown",
            normalized["exchange"],
            plan.name,
            "etf" if plan.module == "etf_profile" else "stock",
            plan.generated_at,
            plan.generated_at,
        ),
    )
    for alias in normalized["alias_candidates"]:
        conn.execute(
            "INSERT OR IGNORE INTO security_aliases(alias, security_id, alias_type) VALUES (?, ?, ?)",
            (alias, security_id, plan.module),
        )
    return security_id


def write_security_profile(conn, plan: ArtifactPlan) -> dict[str, int]:
    data = plan.data
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    scores = data.get("scores") if isinstance(data.get("scores"), dict) else {}
    security_id = ensure_security(conn, plan)
    target_low, target_high = parse_pct_range(summary.get("target_position_range"))
    profile_id = f"security_profile_{stable_digest(plan.artifact_id)[:20]}"
    counts = {
        "security_profile_runs_inserted": 0,
        "security_profile_scores_inserted": 0,
        "security_operation_conditions_inserted": 0,
        "security_risk_items_inserted": 0,
    }
    result = conn.execute(
        """
        INSERT OR IGNORE INTO security_profile_runs(
          security_profile_run_id, run_id, security_id, profile_type,
          action_rating, overall_score, target_position_range,
          target_low_pct, target_high_pct, research_first_status, source_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            profile_id,
            plan.run_id,
            security_id,
            plan.module,
            summary.get("action_rating") or summary.get("rating"),
            as_float(summary.get("stock_score") or summary.get("etf_score") or summary.get("score")),
            summary.get("target_position_range"),
            target_low,
            target_high,
            data.get("research_first_status") or "profiled",
            json_text(data.get("data_sources")),
        ),
    )
    counts["security_profile_runs_inserted"] += result.rowcount

    for key, value in sorted(scores.items()):
        if isinstance(value, dict):
            score = as_float(value.get("score") or value.get("value"))
            weight = as_float(value.get("weight"))
            evidence = value.get("evidence") or value
        else:
            score = as_float(value)
            weight = None
            evidence = value
        result = conn.execute(
            """
            INSERT OR IGNORE INTO security_profile_scores(
              score_id, security_profile_run_id, score_key, score, weight, evidence
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                f"security_score_{stable_digest(f'{profile_id}|{key}')[:20]}",
                profile_id,
                str(key),
                score,
                weight,
                json_text(evidence) if not isinstance(evidence, str) else evidence,
            ),
        )
        counts["security_profile_scores_inserted"] += result.rowcount

    conditions = data.get("operation_conditions") if isinstance(data.get("operation_conditions"), dict) else {}
    for condition_type, values in sorted(conditions.items()):
        if not isinstance(values, list):
            values = [values]
        for index, value in enumerate(values):
            text = json_text(value) if isinstance(value, dict) else str(value)
            result = conn.execute(
                """
                INSERT OR IGNORE INTO security_operation_conditions(
                  condition_id, security_profile_run_id, condition_type, condition_text
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    f"security_condition_{stable_digest(f'{profile_id}|{condition_type}|{index}|{text}')[:20]}",
                    profile_id,
                    str(condition_type),
                    text,
                ),
            )
            counts["security_operation_conditions_inserted"] += result.rowcount

    risk_sources = []
    for key in ("risks", "risk_monitors", "risk_controls"):
        value = data.get(key)
        if isinstance(value, list):
            risk_sources.extend(value)
        elif value:
            risk_sources.append(value)
    for index, value in enumerate(risk_sources):
        if isinstance(value, dict):
            risk_key = value.get("key") or value.get("type")
            risk_text = value.get("text") or value.get("risk") or value.get("description") or json_text(value)
            severity = value.get("severity")
        else:
            risk_key = None
            risk_text = str(value)
            severity = None
        result = conn.execute(
            """
            INSERT OR IGNORE INTO security_risk_items(
              risk_item_id, security_profile_run_id, risk_key, risk_text, severity
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                f"security_risk_{stable_digest(f'{profile_id}|{index}|{risk_text}')[:20]}",
                profile_id,
                risk_key,
                risk_text,
                severity,
            ),
        )
        counts["security_risk_items_inserted"] += result.rowcount

    return counts
