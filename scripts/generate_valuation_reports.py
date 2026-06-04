#!/usr/bin/env python3
"""Generate valuation zone reports and sync intraday battle-map rules."""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import tushare as ts


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "research" / "valuations"
ALERT_RULES = ROOT / "research" / "alerts" / "intraday_rules.json"
PORTFOLIO_DIR = ROOT / "research" / "portfolio"

ZONE_COLORS = {
    "undervalued_observe": "#2f9e44",
    "reasonable_allocation": "#74b816",
    "expensive": "#f59f00",
    "crowded_risk": "#e03131",
}

ZONE_LABELS = {
    "undervalued_observe": "低估观察区",
    "reasonable_allocation": "合理配置区",
    "expensive": "偏贵区",
    "crowded_risk": "拥挤/风险区",
}


@dataclass(frozen=True)
class Target:
    code: str
    name: str
    asset_type: str
    group: str
    role: str
    monitor_role: str
    target_position_range: str
    benchmark: str | None = None
    benchmark_name: str | None = None


TARGETS = [
    Target("510300.SH", "沪深300ETF华泰柏瑞", "broad_etf", "核心宽基", "核心仓", "沪深300核心观察", "0%-20%", "000300.SH", "沪深300"),
    Target("510500.SH", "中证500ETF南方", "broad_etf", "核心宽基", "核心仓", "中证500核心观察", "0%-15%", "000905.SH", "中证500"),
    Target("159915.SZ", "创业板ETF易方达", "broad_etf", "核心宽基", "核心/成长弹性仓", "创业板核心观察", "0%-10%", "399006.SZ", "创业板指"),
    Target("159558.SZ", "半导体设备ETF易方达", "theme_etf", "半导体主线", "进攻仓观察", "半导体设备进攻观察", "0%-2%"),
    Target("588200.SH", "科创芯片ETF嘉实", "theme_etf", "半导体主线", "进攻仓观察", "科创芯片进攻观察", "0%-2%"),
    Target("001280.SZ", "中国铀业", "stock", "战略资源观察", "观察股", "战略资源观察股", "0%-1%"),
    Target("601318.SH", "中国平安", "stock", "红利金融观察", "观察股", "红利金融观察股", "0%-3%"),
]


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rel_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def tushare_client():
    load_env()
    token = os.environ.get("TUSHARE_TOKEN")
    if not token:
        raise RuntimeError("TUSHARE_TOKEN is missing. Copy .env.example to .env and configure the token.")
    ts.set_token(token)
    return ts.pro_api()


