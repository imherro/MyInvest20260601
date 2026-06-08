#!/usr/bin/env python3
"""Create a ratio-only portfolio snapshot from QMT's read-only trading API."""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from project_utils import latest_for_module, read_json as read_project_json


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "research" / "portfolio"
ALERT_RULES = ROOT / "research" / "alerts" / "intraday_rules.json"
DECISION_LOG = ROOT / "research" / "logs" / "decision_log.md"

SENSITIVE_OUTPUT_FIELDS = {
    "account_id",
    "cash",
    "frozen_cash",
    "market_value",
    "total_asset",
    "volume",
    "can_use_volume",
    "frozen_volume",
    "on_road_volume",
    "yesterday_volume",
    "profit_amount",
    "cost_amount",
}

ETF_PREFIXES = ("159", "510", "511", "512", "513", "515", "516", "517", "518", "560", "561", "562", "563", "588")

BUCKET_BY_CODE = {
    "511360": "cash_short",
    "510300": "core_base",
    "510500": "core_base",
    "159915": "core_base",
    "159201": "core_base",
    "002352": "core_base",
    "159819": "attack_mainline",
    "588200": "attack_mainline",
    "159558": "attack_mainline",
    "001280": "attack_mainline",
    "159326": "attack_mainline",
    "159667": "attack_mainline",
    "002241": "attack_mainline",
    "688333": "attack_mainline",
    "002625": "attack_mainline",
    "300627": "attack_mainline",
    "002920": "attack_mainline",
    "688439": "attack_mainline",
    "603596": "attack_mainline",
    "562800": "attack_mainline",
    "510880": "defense",
    "159301": "defense",
    "601318": "defense",
    "512880": "defense",
    "159842": "defense",
    "512070": "defense",
    "159992": "defense",
    "513120": "defense",
    "603087": "defense",
    "300760": "defense",
    "513180": "legacy_watch",
    "513050": "legacy_watch",
    "159378": "legacy_watch",
    "562500": "legacy_watch",
    "159869": "legacy_watch",
    "002258": "legacy_watch",
    "002041": "legacy_watch",
    "603903": "legacy_watch",
    "516150": "legacy_watch",
    "512400": "legacy_watch",
}

CATEGORY_BY_BUCKET = {
    "cash_short": "bond_cash",
    "core_base": "core_quality",
    "attack_mainline": "technology",
    "defense": "defensive",
    "legacy_watch": "other",
}

SNAPSHOT_CATEGORY_BUCKET = {
    "bond_cash": "cash_short",
    "core_quality": "core_base",
    "core_quality_logistics": "core_base",
    "technology": "attack_mainline",
    "technology_terminal": "attack_mainline",
    "high_end_equipment": "attack_mainline",
    "power_equipment": "attack_mainline",
    "resources": "attack_mainline",
    "defensive": "defense",
    "financial": "defense",
    "medicine": "defense",
}

BUCKET_LABELS = {
    "cash_short": "现金/短融",
    "core_base": "宽基/核心底仓",
    "attack_mainline": "进攻主线仓",
    "defense": "防御仓",
    "legacy_watch": "其他/待清理",
}

BUCKET_COLORS = {
    "cash_short": "#5b6b7a",
    "core_base": "#2f6fbd",
    "attack_mainline": "#8b5cf6",
    "defense": "#0f8b6f",
    "legacy_watch": "#9a6700",
}

BUCKET_REGISTRY = ROOT / "research" / "config" / "bucket_registry.json"


def load_bucket_registry() -> None:
    global BUCKET_BY_CODE, CATEGORY_BY_BUCKET, BUCKET_LABELS, BUCKET_COLORS
    if not BUCKET_REGISTRY.exists():
        return
    config = read_project_json(BUCKET_REGISTRY, {})
    BUCKET_BY_CODE = {**BUCKET_BY_CODE, **(config.get("code_to_bucket") or {})}
    for key, meta in (config.get("buckets") or {}).items():
        BUCKET_LABELS[key] = meta.get("label", BUCKET_LABELS.get(key, key))
        BUCKET_COLORS[key] = meta.get("color", BUCKET_COLORS.get(key, "#9a6700"))
        CATEGORY_BY_BUCKET[key] = meta.get("category", CATEGORY_BY_BUCKET.get(key, "other"))


