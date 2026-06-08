#!/usr/bin/env python3
"""Generate a ratio-only action plan from latest research artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from project_utils import ROOT, abs_path, file_sha256, latest_for_module, load_latest_index, read_json, rel_path, write_json


ACTION_DIR = ROOT / "research" / "actions"
DECISION_LOG = ROOT / "research" / "logs" / "decision_log.md"


def dep_record(module: str, path: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "module": module,
        "path": path,
        "generated_at": data.get("generated_at"),
        "basis_trade_date": data.get("basis_trade_date") or data.get("date"),
        "sha256": file_sha256(abs_path(path)),
    }


def pct(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}%"
    except (TypeError, ValueError):
        return ""


def pp_range(low: float, high: float) -> str:
    return f"{low:.1f}pp至{high:.1f}pp"


def load_latest(module: str, index: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    record = latest_for_module(module, index)
    if not record:
        raise RuntimeError(f"missing latest module: {module}")
    path = record["path"]
    return path, read_json(abs_path(path), {})


def bucket_line(item: dict[str, Any]) -> str:
    return f"{item.get('label')}: 目标{pct(item.get('target_pct'))}，当前{pct(item.get('actual_pct'))}，偏离{float(item.get('gap_pct', 0)):+.2f}pp"


def render_markdown(plan: dict[str, Any]) -> str:
    pre = plan["preconditions"]
    action_rows = []
    for item in plan["actions"]:
        action_rows.append(
            "| {priority} | {action} | {subject} | {current} | {change} | {target} | {strength} |".format(
                priority=item["priority"],
                action=item["action_type"],
                subject=f"{item['subject']['name']}（{item['subject']['code']}）" if item["subject"].get("code") else item["subject"]["name"],
                current=item["current_position"],
                change=item["suggested_change"],
                target=item["target_position"],
                strength=item["recommendation_strength"],
            )
        )
    no_action_rows = []
    for item in plan["no_action_list"]:
        no_action_rows.append(f"| {item['subject']} | {item['reason']} | {'；'.join(item.get('watch_points', []))} |")
    research_rows = []
    for item in plan["research_first_list"]:
        research_rows.append(f"| {item['subject']} | {item['missing_content']} | {item['why_it_blocks_action']} | {item['next_step']} |")
    trigger_rows = []
    for item in plan["intraday_triggers"]:
        trigger_rows.append(f"| {item['subject']} | {item['trigger_condition']} | {item['action_after_trigger']} |")

    return f"""# 2026-06-08 最新操作建议（比例版）

生成时间：{plan['generated_at']}

口径：只使用仓位比例、百分比和百分点；不使用金额、市值、盈亏金额或股数。

## 总体结论

{plan['summary']['one_line_conclusion']}

| 状态 | 强度 |
| --- | --- |
| {plan['summary']['action_state']} | {plan['summary']['recommendation_strength']} |

## 前置条件

| 模块 | 结论 | 对操作的影响 |
| --- | --- | --- |
| 市场仓位 | {pre['market_position']['conclusion']} | {pre['market_position']['impact']} |
| 主线评级 | {pre['theme_rating']['conclusion']} | {pre['theme_rating']['impact']} |
| 组合偏离 | {pre['portfolio_deviation']['conclusion']} | {pre['portfolio_deviation']['impact']} |
| 拥挤/质量 | {pre['crowding_risk']['conclusion']} | {pre['crowding_risk']['impact']} |
| 硬约束 | {pre['hard_constraints']['conclusion']} | {pre['hard_constraints']['impact']} |

## 操作清单

| 优先级 | 动作 | 对象 | 当前 | 建议变化 | 目标 | 强度 |
| --- | --- | --- | --- | --- | --- | --- |
{chr(10).join(action_rows)}

## 不操作清单

| 对象 | 原因 | 观察点 |
| --- | --- | --- |
{chr(10).join(no_action_rows)}

## 先补数据/研究

| 对象 | 缺口 | 为什么影响操作 | 下一步 |
| --- | --- | --- | --- |
{chr(10).join(research_rows)}

## 盘中触发

