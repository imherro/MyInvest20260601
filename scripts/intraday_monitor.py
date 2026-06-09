#!/usr/bin/env python3
"""Generate intraday alerts from a quote snapshot and fixed trigger rules."""

from __future__ import annotations

import argparse
import json
import operator
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES = ROOT / "research" / "alerts" / "intraday_rules.json"
DEFAULT_OUTPUT_DIR = ROOT / "research" / "alerts"


OPS = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}


PRIORITY_RANK = {"high": 3, "medium": 2, "low": 1, "none": 0}
TRIGGER_SEVERITY = {
    "blocked": 5.0,
    "gate_blocked": 4.5,
    "risk_trigger": 4.0,
    "sell_trigger": 4.0,
    "reduce_trigger": 3.5,
    "invalidation_trigger": 3.5,
    "watch_trigger": 2.0,
    "near_trigger": 1.5,
    "buy_trigger": 1.0,
    "add_trigger": 1.0,
}


def build_valuation_update_check(
    monitored_quotes: list[dict[str, Any]],
    timestamp: str,
    basis_date: str,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for quote in monitored_quotes:
        if quote.get("allocation_bucket") == "cash_short":
            continue
        if not quote.get("valuation_zone_changed"):
            continue

        report_zone = quote.get("valuation_report_zone") or {}
        realtime_zone = quote.get("realtime_valuation_zone") or {}
        report_label = report_zone.get("label") or report_zone.get("key") or "unknown"
        realtime_label = realtime_zone.get("label") or realtime_zone.get("key") or "unknown"
        items.append(
            {
                "code": quote.get("code"),
                "name": quote.get("name"),
                "severity": "update",
                "reasons": [
                    f"实时价格/净值已从估值报告区间 {report_label} 跨入 {realtime_label}",
                    "盘中监测只提示估值复核，不生成买入、卖出、加仓、减仓指令",
                ],
                "latest_valuation": {
                    "report_zone": report_zone,
                    "realtime_zone": realtime_zone,
                },
                "suggested_next_step": "盘后或盘前重做该标的估值报告，并同步盘中规则。",
            }
        )

    return {
        "module": "valuation_update_check",
        "version": "intraday_overlay_v1",
        "generated_at": timestamp,
        "basis_date": basis_date,
        "scope": "intraday_monitored_quotes",
        "status": "update_needed" if items else "ok",
        "blocking_for_new_actions": bool(items),
        "update_required_count": len(items),
        "items": items,
        "summary": (
            f"盘中发现 {len(items)} 个标的实时价格/净值跨估值区间，新增风险动作前需要先复核估值。"
            if items
            else "盘中未发现监控标的跨估值区间。"
        ),
        "boundary": "Valuation refresh check only; no buy/sell/add/reduce instruction.",
    }


@dataclass
class ConditionResult:
    passed: bool
    blocked: bool
    near: bool
    text: str


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def normalize_timestamp(value: str | None) -> str:
    if value and len(value) == 17 and value[4] == "-" and value[10] == "_":
        return value
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def normalize_code(code: str) -> str:
    code = code.strip().upper()
    if "." in code:
        return code
    if code.startswith(("0", "3")):
        return f"{code}.SZ"
    if code.startswith(("5", "6", "9")):
        return f"{code}.SH"
    return code


def number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def metric_value(quote: dict[str, Any], metric: str) -> Any:
    return quote.get(metric)


def target_value(quote: dict[str, Any], condition: dict[str, Any]) -> Any:
    if "ref" in condition:
        return quote.get(condition["ref"])
    return condition.get("value")


def is_near(current: float, target: float, op: str, threshold_pct: float) -> bool:
    if target == 0:
        return False
    distance_pct = abs(current - target) / abs(target) * 100
    if distance_pct > threshold_pct:
        return False
    if op in {">", ">="}:
        return current < target
    if op in {"<", "<="}:
        return current > target
    return False


def evaluate_condition(
    quote: dict[str, Any],
    condition: dict[str, Any],
    near_threshold_pct: float,
) -> ConditionResult:
    metric = condition["metric"]
    op_name = condition.get("op")
    if op_name not in OPS:
        return ConditionResult(False, True, False, f"{metric}: unsupported op {op_name}")

    current = number(metric_value(quote, metric))
    target = number(target_value(quote, condition))
    missing_policy = condition.get("missing", "block")

    if current is None or target is None:
        blocked = missing_policy != "ignore"
        passed = missing_policy == "ignore"
        return ConditionResult(
            passed,
            blocked,
            False,
            f"{metric}: missing current/target, policy={missing_policy}",
        )

    passed = bool(OPS[op_name](current, target))
    near = False if passed else is_near(current, target, op_name, near_threshold_pct)
    return ConditionResult(
        passed,
        False,
        near,
        f"{metric} {op_name} {target:g}; current={current:g}",
    )


def market_gate_allows(rule: dict[str, Any], rules: dict[str, Any], snapshot: dict[str, Any]) -> bool:
    context = snapshot.get("market_context", {})
    gate = context.get("market_gate") or rules.get("global_gate", {}).get("default_market_gate")
    alert_type = rule.get("alert_type", "")
    if alert_type in {"risk_trigger", "sell_trigger", "reduce_trigger", "invalidation_trigger"}:
        return bool(rules.get("global_gate", {}).get("risk_reduce_always_allowed", True))
    if alert_type in {"buy_trigger", "add_trigger"}:
        return gate in set(rules.get("global_gate", {}).get("allow_add_when_market_gate", []))
    if alert_type in {"watch_trigger", "near_trigger"}:
        return gate in set(rules.get("global_gate", {}).get("allow_watch_when_market_gate", []))
    return True


def rules_are_stale(rules: dict[str, Any]) -> bool:
    status = str((rules.get("staleness") or {}).get("status", "")).lower()
    return status in {"stale", "blocked", "degraded", "legacy_unknown"}


def action_blocked_by_staleness(rule: dict[str, Any], rules: dict[str, Any]) -> bool:
    if not rules_are_stale(rules):
        return False
    return rule.get("alert_type") in {"buy_trigger", "add_trigger"} or rule.get("suggested_action") in {"buy", "add", "increase"}


def subject_weight(subject: dict[str, Any]) -> float:
    ref = subject.get("reference_metrics") or {}
    try:
        return float(ref.get("current_position_pct") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def priority_score(subject: dict[str, Any], alert: dict[str, Any], rules: dict[str, Any]) -> float:
    weight = subject_weight(subject)
    weight_score = max(0.2, min(2.5, 0.5 + weight / 10.0))
    severity = TRIGGER_SEVERITY.get(alert.get("alert_type"), PRIORITY_RANK.get(alert.get("priority"), 1))
    stale = rules_are_stale(rules)
    market_multiplier = 1.0
    if stale and alert.get("alert_type") not in {"risk_trigger", "sell_trigger", "reduce_trigger", "blocked", "gate_blocked"}:
        market_multiplier = 0.35
    data_multiplier = 0.6 if alert.get("alert_type") == "blocked" else 1.0
    return round(weight_score * severity * market_multiplier * data_multiplier, 4)


def attach_priority_score(subject: dict[str, Any], alert: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    alert["priority_label"] = alert.get("priority", "medium")
    alert["priority_score"] = priority_score(subject, alert, rules)
    alert["position_weight_pct"] = round(subject_weight(subject), 4)
    return alert


def evaluate_rule(
    subject: dict[str, Any],
    rule: dict[str, Any],
    quote: dict[str, Any],
    rules: dict[str, Any],
    snapshot: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    near_threshold_pct = float(rule.get("near_threshold_pct", 0.0))
    condition_results = [
        evaluate_condition(quote, condition, near_threshold_pct)
        for condition in rule.get("conditions", [])
    ]
    explicit_false = any((not item.blocked) and (not item.passed) for item in condition_results)
    blocked = (not explicit_false) and any(item.blocked for item in condition_results)
    passed = bool(condition_results) and all(item.passed and not item.blocked for item in condition_results)
    near = (not passed) and (not blocked) and any(item.near for item in condition_results)
    gate_allowed = market_gate_allows(rule, rules, snapshot)

    evidence = [item.text for item in condition_results]
    base_subject = {
        "code": subject["code"],
        "name": subject["name"],
        "type": subject.get("type", "unknown"),
    }

    if blocked:
        return attach_priority_score(subject, {
            "priority": "high",
            "subject": base_subject,
            "alert_type": "blocked",
            "trigger_condition": rule.get("trigger_condition", rule["id"]),
            "current_state": "缺少规则所需行情字段",
            "suggested_action": "review",
            "needs_manual_confirmation": True,
            "evidence": evidence,
            "risks": ["行情字段缺失，不能判断触发状态。"],
            "execution_boundary": "补齐QMT行情字段后重跑监测。",
            "invalidation_condition": "",
            "review_point": "确认QMT快照字段。"
        }, rules), None

    if passed and action_blocked_by_staleness(rule, rules):
        return attach_priority_score(subject, {
            "priority": "high",
            "subject": base_subject,
            "alert_type": "stale_blocked",
            "trigger_condition": rule.get("trigger_condition", rule["id"]),
            "current_state": "条件触发，但规则引用链过期，禁止买入/加仓",
            "suggested_action": "review",
            "needs_manual_confirmation": True,
            "evidence": evidence + [f"rules.staleness={rules.get('staleness', {}).get('status')}"],
            "risks": ["盘中规则引用旧上游，不能输出买入/加仓动作。"],
            "execution_boundary": "先重建 market_score/theme/target_allocation/intraday_rules，再进入操作建议模块。",
            "invalidation_condition": rule.get("invalidation_condition", ""),
            "review_point": rule.get("review_point", ""),
        }, rules), None

    if passed and not gate_allowed:
        return attach_priority_score(subject, {
            "priority": "high",
            "subject": base_subject,
            "alert_type": "gate_blocked",
            "trigger_condition": rule.get("trigger_condition", rule["id"]),
            "current_state": "价格/条件触发，但市场门禁不允许执行该类动作",
            "suggested_action": "review",
            "needs_manual_confirmation": True,
            "evidence": evidence,
            "risks": ["市场仓位或组合门禁冲突。"],
            "execution_boundary": "进入操作建议模块复核，不能直接执行。",
            "invalidation_condition": rule.get("invalidation_condition", ""),
            "review_point": rule.get("review_point", "")
        }, rules), None

    if passed:
        return attach_priority_score(subject, {
            "priority": rule.get("priority", "medium"),
            "subject": base_subject,
            "alert_type": rule.get("alert_type", "watch_trigger"),
            "trigger_condition": rule.get("trigger_condition", rule["id"]),
            "current_state": "已触发",
            "suggested_action": rule.get("suggested_action", "review"),
            "needs_manual_confirmation": True,
            "evidence": evidence,
            "risks": ["提醒不是交易指令，必须人工确认。"],
            "execution_boundary": rule.get("execution_boundary", ""),
            "invalidation_condition": rule.get("invalidation_condition", ""),
            "review_point": rule.get("review_point", "")
        }, rules), None

    if near:
        return None, {
            "subject": f'{subject["code"]} {subject["name"]}',
            "near_condition": rule.get("trigger_condition", rule["id"]),
            "watch_point": "; ".join(evidence),
        }

    return None, None


def build_report(rules: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    quotes = {normalize_code(k): v for k, v in snapshot.get("quotes", {}).items()}
    alerts: list[dict[str, Any]] = []
    near_triggers: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    monitored_quotes: list[dict[str, Any]] = []

    for subject in rules.get("subjects", []):
        code = normalize_code(subject["code"])
        quote = quotes.get(code)
        if quote is None:
            missing.append(
                {
                    "missing_content": f"quote:{code}",
                    "impact": f"{code} {subject.get('name', '')} 无法盘中判断",
                    "next_step": "补齐QMT行情快照后重跑",
                }
            )
            continue
        monitored_quotes.append(
            {
                "code": code,
                "name": subject.get("name", quote.get("name", "")),
                "type": subject.get("type", quote.get("type", "unknown")),
                "last": quote.get("last"),
                "pre_close": quote.get("pre_close"),
                "pct_chg": quote.get("pct_chg"),
                "amount_100m": quote.get("amount_100m"),
                "turnover_rate": quote.get("turnover_rate"),
                "volume_ratio": quote.get("volume_ratio"),
                "ma20": quote.get("ma20"),
                "ma60": quote.get("ma60"),
                "moneyflow_5d": quote.get("moneyflow_5d"),
                "moneyflow_20d": quote.get("moneyflow_20d"),
                "qmt_timetag": quote.get("qmt_timetag"),
                "valuation_visual": quote.get("valuation_visual"),
                "realtime_valuation_zone": quote.get("realtime_valuation_zone"),
                "valuation_report_zone": quote.get("valuation_report_zone"),
                "valuation_zone_changed": quote.get("valuation_zone_changed"),
                "trend_visual": quote.get("trend_visual"),
                "risk_markers": quote.get("risk_markers"),
                "security_stance": quote.get("security_stance"),
                "position_visual": quote.get("position_visual"),
                "allocation_bucket": quote.get("allocation_bucket"),
            }
        )
        for rule in subject.get("rules", []):
            alert, near = evaluate_rule(subject, rule, quote, rules, snapshot)
            if alert:
                alerts.append(alert)
            if near:
                near_triggers.append(near)

    alerts.sort(key=lambda item: (float(item.get("priority_score") or 0), PRIORITY_RANK.get(item["priority"], 0)), reverse=True)
    highest = alerts[0].get("priority_label", alerts[0].get("priority")) if alerts else ("low" if near_triggers else "none")
    state = "triggered" if alerts else ("no_trigger" if not missing else "blocked")
    if missing and alerts:
        state = "review_needed"

    one_line = (
        f"触发{len(alerts)}条提醒，接近触发{len(near_triggers)}条，缺失前置{len(missing)}项。"
        if alerts or near_triggers or missing
        else "未触发已定义盘中规则。"
    )
    timestamp = normalize_timestamp(snapshot.get("timestamp"))
    date_part = timestamp[:10]
    time_part = timestamp[11:]
    valuation_check = build_valuation_update_check(monitored_quotes, timestamp, date_part.replace("-", ""))
    valuation_count = int(valuation_check.get("update_required_count") or 0)
    if valuation_count:
        one_line = f"{one_line} 估值更新提示{valuation_count}项。"

    return {
        "module": "intraday_alerts",
        "version": "1.2",
        "date": date_part,
        "time": time_part,
        "generated_at": timestamp,
        "source_plan": rules.get("data_sources", []),
        "quote_source": snapshot.get("source", "unknown"),
        "market_context": snapshot.get("market_context", {}),
        "staleness": rules.get("staleness", {"status": "legacy_unknown"}),
        "monitored_quotes": monitored_quotes,
        "summary": {
            "alert_state": state,
            "highest_priority": highest,
            "one_line_conclusion": one_line,
            "valuation_update_required_count": valuation_count,
        },
        "alerts": alerts,
        "near_triggers": near_triggers,
        "missing_preconditions": missing,
        "valuation_update_check": valuation_check,
        "decision_log_entry": (
            f"{timestamp} 盘中提醒：最高优先级={highest}；触发={len(alerts)}；"
            f"接近触发={len(near_triggers)}；缺失={len(missing)}；"
            f"valuation_updates={valuation_count}；"
            f"staleness={rules.get('staleness', {}).get('status', 'legacy_unknown')}。"
        ),
    }


def md_table_alerts(alerts: list[dict[str, Any]]) -> str:
    if not alerts:
        return "| 无 | 无 | no_trigger | 无 | 未触发 | log_only | 是 |"
    rows = []
    for item in alerts:
        subject = item["subject"]
        rows.append(
            "| {priority}({score}) | {code} {name} | {alert_type} | {condition} | {state} | {action} | 是 |".format(
                priority=item.get("priority_label", item["priority"]),
                score=item.get("priority_score", "-"),
                code=subject["code"],
                name=subject["name"],
                alert_type=item["alert_type"],
                condition=item["trigger_condition"],
                state=item["current_state"],
                action=item["suggested_action"],
            )
        )
    return "\n".join(rows)


def fmt_value(value: Any) -> str:
    if value is None:
        return "缺失"
    if isinstance(value, (int, float)):
        return f"{value:.2f}"
    return str(value)


def md_table_quotes(quotes: list[dict[str, Any]]) -> str:
    if not quotes:
        return "| 无 | 无 | 缺失 | 缺失 | 缺失 | 缺失 | 缺失 | 缺失 | 缺失 |"
    rows = []
    for item in quotes:
        rows.append(
            "| {code} {name} | {last} | {pct}% | {amount} | {ma20} | {ma60} | {mf5} | {mf20} | {time} |".format(
                code=item["code"],
                name=item["name"],
                last=fmt_value(item.get("last")),
                pct=fmt_value(item.get("pct_chg")),
                amount=fmt_value(item.get("amount_100m")),
                ma20=fmt_value(item.get("ma20")),
                ma60=fmt_value(item.get("ma60")),
                mf5=fmt_value(item.get("moneyflow_5d")),
                mf20=fmt_value(item.get("moneyflow_20d")),
                time=fmt_value(item.get("qmt_timetag")),
            )
        )
    return "\n".join(rows)


def md_table_valuation_updates(items: list[dict[str, Any]]) -> str:
    if not items:
        return "| 无 | 无 | ok | 无需更新 |"
    rows = []
    for item in items:
        rows.append(
            "| {code} {name} | {severity} | {reason} | {next_step} |".format(
                code=item.get("code", ""),
                name=item.get("name", ""),
                severity=item.get("severity", ""),
                reason="；".join(str(text) for text in item.get("reasons", [])),
                next_step=item.get("suggested_next_step", ""),
            )
        )
    return "\n".join(rows)


def render_markdown(report: dict[str, Any]) -> str:
    alerts = report["alerts"]
    near = report["near_triggers"]
    missing = report["missing_preconditions"]

    detail_sections = []
    for item in alerts:
        subject = item["subject"]
        detail_sections.append(
            f"""### 提醒：{subject['code']} {subject['name']}

- 标的/范围：{subject['code']} {subject['name']}
- 提醒类型：{item['alert_type']}
- 优先级：{item['priority']}
- 当前状态：{item['current_state']}
- 建议动作：{item['suggested_action']}
- 是否需要人工确认：是

触发条件：

- {item['trigger_condition']}

依据：

{chr(10).join(f"- {text}" for text in item.get('evidence', []))}

风险：

{chr(10).join(f"- {text}" for text in item.get('risks', []))}

如果执行：

- 操作边界：{item.get('execution_boundary', '')}
- 失效条件：{item.get('invalidation_condition', '')}
- 复盘点：{item.get('review_point', '')}
"""
        )

    near_rows = (
        "\n".join(f"| {item['subject']} | {item['near_condition']} | {item['watch_point']} |" for item in near)
        if near
        else "| 无 | 无 | 无 |"
    )
    missing_rows = (
        "\n".join(f"| {item['missing_content']} | {item['impact']} | {item['next_step']} |" for item in missing)
        if missing
        else "| 无 | 无 | 无 |"
    )

    return f"""# 盘中提醒

日期：{report['date']}
时间：{report['generated_at']}
版本：v1.1
来源计划：

{chr(10).join(f"- `{source}`" for source in report.get('source_plan', []))}

## 1. 总体状态

提醒状态：{report['summary']['alert_state']}
最高优先级：{report['summary']['highest_priority']}

一句话结论：

> {report['summary']['one_line_conclusion']}

## 2. 提醒清单

### 2.1 监控行情

| 标的 | 当前价 | 涨跌幅 | 成交额(亿元) | MA20 | MA60 | 5日资金流 | 20日资金流 | 行情时间 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
{md_table_quotes(report.get('monitored_quotes', []))}

### 2.2 触发状态

| 优先级 | 标的/范围 | 提醒类型 | 触发条件 | 当前状态 | 建议动作 | 人工确认 |
| --- | --- | --- | --- | --- | --- | --- |
{md_table_alerts(alerts)}

## 3. 单条提醒详情

{chr(10).join(detail_sections) if detail_sections else '无触发详情。'}

## 4. 未触发但接近条件

| 标的/范围 | 接近的条件 | 需要观察 |
| --- | --- | --- |
{near_rows}

## 5. 缺失前置条件

| 缺失内容 | 影响 | 下一步 |
| --- | --- | --- |
{missing_rows}

## 6. 估值更新检查

状态：{report.get('valuation_update_check', {}).get('status', 'unknown')}

| 标的 | 状态 | 原因 | 下一步 |
| --- | --- | --- | --- |
{md_table_valuation_updates((report.get('valuation_update_check') or {}).get('items', []))}

## 7. 决策日志条目

```text
{report['decision_log_entry']}
```
"""


def write_report(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = report["generated_at"]
    json_path = output_dir / f"intraday_alert_{timestamp}.json"
    md_path = output_dir / f"intraday_alert_{timestamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quotes-file", required=True, type=Path, help="QMT/manual quote snapshot JSON")
    parser.add_argument("--rules-file", default=DEFAULT_RULES, type=Path, help="Intraday rules JSON")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, type=Path, help="Output directory")
    parser.add_argument("--dry-run", action="store_true", help="Print report JSON without writing files")
    args = parser.parse_args(argv)

    rules = read_json(args.rules_file)
    snapshot = read_json(args.quotes_file)
    report = build_report(rules, snapshot)

    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    md_path, json_path = write_report(report, args.output_dir)
    print(json.dumps({"created": [md_path.as_posix(), json_path.as_posix()]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
