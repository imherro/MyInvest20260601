"""Normalized extraction for valuation_report artifacts."""

from __future__ import annotations

import json
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


def ensure_security(conn, plan: ArtifactPlan) -> str:
    normalized = normalize_security_code(plan.code or plan.rel_path, plan.name)
    security_id = security_id_for(normalized["ts_code"], normalized["code_short"], plan.name)
    code_short = normalized["code_short"] or plan.code or "unknown"
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
            plan.name,
            plan.data.get("asset_type"),
            plan.generated_at,
            plan.generated_at,
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
        (plan.generated_at, plan.generated_at, plan.name, plan.data.get("asset_type"), security_id),
    )
    for alias in normalized["alias_candidates"]:
        conn.execute(
            "INSERT OR IGNORE INTO security_aliases(alias, security_id, alias_type) VALUES (?, ?, 'valuation_report')",
            (alias, security_id),
        )
    return security_id


def write_valuation_report(conn, plan: ArtifactPlan) -> dict[str, int]:
    data = plan.data
    visual = data.get("valuation_visual") if isinstance(data.get("valuation_visual"), dict) else {}
    stance = data.get("security_stance") if isinstance(data.get("security_stance"), dict) else {}
    reference = data.get("reference_metrics") if isinstance(data.get("reference_metrics"), dict) else {}
    security_id = ensure_security(conn, plan)
    valuation_id = f"valuation_{stable_digest(plan.artifact_id)[:20]}"
    price_series = visual.get("price_series") or reference.get("price_series")
    not_portfolio_action = stance.get("not_portfolio_action")
    if not_portfolio_action is None:
        not_portfolio_action = True

    counts = {
        "securities_touched": 1,
        "valuation_reports_inserted": 0,
        "valuation_zones_inserted": 0,
        "valuation_metrics_inserted": 0,
        "valuation_reference_metrics_inserted": 0,
        "valuation_data_gaps_inserted": 0,
    }
    result = conn.execute(
        """
        INSERT OR IGNORE INTO valuation_reports(
          valuation_id, run_id, security_id, basis_date, price_date, asset_type,
          current_value, comparable_current_value, current_zone_key, current_zone_label,
          stance_label, valuation_basis, confidence, not_portfolio_action,
          source_json, price_series_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            valuation_id,
            plan.run_id,
            security_id,
            plan.basis_date,
            reference.get("price_date") or plan.basis_date,
            data.get("asset_type"),
            as_float(visual.get("current_value")),
            as_float(visual.get("comparable_current_value")),
            visual.get("current_zone"),
            visual.get("current_zone_label"),
            stance.get("label"),
            visual.get("basis") or data.get("one_line_conclusion"),
            data.get("confidence") or stance.get("confidence"),
            1 if bool(not_portfolio_action) else 0,
            json_text(data.get("source")),
            json_text(price_series),
        ),
    )
    counts["valuation_reports_inserted"] += result.rowcount

    for index, zone in enumerate(visual.get("zones") or []):
        if not isinstance(zone, dict):
            continue
        zone_key = str(zone.get("key") or zone.get("zone_key") or f"zone_{index}")
        result = conn.execute(
            """
            INSERT OR IGNORE INTO valuation_zones(
              valuation_zone_id, valuation_id, zone_key, zone_label,
              min_value, max_value, display_order, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"valuation_zone_{stable_digest(f'{valuation_id}|{zone_key}')[:20]}",
                valuation_id,
                zone_key,
                zone.get("label") or zone.get("zone_label"),
                as_float(zone.get("min") if "min" in zone else zone.get("min_value")),
                as_float(zone.get("max") if "max" in zone else zone.get("max_value")),
                index,
                json_text(zone),
            ),
        )
        counts["valuation_zones_inserted"] += result.rowcount

    for index, metric in enumerate(data.get("stock_valuation_metrics") or []):
        if not isinstance(metric, dict):
            continue
        metric_key = str(metric.get("metric") or metric.get("key") or f"metric_{index}")
        raw_value = metric.get("value")
        result = conn.execute(
            """
            INSERT OR IGNORE INTO valuation_metrics(
              valuation_metric_id, valuation_id, metric_key, metric_value,
              metric_text, unit, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"valuation_metric_{stable_digest(f'{valuation_id}|{metric_key}|{index}')[:20]}",
                valuation_id,
                metric_key,
                as_float(raw_value),
                None if as_float(raw_value) is not None else (str(raw_value) if raw_value is not None else None),
                metric.get("unit"),
                json_text(metric),
            ),
        )
        counts["valuation_metrics_inserted"] += result.rowcount

    for metric_key, raw_value in reference.items():
        if metric_key in {"valuation_visual", "trend_visual", "price_series", "risk_markers"}:
            metric_text = json_text(raw_value)
            metric_value = None
        else:
            metric_value = as_float(raw_value)
            metric_text = None if metric_value is not None else (str(raw_value) if raw_value is not None else None)
        result = conn.execute(
            """
            INSERT OR IGNORE INTO valuation_reference_metrics(
              reference_metric_id, valuation_id, metric_key, metric_value,
              metric_text, unit, raw_json
            ) VALUES (?, ?, ?, ?, ?, NULL, ?)
            """,
            (
                f"valuation_reference_{stable_digest(f'{valuation_id}|{metric_key}')[:20]}",
                valuation_id,
                str(metric_key),
                metric_value,
                metric_text,
                json_text(raw_value),
            ),
        )
        counts["valuation_reference_metrics_inserted"] += result.rowcount

    for index, gap in enumerate(data.get("data_gaps") or []):
        if isinstance(gap, dict):
            gap_key = gap.get("key") or gap.get("type")
            severity = gap.get("severity")
            description = gap.get("description") or gap.get("message") or json_text(gap)
        else:
            gap_key = None
            severity = None
            description = str(gap)
        result = conn.execute(
            """
            INSERT OR IGNORE INTO valuation_data_gaps(
              data_gap_id, valuation_id, gap_key, severity, description
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                f"valuation_gap_{stable_digest(f'{valuation_id}|{index}|{description}')[:20]}",
                valuation_id,
                gap_key,
                severity,
                description,
            ),
        )
        counts["valuation_data_gaps_inserted"] += result.rowcount

    return counts