def latest_complete_trade_date(pro: Any, today: datetime | None = None) -> str:
    today = today or datetime.now()
    start = (today - timedelta(days=14)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")
    cal = pro.trade_cal(exchange="SSE", start_date=start, end_date=end)
    cal = cal.sort_values("cal_date")
    today_row = cal[cal["cal_date"].eq(end)]
    if not today_row.empty and int(today_row.iloc[-1]["is_open"]) == 1:
        return str(today_row.iloc[-1]["pretrade_date"])
    open_days = cal[cal["is_open"].eq(1)]
    return str(open_days.iloc[-1]["cal_date"])


def pct_rank(series: pd.Series, value: float | None) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if value is None or clean.empty:
        return None
    return round(float((clean <= value).sum() / len(clean) * 100), 2)


def finite(value: Any) -> float | None:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(num) or math.isinf(num):
        return None
    return num


def quantile(series: pd.Series, q: float) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    return round(float(clean.quantile(q)), 4)


def zone_key(value: float, b20: float, b50: float, b80: float) -> str:
    if value <= b20:
        return "undervalued_observe"
    if value <= b50:
        return "reasonable_allocation"
    if value <= b80:
        return "expensive"
    return "crowded_risk"


def build_zones_from_boundaries(low: float, b20: float, b50: float, b80: float, high: float) -> list[dict[str, Any]]:
    bounds = [low, b20, b50, b80, high]
    for idx in range(1, len(bounds)):
        if bounds[idx] <= bounds[idx - 1]:
            bounds[idx] = bounds[idx - 1] + 0.0001
    keys = ["undervalued_observe", "reasonable_allocation", "expensive", "crowded_risk"]
    return [
        {
            "key": key,
            "label": ZONE_LABELS[key],
            "min": round(bounds[idx], 4),
            "max": round(bounds[idx + 1], 4),
            "color": ZONE_COLORS[key],
        }
        for idx, key in enumerate(keys)
    ]


def build_price_position_zones(close_series: pd.Series, current: float) -> tuple[list[dict[str, Any]], str]:
    clean = pd.to_numeric(close_series, errors="coerce").dropna()
    if len(clean) < 20:
        raise RuntimeError("Not enough price history to build valuation zones.")
    q05 = min(quantile(clean, 0.05), current)
    q20 = quantile(clean, 0.20)
    q50 = quantile(clean, 0.50)
    q80 = quantile(clean, 0.80)
    q95 = max(quantile(clean, 0.95), current)
    zones = build_zones_from_boundaries(q05, q20, q50, q80, q95)
    return zones, zone_key(current, q20, q50, q80)


def latest_portfolio_weights() -> dict[str, float]:
    files = sorted(PORTFOLIO_DIR.glob("portfolio_snapshot_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return {}
    snap = read_json(files[0], {})
    weights: dict[str, float] = {}
    for item in snap.get("holdings", []):
        code = str(item.get("code", "")).strip()
        weight = finite(item.get("weight_pct"))
        if code and weight is not None:
            weights[code] = weight
    return weights


def fund_daily(pro: Any, code: str, start: str, end: str) -> pd.DataFrame:
    df = pro.fund_daily(ts_code=code, start_date=start, end_date=end)
    if df.empty:
        raise RuntimeError(f"No fund_daily data for {code}.")
    return df.sort_values("trade_date")


def fund_nav(pro: Any, code: str, start: str, end: str) -> pd.DataFrame:
    try:
        df = pro.fund_nav(ts_code=code, start_date=start, end_date=end)
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df
    return df.sort_values("nav_date")


def stock_daily_basic(pro: Any, code: str, start: str, end: str) -> pd.DataFrame:
    df = pro.daily_basic(ts_code=code, start_date=start, end_date=end)
    if df.empty:
        raise RuntimeError(f"No daily_basic data for {code}.")
    return df.sort_values("trade_date")


def stock_daily(pro: Any, code: str, start: str, end: str) -> pd.DataFrame:
    df = pro.daily(ts_code=code, start_date=start, end_date=end)
    if df.empty:
        raise RuntimeError(f"No daily data for {code}.")
    return df.sort_values("trade_date")


def moneyflow_sums(pro: Any, code: str, end: str) -> tuple[float | None, float | None]:
    start = (datetime.strptime(end, "%Y%m%d") - timedelta(days=45)).strftime("%Y%m%d")
    try:
        df = pro.moneyflow(ts_code=code, start_date=start, end_date=end)
    except Exception:
        return None, None
    if df.empty or "net_mf_amount" not in df.columns:
        return None, None
    df = df.sort_values("trade_date")
    values = pd.to_numeric(df["net_mf_amount"], errors="coerce")
    return round(float(values.tail(5).sum()), 2), round(float(values.tail(20).sum()), 2)


def index_valuation(pro: Any, index_code: str, start: str, end: str) -> dict[str, Any]:
    try:
        df = pro.index_dailybasic(ts_code=index_code, start_date=start, end_date=end)
    except Exception:
        return {"available": False, "reason": "index_dailybasic unavailable"}
    if df.empty:
        return {"available": False, "reason": "index_dailybasic empty"}
    df = df.sort_values("trade_date")
    latest = df.iloc[-1]
    pe = finite(latest.get("pe_ttm"))
    pb = finite(latest.get("pb"))
    return {
        "available": True,
        "date": str(latest.get("trade_date")),
        "pe_ttm": pe,
        "pb": pb,
        "pe_ttm_percentile": pct_rank(df["pe_ttm"], pe),
        "pb_percentile": pct_rank(df["pb"], pb),
        "sample_days": int(len(df)),
    }


def stock_metric_price_bands(df: pd.DataFrame, current: float, asset_type: str) -> tuple[list[dict[str, Any]], str, list[str]]:
    latest = df.iloc[-1]
    if asset_type == "stock_financial":
        metrics = [("pb", 0.55), ("pe_ttm", 0.35), ("ps_ttm", 0.10)]
    else:
        metrics = [("pe_ttm", 0.45), ("ps_ttm", 0.30), ("pb", 0.25)]
    boundaries = {"q05": [], "q20": [], "q50": [], "q80": [], "q95": []}
    evidence: list[str] = []
    for metric, weight in metrics:
        latest_metric = finite(latest.get(metric))
        series = pd.to_numeric(df.get(metric), errors="coerce").dropna()
        series = series[series > 0]
        if latest_metric is None or latest_metric <= 0 or len(series) < 30:
            continue
        for key, q in [("q05", 0.05), ("q20", 0.20), ("q50", 0.50), ("q80", 0.80), ("q95", 0.95)]:
            target_multiple = float(series.quantile(q))
            boundaries[key].append(current * target_multiple / latest_metric * weight)
        evidence.append(f"{metric} current={latest_metric:.2f}, percentile={pct_rank(series, latest_metric)}%")
    if not boundaries["q20"]:
        zones, key = build_price_position_zones(df["close"], current)
        return zones, key, ["估值指标样本不足，降级为价格位置代理。"]
    summed = {key: round(float(sum(values)), 4) for key, values in boundaries.items()}
    q05 = min(summed["q05"], current)
    q95 = max(summed["q95"], current)
    zones = build_zones_from_boundaries(q05, summed["q20"], summed["q50"], summed["q80"], q95)
    return zones, zone_key(current, summed["q20"], summed["q50"], summed["q80"]), evidence


def zone_text(zones: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"| {zone['label']} | {zone['min']:.4f}-{zone['max']:.4f} | {zone['color']} |"
        for zone in zones
    )


def render_report(report: dict[str, Any]) -> str:
    visual = report["valuation_visual"]
    idx = report.get("index_valuation") or {}
    valuation_rows = []
    if idx.get("available"):
        valuation_rows.append(f"| 跟踪指数PE_TTM | {idx.get('pe_ttm')} | {idx.get('pe_ttm_percentile')}% | {idx.get('date')} |")
        valuation_rows.append(f"| 跟踪指数PB | {idx.get('pb')} | {idx.get('pb_percentile')}% | {idx.get('date')} |")
    else:
        valuation_rows.append(f"| 跟踪指数估值 | 缺失 | - | {idx.get('reason', 'not applicable')} |")
    for item in report.get("stock_valuation_metrics", []):
        valuation_rows.append(f"| {item['metric']} | {item['value']} | {item['percentile']}% | {item['date']} |")
    valuation_rows_text = "\n".join(valuation_rows)

    return f"""# 估值报告：{report['name']}

代码：{report['code']}
日期：{report['date']}
生成时间：{report['generated_at']}
数据基准日：{report['basis_date']}
资产类型：{report['asset_type']}
估值可信度：{report['confidence']}
边界：本报告只给估值分段和监测输入，不生成组合级买卖动作。

## 1. 核心结论

当前价格/净值位置：{visual['current_value']:.4f}
当前位置：{visual['current_zone_label']}
估值口径：{visual['basis']}

一句话结论：
> {report['one_line_conclusion']}

## 2. 可视化分段

| 分段 | 价格/净值范围 | 颜色 |
| --- | ---: | --- |
{zone_text(visual['zones'])}

## 3. 估值证据

| 指标 | 当前值 | 分位 | 日期/说明 |
| --- | ---: | ---: | --- |
{valuation_rows_text}

## 4. 趋势和监测位

| 项目 | 数值 |
| --- | ---: |
| MA20 | {report['reference_metrics'].get('ma20')} |
| MA60 | {report['reference_metrics'].get('ma60')} |
| 风控观察位 | {report['reference_metrics'].get('support')} |
| 右侧确认位 | {report['reference_metrics'].get('right_confirm')} |
| 拥挤/风险起点 | {report['reference_metrics'].get('risk_zone_start')} |

## 5. 数据缺口

{chr(10).join(f"- {item}" for item in report.get('data_gaps', [])) or "- 无重大缺口。"}

## 6. 盘中监测同步

已写入：`research/alerts/intraday_rules.json`

盘中作战地图应显示四段颜色条，并标记实时价格位置。触发提醒仍只代表需要复核，不代表自动交易。
"""


def make_report_for_etf(pro: Any, target: Target, start: str, end: str, timestamp: str, weights: dict[str, float]) -> dict[str, Any]:
    daily = fund_daily(pro, target.code, start, end)
    nav = fund_nav(pro, target.code, start, end)
    latest = daily.iloc[-1]
    current = float(latest["close"])
    zones, current_zone = build_price_position_zones(daily["close"], current)
    index_val = index_valuation(pro, target.benchmark, start, end) if target.benchmark else {"available": False, "reason": "theme index valuation not mapped"}
    ma20 = round(float(daily["close"].tail(20).mean()), 4)
    ma60 = round(float(daily["close"].tail(60).mean()), 4) if len(daily) >= 60 else None
    nav_latest = None if nav.empty else finite(nav.iloc[-1].get("unit_nav"))
    premium_discount = round((current / nav_latest - 1) * 100, 2) if nav_latest else None
    code_plain = target.code.split(".")[0]
    data_gaps = []
    if not index_val.get("available"):
        data_gaps.append("未取得可直接映射的跟踪指数长期PE/PB分位，本报告对主题ETF使用价格/净值位置代理。")
    if nav_latest is None:
        data_gaps.append("未取得最新基金单位净值，折溢价无法计算。")
    confidence = "中高" if target.asset_type == "broad_etf" and index_val.get("available") else "中低"
    basis = "跟踪指数估值 + ETF价格/净值位置" if index_val.get("available") else "ETF价格/净值位置代理"
    return {
        "module": "valuation_report",
        "version": "1.0",
        "code": target.code,
        "name": target.name,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "generated_at": timestamp,
        "basis_date": str(latest["trade_date"]),
        "asset_type": target.asset_type,
        "group": target.group,
        "role": target.role,
        "confidence": confidence,
        "one_line_conclusion": f"{target.name} 当前处于{ZONE_LABELS[current_zone]}；{basis}，最终动作需由ACTION_PLAN结合市场仓位和组合暴露决定。",
        "valuation_visual": {
            "metric": "price",
            "current_value": round(current, 4),
            "current_zone": current_zone,
            "current_zone_label": ZONE_LABELS[current_zone],
            "zones": zones,
            "basis": basis,
            "premium_discount_pct": premium_discount,
        },
        "index_valuation": index_val,
        "stock_valuation_metrics": [],
        "reference_metrics": {
            "price_date": str(latest["trade_date"]),
            "last_reference": round(current, 4),
            "ma20": ma20,
            "ma60": ma60,
            "moneyflow_5d": None,
            "moneyflow_20d": None,
            "support": zones[0]["max"],
            "right_confirm": ma60,
            "risk_zone_start": zones[3]["min"],
            "current_position_pct": weights.get(code_plain, 0),
            "target_position_range": target.target_position_range,
            "valuation_visual": None,
        },
        "data_gaps": data_gaps,
        "source": {
            "tushare": ["fund_daily", "fund_nav", "index_dailybasic"] if target.benchmark else ["fund_daily", "fund_nav"],
            "history_sample_days": int(len(daily)),
        },
    }


def make_report_for_stock(pro: Any, target: Target, start: str, end: str, timestamp: str, weights: dict[str, float]) -> dict[str, Any]:
    basic = stock_daily_basic(pro, target.code, start, end)
    price = stock_daily(pro, target.code, start, end)
    df = pd.merge(basic, price[["trade_date", "close"]], on="trade_date", suffixes=("_basic", ""))
    current = float(df.iloc[-1]["close"])
    stock_kind = "stock_financial" if target.code == "601318.SH" else "stock_industrial"
    zones, current_zone, evidence = stock_metric_price_bands(df, current, stock_kind)
    latest = df.iloc[-1]
    ma20 = round(float(df["close"].tail(20).mean()), 4)
    ma60 = round(float(df["close"].tail(60).mean()), 4) if len(df) >= 60 else None
    mf5, mf20 = moneyflow_sums(pro, target.code, end)
    code_plain = target.code.split(".")[0]
    metrics = []
    for metric in ["pe_ttm", "pb", "ps_ttm", "dv_ttm"]:
        value = finite(latest.get(metric))
        if value is None:
            continue
        metrics.append(
            {
                "metric": metric,
                "value": round(value, 4),
                "percentile": pct_rank(df[metric], value),
                "date": str(latest["trade_date"]),
            }
        )
    data_gaps = []
    if len(df) < 720:
        data_gaps.append("历史样本不足3年，长期估值分位可信度下降。")
    if target.code == "001280.SZ":
        data_gaps.append("中国铀业上市样本短，估值区间需结合铀价、中报和流通盘变化复核。")
    basis = "PE/PB/PS历史分位映射价格区间"
    confidence = "中" if len(df) >= 240 else "中低"
    return {
        "module": "valuation_report",
        "version": "1.0",
        "code": target.code,
        "name": target.name,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "generated_at": timestamp,
        "basis_date": str(latest["trade_date"]),
        "asset_type": target.asset_type,
        "group": target.group,
        "role": target.role,
        "confidence": confidence,
        "one_line_conclusion": f"{target.name} 当前处于{ZONE_LABELS[current_zone]}；估值区间来自{basis}，不是组合级买卖指令。",
        "valuation_visual": {
            "metric": "price",
            "current_value": round(current, 4),
            "current_zone": current_zone,
            "current_zone_label": ZONE_LABELS[current_zone],
            "zones": zones,
            "basis": basis,
            "evidence": evidence,
        },
        "index_valuation": {"available": False, "reason": "stock valuation uses daily_basic metrics"},
        "stock_valuation_metrics": metrics,
        "reference_metrics": {
            "price_date": str(latest["trade_date"]),
            "last_reference": round(current, 4),
            "ma20": ma20,
            "ma60": ma60,
            "moneyflow_5d": mf5,
            "moneyflow_20d": mf20,
            "support": zones[0]["max"],
            "right_confirm": ma60,
            "risk_zone_start": zones[3]["min"],
            "current_position_pct": weights.get(code_plain, 0),
            "target_position_range": target.target_position_range,
            "valuation_visual": None,
        },
        "data_gaps": data_gaps,
        "source": {
            "tushare": ["daily", "daily_basic", "moneyflow"],
            "history_sample_days": int(len(df)),
        },
    }


def report_filename(report: dict[str, Any], suffix: str) -> Path:
    code = report["code"].replace(".", "_")
    name = "".join(ch for ch in report["name"] if ch not in '\\/:*?"<>|')
    return OUTPUT_DIR / f"valuation_{code}_{name}_{report['generated_at']}.{suffix}"


def write_report(report: dict[str, Any]) -> tuple[Path, Path]:
    visual = report["valuation_visual"]
    report["reference_metrics"]["valuation_visual"] = visual
    md_path = report_filename(report, "md")
    json_path = report_filename(report, "json")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_report(report), encoding="utf-8")
    write_json(json_path, report)
    return md_path, json_path


def alert_rules_for_report(report: dict[str, Any], md_path: Path, json_path: Path) -> dict[str, Any]:
    ref = report["reference_metrics"]
    visual = report["valuation_visual"]
    low_max = visual["zones"][0]["max"]
    risk_min = visual["zones"][3]["min"]
    return {
        "code": report["code"],
        "name": report["name"],
        "type": "ETF" if "etf" in report["asset_type"] else "stock",
        "source_profile": rel_path(json_path),
        "source_report": rel_path(md_path),
        "group": report["group"],
        "role": report["role"],
        "ideal_position_range": ref.get("target_position_range"),
        "reference_metrics": ref,
        "rules": [
            {
                "id": f"{report['code'].replace('.', '_')}_valuation_low",
                "alert_type": "watch_trigger",
                "priority": "medium",
                "suggested_action": "wait",
                "trigger_condition": f"进入{ZONE_LABELS['undervalued_observe']}，只触发估值观察复核",
                "conditions": [{"metric": "last", "op": "<=", "value": low_max}],
                "near_threshold_pct": 1.0,
                "execution_boundary": "估值观察不等于买入；必须由ACTION_PLAN结合市场仓位、趋势和组合暴露复核。",
                "invalidation_condition": "价格重新离开低估观察区或基本面/指数估值口径恶化。",
                "review_point": "复核估值口径、趋势、资金流和最新组合偏离。",
            },
            {
                "id": f"{report['code'].replace('.', '_')}_valuation_risk",
                "alert_type": "risk_trigger",
                "priority": "high",
                "suggested_action": "review",
                "trigger_condition": f"进入{ZONE_LABELS['crowded_risk']}，触发拥挤/高估风险复核",
                "conditions": [{"metric": "last", "op": ">=", "value": risk_min}],
                "near_threshold_pct": 1.0,
                "execution_boundary": "风险提醒不等于卖出；必须由ACTION_PLAN结合持仓、趋势和市场门禁处理。",
                "invalidation_condition": "价格回落至偏贵区以下，或盈利/指数估值显著改善。",
                "review_point": "复核是否需要控制新增、减小暴露或等待盘后复盘。",
            },
        ],
    }


def sync_intraday_rules(reports: list[tuple[dict[str, Any], Path, Path]]) -> None:
    existing = read_json(ALERT_RULES, {})
    rules = {
        "module": "intraday_rules",
        "version": "1.1",
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "boundary": "Rules are alert triggers only. They do not create portfolio-level buy/sell orders and do not call any trading API.",
        "data_sources": [
            "docs/modules/INTRADAY_ALERTS.md",
            "docs/modules/VALUATION_RESEARCH.md",
            "research/market/market_score_2026-06-03_211833.json",
            "research/allocation/target_allocation_2026-06-03_211833.json",
        ]
        + [rel_path(json_path) for _, _, json_path in reports],
        "global_gate": existing.get(
            "global_gate",
            {
                "default_market_gate": "verify_only",
                "allow_add_when_market_gate": ["allow_new_risk"],
                "allow_watch_when_market_gate": ["verify_only", "allow_new_risk"],
                "risk_reduce_always_allowed": True,
                "manual_confirmation_required": True,
            },
        ),
        "subjects": [alert_rules_for_report(report, md_path, json_path) for report, md_path, json_path in reports],
    }
    write_json(ALERT_RULES, rules)


def generate() -> list[tuple[dict[str, Any], Path, Path]]:
    pro = tushare_client()
    end = latest_complete_trade_date(pro)
    start = (datetime.strptime(end, "%Y%m%d") - timedelta(days=365 * 3 + 20)).strftime("%Y%m%d")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    weights = latest_portfolio_weights()
    written: list[tuple[dict[str, Any], Path, Path]] = []
    for target in TARGETS:
        if target.asset_type.endswith("etf"):
            report = make_report_for_etf(pro, target, start, end, timestamp, weights)
        else:
            report = make_report_for_stock(pro, target, start, end, timestamp, weights)
        md_path, json_path = write_report(report)
        written.append((report, md_path, json_path))
    sync_intraday_rules(written)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    written = generate()
    print(json.dumps({"created": [p.as_posix() for _, md, js in written for p in (md, js)], "updated": ALERT_RULES.as_posix()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
