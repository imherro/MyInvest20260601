"""Normalized extraction for action_plan artifacts."""

from __future__ import annotations

import json
from typing import Any

from ..ingest import ArtifactPlan, stable_digest
from ..normalize import normalize_security_code, parse_pct_range, parse_suggested_change_pp


def as_float(value: Any) -> float | None:
    low, _ = parse_pct_range(str(value) if value is not None else None)
    return low


def json_text(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def find_security_id(conn, code: str | None, name: str | None) -> str | None:
    if not code:
        return None
    normalized = normalize_security_code(code, name)
    aliases = [code]
    aliases.extend(normalized["alias_candidates"])
    if normalized["ts_code"]:
        aliases.append(normalized["ts_code"])
    for alias in dict.fromkeys(alias for alias in aliases if alias):
        row = conn.execute("SELECT security_id FROM security_aliases WHERE alias = ? LIMIT 1", (alias,)).fetchone()
        if row:
            return str(row["security_id"])
    code_short = normalized["code_short"]
    if code_short:
        row = conn.execute("SELECT security_id FROM securities WHERE code_short = ? LIMIT 1", (code_short,)).fetchone()
        if row:
            return str(row["security_id"])
    return None


def find_position_slot_id(conn, security_id: str | None, bucket_key: str | None) -> str | None:
    if not security_id:
        return None
    if bucket_key:
        row = conn.execute(
            """
            SELECT position_slot_id FROM position_slots
            WHERE security_id = ? AND bucket_key = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (security_id, bucket_key),
        ).fetchone()
        if row:
            return str(row["position_slot_id"])
    row = conn.execute(
        "SELECT position_slot_id FROM position_slots WHERE security_id = ? ORDER BY created_at DESC LIMIT 1",
        (security_id,),
    ).fetchone()
    return str(row["position_slot_id"]) if row else None


def condition_rows(action_item_id: str, condition_type: str, values: Any) -> list[tuple[str, str, str]]:
    if not isinstance(values, list):
        return []
    rows: list[tuple[str, str, str]] = []
    for index, value in enumerate(values):
        text = json_text(value) if isinstance(value, dict) else str(value)
        rows.append((f"action_condition_{stable_digest(f'{action_item_id}|{condition_type}|{index}|{text}')[:20]}", condition_type, text))
    return rows


def write_action_plan(conn, plan: ArtifactPlan) -> dict[str, int]:
    data = plan.data
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    preconditions = data.get("preconditions") if isinstance(data.get("preconditions"), dict) else {}
    action_plan_id = f"action_plan_{stable_digest(plan.artifact_id)[:20]}"
    counts = {
        "action_plans_inserted": 0,
        "action_items_inserted": 0,
        "action_item_evidence_inserted": 0,
        "action_item_conditions_inserted": 0,
        "research_first_blocks_inserted": 0,
    }
    result = conn.execute(
        """
        INSERT OR IGNORE INTO action_plans(
          action_plan_id, run_id, session, action_state, recommendation_strength,
          market_conclusion, valuation_conclusion, portfolio_conclusion,
          research_first_conclusion, one_line_conclusion, source_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            action_plan_id,
            plan.run_id,
            data.get("session"),
            summary.get("action_state"),
            summary.get("recommendation_strength"),
            json_text(preconditions.get("market_position")),
            json_text(preconditions.get("valuation")),
            json_text(preconditions.get("portfolio_deviation")),
            json_text(data.get("research_first_list")),
            summary.get("one_line_conclusion"),
            json_text(data.get("source_files") or data.get("dependencies")),
        ),
    )
    counts["action_plans_inserted"] += result.rowcount

    for index, item in enumerate(data.get("actions") or []):
        if not isinstance(item, dict):
            continue
        subject = item.get("subject") if isinstance(item.get("subject"), dict) else {}
        subject_code = str(subject.get("code") or "").strip() or None
        subject_name = subject.get("name")
        bucket_key = item.get("bucket_role")
        security_id = find_security_id(conn, subject_code, subject_name)
        position_slot_id = find_position_slot_id(conn, security_id, str(bucket_key) if bucket_key else None)
        suggested_low, suggested_high = parse_suggested_change_pp(item.get("suggested_change"))
        target_low, target_high = parse_pct_range(item.get("target_position"))
        action_type = item.get("action_type")
        action_item_id = f"action_item_{stable_digest(f'{action_plan_id}|{index}|{subject_code}|{action_type}')[:20]}"
        safe_item_json = {
            "priority": item.get("priority"),
            "action_type": item.get("action_type"),
            "subject": subject,
            "bucket_role": bucket_key,
            "current_position": item.get("current_position"),
            "suggested_change": item.get("suggested_change"),
            "target_position": item.get("target_position"),
            "recommendation_strength": item.get("recommendation_strength"),
            "needs_manual_confirmation": item.get("needs_manual_confirmation"),
        }
        result = conn.execute(
            """
            INSERT OR IGNORE INTO action_items(
              action_item_id, action_plan_id, security_id, position_slot_id,
              priority, action_type, subject_type, subject_code, subject_name,
              bucket_key, current_position_text, current_position_pct,
              suggested_change_text, suggested_change_low_pp, suggested_change_high_pp,
              target_position_text, target_position_low_pct, target_position_high_pct,
              recommendation_strength, needs_manual_confirmation, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action_item_id,
                action_plan_id,
                security_id,
                position_slot_id,
                item.get("priority"),
                action_type,
                subject.get("type"),
                subject_code,
                subject_name,
                bucket_key,
                item.get("current_position"),
                as_float(item.get("current_position")),
                item.get("suggested_change"),
                suggested_low,
                suggested_high,
                item.get("target_position"),
                target_low,
                target_high,
                item.get("recommendation_strength"),
                1 if item.get("needs_manual_confirmation") else 0,
                json_text(safe_item_json),
            ),
        )
        counts["action_items_inserted"] += result.rowcount

        for evidence_index, evidence in enumerate(item.get("evidence") or []):
            text = json_text(evidence) if isinstance(evidence, dict) else str(evidence)
            result = conn.execute(
                """
                INSERT OR IGNORE INTO action_item_evidence(
                  evidence_id, action_item_id, evidence_type, evidence_text
                ) VALUES (?, ?, 'text', ?)
                """,
                (
                    f"action_evidence_{stable_digest(f'{action_item_id}|{evidence_index}|{text}')[:20]}",
                    action_item_id,
                    text,
                ),
            )
            counts["action_item_evidence_inserted"] += result.rowcount

        condition_values = []
        condition_values.extend(condition_rows(action_item_id, "trigger", item.get("trigger_conditions")))
        condition_values.extend(condition_rows(action_item_id, "invalidation", item.get("invalidation_conditions")))
        condition_values.extend(condition_rows(action_item_id, "risk", item.get("risks")))
        condition_values.extend(condition_rows(action_item_id, "review_point", item.get("review_points")))
        for condition_id, condition_type, condition_text in condition_values:
            result = conn.execute(
                """
                INSERT OR IGNORE INTO action_item_conditions(
                  condition_id, action_item_id, condition_type, condition_text
                ) VALUES (?, ?, ?, ?)
                """,
                (condition_id, action_item_id, condition_type, condition_text),
            )
            counts["action_item_conditions_inserted"] += result.rowcount

    for index, block in enumerate(data.get("research_first_list") or []):
        if isinstance(block, dict):
            subject_code = block.get("code") or block.get("subject_code")
            subject_name = block.get("name") or block.get("subject_name")
            subject_type = block.get("type") or block.get("subject_type")
            reason = block.get("reason") or block.get("blocker_reason") or block.get("blocking_reason")
            required = block.get("required_research") or block.get("next_step")
        else:
            subject_code = None
            subject_name = None
            subject_type = None
            reason = str(block)
            required = None
        result = conn.execute(
            """
            INSERT OR IGNORE INTO research_first_blocks(
              research_first_block_id, action_plan_id, subject_code, subject_name,
              subject_type, blocker_reason, required_research, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'blocked')
            """,
            (
                f"research_first_{stable_digest(f'{action_plan_id}|{index}|{subject_code}|{reason}')[:20]}",
                action_plan_id,
                subject_code,
                subject_name,
                subject_type,
                reason,
                required,
            ),
        )
        counts["research_first_blocks_inserted"] += result.rowcount

    return counts