| 对象 | 条件 | 触发后动作 |
| --- | --- | --- |
{chr(10).join(trigger_rows)}

## 风险

{chr(10).join(f"- {item}" for item in plan['risks'])}

## 硬约束

{chr(10).join(f"- {item}" for item in plan['triggered_hard_constraints'])}

## 与上一版相比

{chr(10).join(f"- {item}" for item in plan['comparison_with_previous']['main_changes'])}

变化原因：

{chr(10).join(f"- {item}" for item in plan['comparison_with_previous']['change_reasons'])}

## 来源文件

{chr(10).join(f"- `{item['path']}`" for item in plan['dependencies']['required'])}
"""


def build_plan(index: dict[str, Any], generated_at: str) -> dict[str, Any]:
    market_path, market = load_latest("market_score", index)
    theme_path, theme = load_latest("theme_review", index)
    portfolio_path, portfolio = load_latest("portfolio_snapshot", index)
    allocation_path, allocation = load_latest("target_allocation", index)
    intraday_path, intraday = load_latest("intraday_rules", index)

    market_summary = market.get("summary") or {}
    alloc_summary = allocation.get("summary") or {}
    actual = allocation.get("actual_allocation_overlay") or {}
    buckets = {item["key"]: item for item in actual.get("buckets", []) if isinstance(item, dict) and item.get("key")}

    equity_actual = float(actual.get("actual_equity_pct") or (portfolio.get("summary") or {}).get("equity_weight_pct") or 0)
    cash_actual = float(actual.get("actual_cash_short_pct") or (portfolio.get("summary") or {}).get("bond_cash_weight_pct") or 0)
    equity_high = 45.0
    equity_center = 42.5
    reduce_to_high = max(0.0, equity_actual - equity_high)
    reduce_to_center = max(0.0, equity_actual - equity_center)
    cash_to_high = max(0.0, 55.0 - cash_actual)
    cash_to_center = max(0.0, 57.5 - cash_actual)

    deps = [
        dep_record("market_score", market_path, market),
        dep_record("theme_review", theme_path, theme),
        dep_record("portfolio_snapshot", portfolio_path, portfolio),
        dep_record("target_allocation", allocation_path, allocation),
        dep_record("intraday_rules", intraday_path, intraday),
    ]

    bucket_notes = [bucket_line(item) for item in buckets.values()]
    source_files = {
        "market_position": market_path,
        "theme_registry": theme_path,
        "etf_profiles": [],
        "stock_profiles": [],
        "portfolio_analysis": portfolio_path,
        "decision_log": rel_path(DECISION_LOG),
        "target_allocation": allocation_path,
        "intraday_rules": intraday_path,
    }

    one_line = (
        f"最新目标权益为40%-45%，当前权益约{equity_actual:.2f}%，高于上沿约{reduce_to_high:.2f}pp；"
        f"建议只做风险收缩：权益先降{pp_range(reduce_to_high, reduce_to_center)}，现金/短融提高到55%-60%，暂停新增进攻仓。"
    )

    plan: dict[str, Any] = {
        "module": "action_plan",
        "version": "ratio_only_v2",
        "date": "2026-06-08",
        "generated_at": generated_at,
        "basis_trade_date": "2026-06-08",
        "session": "latest_ratio_only",
        "amount_policy": "ratio_only_no_market_value_no_profit_amount_no_total_amount_no_share_count",
        "dependencies": {
            "required": deps,
            "policy": "Action plan is invalid if market_score, theme_review, portfolio_snapshot, target_allocation, or intraday_rules is replaced by a newer file.",
        },
        "source_files": source_files,
        "summary": {
            "action_state": "actionable",
            "recommendation_strength": "Normal",
            "one_line_conclusion": one_line,
        },
        "quality": {
            "status": "warning",
            "warnings": [
                "上游QMT持仓快照存在159301成本字段异常；本操作建议只使用仓位比例和百分点，不使用异常成本或盈亏字段。"
            ],
        },
        "staleness": {
            "status": "fresh",
            "checked_at": generated_at,
        },
        "preconditions": {
            "market_position": {
                "conclusion": f"市场仓位分数{market_summary.get('market_position_score', 41)}，目标权益40%-45%，现金/短融55%-60%。",
                "impact": "不支持新增权益；当前建议只允许降风险、补现金短融和等待条件确认。",
            },
            "theme_rating": {
                "conclusion": "AI为战略A/交易B，半导体为战略A/交易C，进攻仓状态为pause_new。",
                "impact": "进攻主线只保留观察，不做新增；半导体、AI相关仓位不因长期逻辑直接加仓。",
            },
            "portfolio_deviation": {
                "conclusion": "；".join(bucket_notes),
                "impact": "优先处理其他/待清理与超配权益，核心仓低配不构成买入理由。",
            },
            "crowding_risk": {
                "conclusion": "QMT持仓快照存在159301成本字段异常，盘中规则状态为degraded。",
                "impact": "比例偏离可用；不得基于异常成本或盈亏字段给精确个券操作。",
            },
            "hard_constraints": {
                "conclusion": "市场门禁未解除、无新增A档交易主线、权益高于目标上沿。",
                "impact": "买入和加仓类建议全部暂停，风险收缩优先级高于结构补齐。",
            },
        },
        "actions": [
            {
                "priority": "high",
                "action_type": "Reduce",
                "subject": {"code": "", "name": "权益总仓", "type": "portfolio"},
                "bucket_role": "portfolio",
                "current_position": f"约{equity_actual:.2f}%",
                "suggested_change": f"先降{pp_range(reduce_to_high, reduce_to_center)}",
                "target_position": "40%-45%",
                "recommendation_strength": "Normal",
                "needs_manual_confirmation": True,
                "evidence": [
                    "market_score给出的目标权益区间为40%-45%",
                    "target_allocation显示当前权益高于目标上沿",
                    "主线研究未给出新增进攻仓条件",
                ],
                "trigger_conditions": ["人工确认后执行；优先从legacy_watch和超配桶释放比例"],
                "invalidation_conditions": ["市场仓位报告刷新且权益上限上调到50%以上", "主线研究确认新增A档交易主线且市场门禁解除"],
                "risks": ["若盘中反弹直接追买，会与最新总仓位约束冲突"],
                "review_points": ["执行后重新生成QMT只读持仓快照和目标仓位覆盖层"],
            },
            {
                "priority": "high",
                "action_type": "Add",
                "subject": {"code": "511360", "name": "现金/短融桶", "type": "bond"},
                "bucket_role": "bond_cash",
                "current_position": f"约{cash_actual:.2f}%",
                "suggested_change": f"提高{pp_range(cash_to_high, cash_to_center)}",
                "target_position": "55%-60%",
                "recommendation_strength": "Normal",
                "needs_manual_confirmation": True,
                "evidence": [
                    "目标配置要求现金/短融55%-60%",
                    "当前现金/短融低于目标区间",
                    "这是风险收缩承接仓，不是权益加仓",
                ],
                "trigger_conditions": ["权益减仓动作同步完成后承接到现金/短融桶"],
                "invalidation_conditions": ["目标仓位刷新且现金/短融目标下调"],
                "risks": ["短融工具仍需确认流动性和交易成本，但不承担权益方向风险"],
                "review_points": ["观察现金/短融比例是否回到55%-60%"],
            },
            {
                "priority": "high",
                "action_type": "Reduce",
                "subject": {"code": "", "name": "其他/待清理桶", "type": "portfolio"},
                "bucket_role": "theme",
                "current_position": f"约{buckets.get('legacy_watch', {}).get('actual_pct', 0):.2f}%",
                "suggested_change": "第一阶段降低8.0pp至10.0pp",
                "target_position": "阶段目标8%-10%，最终目标0%-3%",
                "recommendation_strength": "Normal",
                "needs_manual_confirmation": True,
                "evidence": [
                    "target_allocation将其他/待清理桶目标设为0%",
                    "该桶是当前权益超配的主要来源",
                    "弱势市场下C/D主题和遗留暴露不应占用主仓位",
                ],
                "trigger_conditions": ["优先检查流动性、税费和是否已触发个券失效条件"],
                "invalidation_conditions": ["单个标的已有最新档案明确升级为当前主线且目标仓位被重设"],
                "risks": ["一次性调整过快可能错过反抽；因此建议分阶段而不是一次清零"],
                "review_points": ["减完第一阶段后看权益总仓是否回到45%以内"],
            },
            {
                "priority": "medium",
                "action_type": "Reduce",
                "subject": {"code": "", "name": "进攻主线桶", "type": "portfolio"},
                "bucket_role": "offensive",
                "current_position": f"约{buckets.get('attack_mainline', {}).get('actual_pct', 0):.2f}%",
                "suggested_change": "如清理legacy后权益仍高于45%，再降低1.0pp至3.0pp",
                "target_position": "5%-8%",
                "recommendation_strength": "Weak",
                "needs_manual_confirmation": True,
                "evidence": [
                    "进攻桶高于目标中枢",
                    "AI交易评级B、半导体交易评级C",
                    "市场门禁为pause_new",
                ],
                "trigger_conditions": ["legacy_watch清理后权益仍超目标，或代表ETF/个股继续破位"],
                "invalidation_conditions": ["AI/半导体交易评级恢复A且市场仓位上限提高"],
                "risks": ["战略主线未破坏，不能把交易降级误读为长期否定"],
                "review_points": ["只做压缩，不做反向加仓"],
            },
            {
                "priority": "medium",
                "action_type": "Watch",
                "subject": {"code": "", "name": "防御桶", "type": "portfolio"},
                "bucket_role": "defensive",
                "current_position": f"约{buckets.get('defense', {}).get('actual_pct', 0):.2f}%",
                "suggested_change": "暂不优先压缩；若权益仍高于45%，再评估降低1.0pp至3.0pp",
                "target_position": "12%-16%",
                "recommendation_strength": "Weak",
                "needs_manual_confirmation": True,
                "evidence": [
                    "防御桶高于目标中枢但承担弱势环境缓冲作用",
                    "优先级低于legacy_watch清理",
                ],
                "trigger_conditions": ["红利、金融、医药等防御方向放量滞涨或组合仍超权益上限"],
                "invalidation_conditions": ["市场继续走弱且防御资产仍明显强于权益整体"],
                "risks": ["防御仓也属于权益，不能替代现金/短融防守锚"],
                "review_points": ["区分防御权益和现金短融，不把防御仓当现金"],
            },
        ],
        "no_action_list": [
            {
                "subject": "宽基/核心底仓",
                "reason": "market_position_not_supportive",
                "watch_points": ["虽然核心桶低配，但总权益已经超目标上沿", "等待市场仓位上限上调后再讨论补核心"],
            },
            {
                "subject": "AI、半导体、机器人等进攻方向",
                "reason": "condition_not_triggered",
                "watch_points": ["市场门禁仍为pause_new", "半导体交易评级为C", "AI交易评级为B，不做新增"],
            },
            {
                "subject": "低位但未触发右侧确认的持仓",
                "reason": "risk_too_high",
                "watch_points": ["不因亏损比例或短期低估直接补仓", "先处理总仓位超配"],
            },
        ],
        "research_first_list": [
            {
                "subject": "159301 公用事业ETF华夏",
                "missing_content": "portfolio_analysis",
                "why_it_blocks_action": "QMT成本字段异常，已排除成本/盈亏口径，不能用于精确个券级操作。",
                "next_step": "刷新QMT持仓快照或人工核对该标的成本字段；本次仅使用仓位比例。",
            },
            {
                "subject": "515880 通信ETF国泰",
                "missing_content": "portfolio_analysis",
                "why_it_blocks_action": "QMT返回名称为代码 fallback，说明名称映射仍需修复。",
                "next_step": "补充代码名称映射后再进入个券级跟踪；当前比例很低，不影响总仓位动作。",
            },
        ],
        "intraday_triggers": [
            {
                "subject": "权益总仓",
                "trigger_condition": "执行后权益仍高于45%",
                "action_after_trigger": "review",
                "needs_manual_confirmation": True,
            },
            {
                "subject": "现金/短融桶",
                "trigger_condition": "现金/短融仍低于55%",
                "action_after_trigger": "review",
                "needs_manual_confirmation": True,
            },
            {
                "subject": "市场门禁",
                "trigger_condition": "最新市场仓位报告将权益上限上调到50%以上，且主线研究确认至少一个交易A主线",
                "action_after_trigger": "cancel",
                "needs_manual_confirmation": True,
            },
            {
                "subject": "风险继续扩大",
                "trigger_condition": "主要指数继续破位、资金流继续为负、进攻代表ETF继续弱于宽基",
                "action_after_trigger": "review",
                "needs_manual_confirmation": True,
            },
        ],
        "risks": [
            "本建议只基于比例和最新已落盘研究，不包含实时成交可行性、盘口流动性或交易费用测算。",
            "QMT持仓快照存在单一标的数据质量错误，因此所有个券级精确建议降级。",
            "战略主线和交易主线要分开理解：AI/半导体长期逻辑仍需跟踪，但当前交易条件不支持新增。",
            "若今天盘后市场数据更新，必须重新生成市场仓位、目标仓位和操作建议。",
        ],
        "triggered_hard_constraints": [
            "当前权益约54.10%，高于40%-45%目标区间。",
            "进攻仓暂停新增。",
            "没有新增A档交易主线作为扩大权益的依据。",
            "其他/待清理桶显著高于理想目标。",
        ],
        "comparison_with_previous": {
            "previous_date": "2026-06-03",
            "main_changes": [
                "从局部主题/个股操作建议，升级为全组合风险收缩建议。",
                "总权益目标从旧版本参考框架切换为2026-06-08目标仓位：40%-45%。",
                "新增现金/短融目标55%-60%和legacy_watch第一优先清理规则。",
            ],
            "change_reasons": [
                "2026-06-08市场仓位分数降到弱势震荡区间。",
                "主线研究显示AI交易B、半导体交易C，新增进攻条件不足。",
                "QMT只读持仓显示权益比例高于目标上沿，且偏离集中在legacy_watch和超配权益桶。",
            ],
        },
    }

    plan["decision_log_entry"] = (
        f"2026-06-08 最新操作建议（比例版）：生成 action_plan_{generated_at}_latest_ratio_only.md/json；"
        f"只使用比例和百分点，不使用金额、市值、盈亏金额或股数；结论为权益从约{equity_actual:.2f}%先降低"
        f"{pp_range(reduce_to_high, reduce_to_center)}，目标回到40%-45%，现金/短融提高到55%-60%，暂停新增进攻仓，优先清理其他/待清理桶。"
    )
    return plan


def append_decision_log(entry: str, md_path: Path, json_path: Path, deps: list[dict[str, Any]]) -> None:
    lines = [
        "",
        f"## {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 最新操作建议（比例版）",
        "",
        "- 决策类型：action_plan",
        f"- 生成文件：`{rel_path(md_path)}`、`{rel_path(json_path)}`",
        "- 读取前置文件：" + "、".join(f"`{item['path']}`" for item in deps),
        "- 金额口径：只使用比例和百分点，不使用金额、市值、盈亏金额或股数。",
        f"- 结论：{entry}",
        "",
    ]
    DECISION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DECISION_LOG.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", help="Override generated_at timestamp, YYYY-MM-DD_HHMMSS.")
    parser.add_argument("--no-log", action="store_true", help="Do not append decision_log.md.")
    args = parser.parse_args(argv)

    generated_at = args.timestamp or datetime.now().strftime("%Y-%m-%d_%H%M%S")
    index = load_latest_index()
    plan = build_plan(index, generated_at)

    stem = f"action_plan_{generated_at}_latest_ratio_only"
    json_path = ACTION_DIR / f"{stem}.json"
    md_path = ACTION_DIR / f"{stem}.md"
    write_json(json_path, plan)
    md_path.write_text(render_markdown(plan), encoding="utf-8")
    if not args.no_log:
        append_decision_log(plan["decision_log_entry"], md_path, json_path, plan["dependencies"]["required"])

    print(
        json.dumps(
            {
                "created": [rel_path(md_path), rel_path(json_path)],
                "summary": plan["summary"]["one_line_conclusion"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