load_bucket_registry()


@dataclass(frozen=True)
class QmtPaths:
    site_packages: Path
    userdata: Path


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rel_path(path: Path | None) -> str | None:
    if path is None:
        return None
    return path.relative_to(ROOT).as_posix()


def finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result or result in {float("inf"), float("-inf")}:
        return None
    return result


def round_pct(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 4)


def plain_code(code: str) -> str:
    return str(code).split(".")[0].strip()


def normalize_code(code: str) -> str:
    raw = plain_code(code)
    if "." in str(code):
        return str(code).upper()
    if raw.startswith(("0", "3", "159")):
        return f"{raw}.SZ"
    if raw.startswith(("5", "6", "9")):
        return f"{raw}.SH"
    return raw


def mask_account(account_id: str | None) -> str:
    if not account_id:
        return ""
    text = str(account_id)
    if len(text) <= 4:
        return "****"
    return f"****{text[-4:]}"


def security_type(code: str) -> str:
    raw = plain_code(code)
    if raw.startswith(ETF_PREFIXES):
        return "ETF"
    return "stock"


def bucket_for_code(code: str) -> str:
    return BUCKET_BY_CODE.get(plain_code(code), "legacy_watch")


def latest_portfolio_snapshot() -> tuple[dict[str, Any], Path | None]:
    files = sorted(PORTFOLIO_DIR.glob("portfolio_snapshot_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return {}, None
    return read_json(files[0], {}), files[0]


def name_maps() -> dict[str, str]:
    names: dict[str, str] = {}
    rules = read_json(ALERT_RULES, {})
    for subject in rules.get("subjects", []):
        code = plain_code(subject.get("code", ""))
        if code and subject.get("name"):
            names[code] = str(subject["name"])
    latest, _ = latest_portfolio_snapshot()
    for item in latest.get("holdings", []):
        code = plain_code(item.get("code", ""))
        if code and item.get("name") and code not in names:
            names[code] = str(item["name"])
    return names


def latest_category_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    latest, _ = latest_portfolio_snapshot()
    for item in latest.get("holdings", []):
        code = plain_code(item.get("code", ""))
        category = item.get("category")
        if code and category:
            mapping[code] = str(category)
    return mapping


def discover_qmt_paths(site_arg: str | None, userdata_arg: str | None) -> QmtPaths:
    load_env()
    site_candidates: list[Path] = []
    userdata_candidates: list[Path] = []
    for value in [site_arg, os.environ.get("QMT_SITE_PACKAGES")]:
        if value:
            site_candidates.append(Path(value))
    for value in [userdata_arg, os.environ.get("QMT_USERDATA_DIR")]:
        if value:
            userdata_candidates.append(Path(value))

    for drive in ["D:/", "C:/"]:
        base = Path(drive)
        if base.exists():
            site_candidates.extend(base.glob("*/python/Lib/site-packages"))

    site_packages = next((p for p in site_candidates if (p / "xtquant" / "xttrader.py").exists()), None)
    if site_packages is None:
        raise RuntimeError("QMT xtquant site-packages not found. Set QMT_SITE_PACKAGES in .env or pass --qmt-site.")

    qmt_root = site_packages.parents[2]
    userdata_candidates.extend([qmt_root / "userdata_mini", qmt_root / "userdata"])
    userdata = next((p for p in userdata_candidates if p.exists()), None)
    if userdata is None:
        raise RuntimeError("QMT userdata directory not found. Set QMT_USERDATA_DIR in .env or pass --userdata.")

    return QmtPaths(site_packages=site_packages, userdata=userdata)


def import_qmt(paths: QmtPaths) -> tuple[Any, Any, Any]:
    sys.path.insert(0, str(paths.site_packages))
    from xtquant import xtdata, xttrader, xttype  # type: ignore

    return xtdata, xttrader, xttype


def object_public_dict(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "__dict__"):
        items = vars(obj).items()
    else:
        items = ((key, getattr(obj, key, None)) for key in dir(obj) if not key.startswith("_"))
    return {
        key: value
        for key, value in items
        if not callable(value) and isinstance(value, (str, int, float, bool, type(None)))
    }


def choose_account(trader: Any, xttype: Any, account_id: str | None) -> Any:
    if account_id:
        return xttype.StockAccount(account_id, "STOCK")
    env_account = os.environ.get("QMT_ACCOUNT_ID")
    if env_account:
        return xttype.StockAccount(env_account, "STOCK")

    infos = trader.query_account_infos() or []
    if not infos:
        raise RuntimeError("QMT returned no account info. Pass --account-id or set QMT_ACCOUNT_ID in .env.")
    first = infos[0]
    raw = object_public_dict(first)
    discovered_id = (
        raw.get("account_id")
        or raw.get("m_strAccountID")
        or raw.get("m_straccountid")
        or raw.get("accountID")
        or raw.get("account_id_")
        or getattr(first, "account_id", None)
        or getattr(first, "m_strAccountID", None)
    )
    if not discovered_id:
        raise RuntimeError("Could not discover QMT account id from account infos. Pass --account-id or set QMT_ACCOUNT_ID in .env.")
    return xttype.StockAccount(str(discovered_id), "STOCK")


def qmt_connection(paths: QmtPaths, account_id: str | None) -> tuple[Any, Any, Any, Any]:
    xtdata, xttrader, xttype = import_qmt(paths)
    session = int(time.time()) + random.randint(1, 9999)
    trader = xttrader.XtQuantTrader(str(paths.userdata), session)
    trader.start()
    result = trader.connect()
    if result != 0:
        trader.stop()
        raise RuntimeError(f"QMT trader connect failed: {result}. Check QMT login and independent trading mode.")
    account = choose_account(trader, xttype, account_id)
    sub_result = trader.subscribe(account)
    if sub_result != 0:
        trader.stop()
        raise RuntimeError(f"QMT account subscribe failed: {sub_result}. Check account login/permission.")
    return trader, account, xtdata, xttype


def tick_map(xtdata: Any, codes: list[str]) -> dict[str, dict[str, Any]]:
    try:
        return xtdata.get_full_tick(codes) or {}
    except Exception:
        return {}


def tick_last(tick: dict[str, Any]) -> float | None:
    for key in ["lastPrice", "last", "price"]:
        value = finite(tick.get(key))
        if value is not None and value > 0:
            return value
    return None


def tick_pct(tick: dict[str, Any], current_price: float | None) -> float | None:
    last = current_price
    pre_close = finite(tick.get("lastClose")) or finite(tick.get("preClose")) or finite(tick.get("pre_close"))
    if last is None or pre_close in (None, 0):
        return None
    return (last / pre_close - 1.0) * 100


def build_holdings(asset: Any, positions: list[Any], ticks: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, float], list[dict[str, Any]], list[dict[str, Any]]]:
    names = name_maps()
    category_map = latest_category_map()
    total_asset = finite(getattr(asset, "total_asset", None))
    total_market_value = sum(finite(getattr(item, "market_value", None)) or 0.0 for item in positions)
    denominator = total_asset if total_asset and total_asset > 0 else total_market_value
    holdings: list[dict[str, Any]] = []
    category_summary: dict[str, float] = {}
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for pos in positions:
        code = normalize_code(getattr(pos, "stock_code", ""))
        raw = plain_code(code)
        market_value = finite(getattr(pos, "market_value", None))
        volume = finite(getattr(pos, "volume", None))
        open_price = finite(getattr(pos, "open_price", None))
        tick = ticks.get(code, {})
        current_price = tick_last(tick)
        if current_price is None and market_value is not None and volume and volume > 0:
            current_price = market_value / volume
        if open_price is not None and open_price <= 0:
            errors.append(
                {
                    "code": raw,
                    "field": "cost_price",
                    "value": round(open_price, 4),
                    "action": "set_null_and_exclude_from_reference_pnl_pct",
                    "reason": "QMT open_price/cost field is non-positive and cannot be used as cost basis.",
                }
            )
            open_price = None
        if current_price is not None and current_price <= 0:
            errors.append(
                {
                    "code": raw,
                    "field": "current_price",
                    "value": round(current_price, 4),
                    "action": "set_null_and_block_precise_signal",
                    "reason": "QMT current price is non-positive.",
                }
            )
            current_price = None
        if not names.get(raw):
            warnings.append(
                {
                    "code": raw,
                    "field": "name",
                    "reason": "Name not found in intraday rules or previous portfolio snapshot; code used as fallback.",
                }
            )
        weight_pct = (market_value / denominator * 100.0) if market_value is not None and denominator else None
        reference_pnl_pct = ((current_price / open_price - 1.0) * 100.0) if current_price and open_price and open_price > 0 else None
        day_change_pct = tick_pct(tick, current_price)
        bucket = bucket_for_code(raw)
        category = category_map.get(raw) or CATEGORY_BY_BUCKET.get(bucket, "other")
        item = {
            "code": raw,
            "ts_code": code,
            "name": names.get(raw, raw),
            "type": security_type(raw),
            "weight_pct": round_pct(weight_pct),
            "day_change_pct": round_pct(day_change_pct),
            "reference_pnl_pct": round_pct(reference_pnl_pct),
            "cost_price": round(open_price, 4) if open_price is not None else None,
            "current_price": round(current_price, 4) if current_price is not None else None,
            "category": category,
            "allocation_bucket": bucket,
            "qmt_timetag": tick.get("timetag") or tick.get("time") or tick.get("stime"),
        }
        holdings.append(item)
        if item["weight_pct"] is not None:
            category_summary[category] = category_summary.get(category, 0.0) + float(item["weight_pct"])

    holdings.sort(key=lambda item: float(item.get("weight_pct") or 0), reverse=True)
    category_summary = {key: round(value, 4) for key, value in sorted(category_summary.items(), key=lambda kv: kv[0])}
    return holdings, category_summary, errors, warnings


def build_snapshot(trader: Any, account: Any, xtdata: Any) -> dict[str, Any]:
    asset = trader.query_stock_asset(account)
    if asset is None:
        raise RuntimeError("QMT query_stock_asset returned empty result.")
    positions = trader.query_stock_positions(account) or []
    positions = [item for item in positions if (finite(getattr(item, "market_value", None)) or 0) > 0]
    codes = [normalize_code(getattr(item, "stock_code", "")) for item in positions]
    ticks = tick_map(xtdata, codes)
    holdings, category_summary, quality_errors, quality_warnings = build_holdings(asset, positions, ticks)

    total_asset = finite(getattr(asset, "total_asset", None))
    cash = finite(getattr(asset, "cash", None))
    cash_pct = (cash / total_asset * 100.0) if cash is not None and total_asset and total_asset > 0 else None
    if cash_pct is not None and cash_pct > 0:
        category_summary["cash_uninvested"] = round_pct(cash_pct) or 0.0

    bond_cash_weight = category_summary.get("bond_cash", 0.0) + category_summary.get("cash_uninvested", 0.0)
    equity_weight = max(0.0, 100.0 - bond_cash_weight)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    date = timestamp[:10]
    account_masked = mask_account(getattr(account, "account_id", ""))
    weight_sum = round(sum(float(item.get("weight_pct") or 0) for item in holdings) + (cash_pct or 0), 4)
    if abs(weight_sum - 100.0) > 0.2:
        quality_errors.append(
            {
                "field": "summary.weight_sum_pct",
                "value": weight_sum,
                "reason": "Portfolio weights do not sum to 100±0.2.",
            }
        )
    return {
        "module": "portfolio_snapshot",
        "version": "qmt_readonly_ratio_only_v1",
        "date": date,
        "generated_at": timestamp,
        "source": "qmt_xttrader_readonly",
        "session": "qmt_readonly",
        "account_masked": account_masked,
        "amount_policy": "ratio_only; cost_price/current_price/pnl_pct allowed; no market_value, cash amount, cost amount, profit amount, volume, available volume, or full account id saved",
        "privacy_policy": {
            "allowed_fields": ["code", "name", "weight_pct", "day_change_pct", "reference_pnl_pct", "cost_price", "current_price", "category", "allocation_bucket"],
            "excluded_fields": sorted(SENSITIVE_OUTPUT_FIELDS),
        },
        "quality": {
            "status": "error" if quality_errors else ("warning" if quality_warnings else "ok"),
            "errors": quality_errors,
            "warnings": quality_warnings,
            "policy": "cost_price/current_price <= 0 are set to null and excluded from reference_pnl_pct; severe quality errors degrade downstream action use.",
        },
        "summary": {
            "total_items": len(holdings),
            "equity_weight_pct": round(equity_weight, 4),
            "bond_cash_weight_pct": round(bond_cash_weight, 4),
            "cash_uninvested_pct": round_pct(cash_pct),
            "weight_sum_pct": weight_sum,
            "one_line_conclusion": "QMT只读持仓快照已生成；文件仅保存比例、价格和盈亏比例，不保存金额、数量或账号全号。",
        },
        "category_summary": category_summary,
        "holdings": holdings,
        "data_excluded": sorted(SENSITIVE_OUTPUT_FIELDS),
        "decision_log_entry": f"{date} QMT只读持仓快照：生成 portfolio_snapshot_{timestamp}.md/json；只保存仓位比例、成本价、现价、当日涨跌幅和参考盈亏比例，不保存市值、现金金额、盈亏金额、股数、可用数量或账号全号；同步 intraday_rules 实际仓位覆盖层。",
    }


def assert_no_sensitive_fields(data: Any, path: str = "") -> None:
    if isinstance(data, dict):
        for key, value in data.items():
            lowered = str(key).lower()
            if key in SENSITIVE_OUTPUT_FIELDS or lowered in SENSITIVE_OUTPUT_FIELDS:
                if path.endswith("privacy_policy") or path.endswith("data_excluded"):
                    continue
                raise RuntimeError(f"Sensitive field leaked into output: {path}.{key}")
            assert_no_sensitive_fields(value, f"{path}.{key}" if path else str(key))
    elif isinstance(data, list):
        for index, item in enumerate(data):
            assert_no_sensitive_fields(item, f"{path}[{index}]")


def render_markdown(snapshot: dict[str, Any]) -> str:
    rows = []
    for item in snapshot.get("holdings", []):
        rows.append(
            "| {code} | {name} | {bucket} | {weight:.4f}% | {day} | {pnl} | {cost} | {price} |".format(
                code=item.get("code", ""),
                name=item.get("name", ""),
                bucket=BUCKET_LABELS.get(item.get("allocation_bucket"), item.get("allocation_bucket", "")),
                weight=float(item.get("weight_pct") or 0),
                day="-" if item.get("day_change_pct") is None else f"{float(item['day_change_pct']):.4f}%",
                pnl="-" if item.get("reference_pnl_pct") is None else f"{float(item['reference_pnl_pct']):.4f}%",
                cost="-" if item.get("cost_price") is None else f"{float(item['cost_price']):.4f}",
                price="-" if item.get("current_price") is None else f"{float(item['current_price']):.4f}",
            )
        )
    category_rows = [
        f"| {category} | {float(weight):.4f}% |"
        for category, weight in snapshot.get("category_summary", {}).items()
    ]
    return f"""# QMT只读持仓快照

日期：{snapshot['date']}  
生成时间：{snapshot['generated_at']}  
来源：QMT xttrader 只读查询  
账号：{snapshot.get('account_masked', '')}

## 1. 隐私口径

本文件只保存比例、成本价、现价、当日涨跌幅和参考盈亏比例。  
不保存：市值、现金金额、成本金额、盈亏金额、股数、可用数量、冻结数量、账号全号。

## 2. 汇总

| 项目 | 比例 |
| --- | ---: |
| 权益仓 | {snapshot['summary']['equity_weight_pct']:.4f}% |
| 债券/短融/现金仓 | {snapshot['summary']['bond_cash_weight_pct']:.4f}% |
| 未投资现金 | {snapshot['summary'].get('cash_uninvested_pct') if snapshot['summary'].get('cash_uninvested_pct') is not None else '-'}% |
| 权重合计 | {snapshot['summary']['weight_sum_pct']:.4f}% |

## 3. 分类汇总

| 分类 | 比例 |
| --- | ---: |
{chr(10).join(category_rows) if category_rows else '| 无 | 0% |'}

## 4. 持仓明细

| 代码 | 名称 | 仓位桶 | 仓位比例 | 当日涨跌幅 | 参考盈亏比例 | 成本价 | 现价 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(rows) if rows else '| 无 | 无 | 无 | 0% | - | - | - | - |'}

## 5. 决策日志条目

```text
{snapshot['decision_log_entry']}
```
"""


def latest_file(directory: Path, pattern: str) -> Path | None:
    files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def sync_intraday_rules(snapshot: dict[str, Any]) -> bool:
    if not ALERT_RULES.exists():
        return False
    rules = read_json(ALERT_RULES, {})
    latest_allocation = latest_for_module("target_allocation")
    stale_findings: list[dict[str, Any]] = []
    weights = {plain_code(item.get("code", "")): float(item.get("weight_pct") or 0) for item in snapshot.get("holdings", [])}

    actual_by_bucket = {key: 0.0 for key in BUCKET_LABELS}
    for item in snapshot.get("holdings", []):
        actual_by_bucket[item.get("allocation_bucket") or bucket_for_code(item.get("code", ""))] += float(item.get("weight_pct") or 0)
    actual_by_bucket["cash_short"] += float(snapshot.get("summary", {}).get("cash_uninvested_pct") or 0)

    allocation_map = rules.get("allocation_map") or {}
    current_target_file = allocation_map.get("target_allocation_file")
    if latest_allocation and current_target_file != latest_allocation.get("path"):
        stale_findings.append(
            {
                "level": "STALE",
                "path": "research/alerts/intraday_rules.json",
                "reason": "QMT snapshot sync detected intraday_rules target_allocation_file is not latest",
                "dependency": current_target_file,
                "latest_path": latest_allocation.get("path"),
            }
        )
    if snapshot.get("quality", {}).get("status") in {"error", "warning"}:
        stale_findings.append(
            {
                "level": "WARN",
                "path": "research/alerts/intraday_rules.json",
                "reason": "latest QMT portfolio snapshot has data quality warnings/errors",
                "dependency": f"research/portfolio/portfolio_snapshot_{snapshot['generated_at']}.json",
            }
        )
    old_buckets = allocation_map.get("buckets", [])
    target_by_bucket = {item.get("key"): float(item.get("target_pct") or 0) for item in old_buckets}
    buckets = []
    for key in ["core_base", "attack_mainline", "defense", "legacy_watch", "cash_short"]:
        actual = round(actual_by_bucket.get(key, 0.0), 4)
        target = round(target_by_bucket.get(key, 0.0), 4)
        if actual == 0 and target == 0:
            continue
        buckets.append(
            {
                "key": key,
                "label": BUCKET_LABELS[key],
                "color": BUCKET_COLORS[key],
                "target_pct": target,
                "actual_pct": actual,
                "gap_pct": round(actual - target, 4),
                "note": "actual_pct由QMT只读持仓快照同步；不保存任何金额或数量。",
            }
        )
    allocation_map.update(
        {
            "basis": "latest_target_allocation_and_qmt_readonly_portfolio_snapshot",
            "portfolio_snapshot_file": f"research/portfolio/portfolio_snapshot_{snapshot['generated_at']}.json",
            "actual_equity_pct": round(float(snapshot["summary"]["equity_weight_pct"]), 4),
            "actual_cash_short_pct": round(float(snapshot["summary"]["bond_cash_weight_pct"]), 4),
            "actual_overlay": [
                {"key": item["key"], "label": item["label"], "color": item["color"], "actual_pct": item["actual_pct"], "gap_pct": item["gap_pct"]}
                for item in buckets
                if item["actual_pct"] > 0
            ],
            "buckets": buckets,
        }
    )
    rules["allocation_map"] = allocation_map
    rules["last_portfolio_snapshot_sync"] = snapshot["generated_at"]
    if stale_findings:
        rules["staleness"] = {
            "status": "stale" if any(item["level"] == "STALE" for item in stale_findings) else "degraded",
            "checked_at": snapshot["generated_at"],
            "mode": "degraded_observation_only",
            "reason": "QMT只同步真实仓位；若目标仓位或数据质量异常，不允许静默形成新持仓+旧目标的状态。",
            "findings": stale_findings,
        }
        rules.setdefault("global_gate", {})["default_market_gate"] = "verify_only"
    for subject in rules.get("subjects", []):
        raw = plain_code(subject.get("code", ""))
        ref = subject.setdefault("reference_metrics", {})
        ref["current_position_pct"] = round(weights.get(raw, 0.0), 4)
    write_json(ALERT_RULES, rules)
    return True


def write_snapshot(snapshot: dict[str, Any], sync_rules: bool) -> tuple[Path, Path, bool]:
    assert_no_sensitive_fields(snapshot)
    timestamp = snapshot["generated_at"]
    json_path = PORTFOLIO_DIR / f"portfolio_snapshot_{timestamp}.json"
    md_path = PORTFOLIO_DIR / f"portfolio_snapshot_{timestamp}.md"
    write_json(json_path, snapshot)
    md_path.write_text(render_markdown(snapshot), encoding="utf-8")
    synced = sync_intraday_rules(snapshot) if sync_rules else False
    DECISION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DECISION_LOG.open("a", encoding="utf-8") as handle:
        handle.write("\n" + snapshot["decision_log_entry"] + "\n")
    return md_path, json_path, synced


def probe(args: argparse.Namespace) -> int:
    paths = discover_qmt_paths(args.qmt_site, args.userdata)
    trader, account, _xtdata, _xttype = qmt_connection(paths, args.account_id)
    try:
        asset = trader.query_stock_asset(account)
        positions = trader.query_stock_positions(account) or []
        result = {
            "qmt_site_found": True,
            "userdata_found": True,
            "account_masked": mask_account(getattr(account, "account_id", "")),
            "asset_available": asset is not None,
            "positions_count": len(positions),
            "privacy": "probe does not print amount, volume, market value, cash, or full account id",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        trader.stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qmt-site", help="QMT python/Lib/site-packages path. Defaults to auto-discovery or QMT_SITE_PACKAGES.")
    parser.add_argument("--userdata", help="QMT userdata_mini/userdata path. Defaults to auto-discovery or QMT_USERDATA_DIR.")
    parser.add_argument("--account-id", help="QMT fund account id. Defaults to QMT_ACCOUNT_ID or first discovered account.")
    parser.add_argument("--probe", action="store_true", help="Check read-only connectivity without writing a snapshot.")
    parser.add_argument("--no-sync-rules", action="store_true", help="Do not sync research/alerts/intraday_rules.json.")
    parser.add_argument("--dry-run", action="store_true", help="Print sanitized snapshot JSON without writing files.")
    args = parser.parse_args(argv)

    paths = discover_qmt_paths(args.qmt_site, args.userdata)
    if args.probe:
        return probe(args)

    trader, account, xtdata, _xttype = qmt_connection(paths, args.account_id)
    try:
        snapshot = build_snapshot(trader, account, xtdata)
    finally:
        trader.stop()

    assert_no_sensitive_fields(snapshot)
    if args.dry_run:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        return 0

    md_path, json_path, synced = write_snapshot(snapshot, sync_rules=not args.no_sync_rules)
    print(
        json.dumps(
            {
                "created": [rel_path(md_path), rel_path(json_path)],
                "synced_intraday_rules": synced,
                "privacy": "ratio-only; no amount, volume, cash amount, profit amount, or full account id saved",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
