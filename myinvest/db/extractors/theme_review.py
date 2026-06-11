"""Normalized extraction for theme_review artifacts."""

from __future__ import annotations

import json
from typing import Any

from ..ingest import ArtifactPlan, stable_digest


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


def theme_key_for(name: str) -> str:
    return stable_digest(name)[:20]


def write_theme_review(conn, plan: ArtifactPlan) -> dict[str, int]:
    data = plan.data
    themes = data.get("themes") if isinstance(data.get("themes"), list) else []
    theme_review_run_id = f"theme_review_{stable_digest(plan.artifact_id)[:20]}"
    counts = {
        "theme_review_runs_inserted": 0,
        "themes_inserted": 0,
        "theme_review_items_inserted": 0,
        "theme_security_links_inserted": 0,
    }
    result = conn.execute(
        """
        INSERT OR IGNORE INTO theme_review_runs(theme_review_run_id, run_id, summary, source_json)
        VALUES (?, ?, ?, ?)
        """,
        (theme_review_run_id, plan.run_id, json_text(data.get("market_context")), json_text(data.get("policy_sources"))),
    )
    counts["theme_review_runs_inserted"] += result.rowcount

    for index, item in enumerate(themes):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or f"theme_{index}")
        theme_key = theme_key_for(name)
        theme_id = f"theme_{theme_key}"
        result = conn.execute(
            "INSERT OR IGNORE INTO themes(theme_id, theme_key, theme_name) VALUES (?, ?, ?)",
            (theme_id, theme_key, name),
        )
        counts["themes_inserted"] += result.rowcount
        review_item_id = f"theme_item_{stable_digest(f'{theme_review_run_id}|{theme_key}')[:20]}"
        result = conn.execute(
            """
            INSERT OR IGNORE INTO theme_review_items(
              theme_review_item_id, theme_review_run_id, theme_id, theme_key,
              theme_name, strategic_rating, trading_rating, phase,
              prior_rating, rating_change_reason, target_position_range,
              target_low_pct, target_high_pct, evidence_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)
            """,
            (
                review_item_id,
                theme_review_run_id,
                theme_id,
                theme_key,
                name,
                item.get("strategic_rating"),
                item.get("tactical_rating") or item.get("trading_rating") or item.get("rating"),
                item.get("stage"),
                item.get("previous_rating"),
                item.get("change_type"),
                item.get("target_position_range"),
                json_text(
                    {
                        "score": item.get("score"),
                        "score_components": item.get("score_components"),
                        "core_view": item.get("core_view"),
                    }
                ),
            ),
        )
        counts["theme_review_items_inserted"] += result.rowcount
        for link_index, linked in enumerate(item.get("etf_stats") or []):
            if not isinstance(linked, dict):
                continue
            code = linked.get("ts_code")
            result = conn.execute(
                """
                INSERT OR IGNORE INTO theme_security_links(
                  link_id, theme_review_item_id, security_id, code, name, link_role
                ) VALUES (?, ?, NULL, ?, ?, 'etf_stat')
                """,
                (
                    f"theme_link_{stable_digest(f'{review_item_id}|{link_index}|{code}')[:20]}",
                    review_item_id,
                    code,
                    linked.get("name"),
                ),
            )
            counts["theme_security_links_inserted"] += result.rowcount
    return counts
