#!/usr/bin/env python3
"""Generate a theme leader candidate pool from the theme registry.

The output is a routing artifact, not an action plan. It only answers:
which theme-linked ETFs/stocks are ready for later review, and which ones
must remain ResearchFirst.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
THEME_REGISTRY = ROOT / "research" / "themes" / "theme_registry.json"
ETF_REGISTRY = ROOT / "research" / "etfs" / "etf_registry.json"
STOCK_REGISTRY = ROOT / "research" / "stocks" / "stock_registry.json"
VALUATION_DIR = ROOT / "research" / "valuations"
OUTPUT_DIR = ROOT / "research" / "theme_leaders"

DEFAULT_CONFIRMED_RATINGS = ("A", "A-", "B+")
EXCLUDED_STAGES = {"decline"}


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def normalize_code(code: Any) -> str:
    text = str(code or "").strip().upper()
    if not text:
        return ""
    if "." in text:
        symbol, suffix = text.split(".", 1)
        return f"{symbol.zfill(6)}.{suffix}"
    if re.fullmatch(r"\d{6}", text):
        suffix = "SH" if text.startswith(("5", "6", "9")) else "SZ"
        return f"{text}.{suffix}"
    return text


def bare_code(code: Any) -> str:
    return normalize_code(code).split(".", 1)[0]


def clean_name(name: Any) -> str:
    text = str(name or "").strip()
    for suffix in ("-W", "-U", "W", "U", "A", "股份", "集团"):
        if text.endswith(suffix) and len(text) > len(suffix) + 1:
            text = text[: -len(suffix)]
    return text.replace(" ", "")


def load_env_token() -> str | None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return os.environ.get("TUSHARE_TOKEN")
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip().startswith("TUSHARE_TOKEN="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            return value or os.environ.get("TUSHARE_TOKEN")
    return os.environ.get("TUSHARE_TOKEN")


def load_tushare_name_map(warnings: list[str]) -> dict[str, list[dict[str, Any]]]:
    token = load_env_token()
    if not token:
        warnings.append("Tushare token missing; stock code resolution uses local registry only.")
        return {}
    try:
        import tushare as ts  # type: ignore
    except Exception as exc:  # pragma: no cover - environment dependent
        warnings.append(f"Tushare import failed: {type(exc).__name__}: {exc}")
        return {}
    try:
        pro = ts.pro_api(token)
        df = pro.stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,symbol,name,industry,market",
        )
    except Exception as exc:  # pragma: no cover - network/provider dependent
        warnings.append(f"Tushare stock_basic failed: {type(exc).__name__}: {exc}")
        return {}

    name_map: dict[str, list[dict[str, Any]]] = {}

    def add_name(key: str, record: dict[str, Any]) -> None:
        if not key:
            return
        bucket = name_map.setdefault(key, [])
        if not any(existing.get("code") == record.get("code") for existing in bucket):
            bucket.append(record)

    for _, row in df.iterrows():
        record = {
            "code": normalize_code(row.get("ts_code")),
            "name": str(row.get("name") or "").strip(),
            "industry": str(row.get("industry") or "").strip(),
            "market": str(row.get("market") or "").strip(),
            "source": "Tushare.stock_basic",
        }
        if not record["name"] or not record["code"]:
            continue
        add_name(record["name"], record)
        add_name(clean_name(record["name"]), record)
    return name_map


def registry_by_code(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for item in items:
        code = normalize_code(item.get("code"))
        if code:
            output[code] = item
            output[bare_code(code)] = item
    return output


def registry_by_name(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for item in items:
        name = str(item.get("name") or "").strip()
        if name:
            output[name] = item
            output[clean_name(name)] = item
    return output


def latest_valuation_map() -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for path in sorted(VALUATION_DIR.glob("*.json")):
        data = read_json(path, {})
        if not isinstance(data, dict):
            continue
        code = normalize_code(data.get("code") or data.get("ts_code") or data.get("security_code"))
        if not code:
            match = re.search(r"valuation_(\d{6})_([A-Z]{2})_", path.name)
            if match:
                code = f"{match.group(1)}.{match.group(2)}"
        if not code:
            continue
        generated_at = data.get("generated_at") or path.name
        record = {
            "path": rel(path),
            "generated_at": generated_at,
            "zone": data.get("zone") or data.get("valuation_zone"),
        }
        previous = latest.get(code)
        if previous is None or str(generated_at) > str(previous.get("generated_at", "")):
            latest[code] = record
            latest[bare_code(code)] = record
    return latest


def profile_present(entry: dict[str, Any] | None, kind: str) -> bool:
    if not entry:
        return False
    status = str(entry.get("status") or "").lower()
    if status not in {"profile_generated", "active", "watch", "completed"}:
        return False
    profile_json = entry.get("last_profile_json")
    if not profile_json:
        return False
    return (ROOT / str(profile_json)).exists()


def resolve_stock(
    name: str,
    stock_by_name: dict[str, dict[str, Any]],
    stock_by_code: dict[str, dict[str, Any]],
    tushare_map: dict[str, list[dict[str, Any]]],
) -> tuple[str, str, dict[str, Any] | None, str]:
    if name in stock_by_name:
        entry = stock_by_name[name]
        return normalize_code(entry.get("code")), str(entry.get("name") or name), entry, "stock_registry"
    cleaned = clean_name(name)
    if cleaned in stock_by_name:
        entry = stock_by_name[cleaned]
        return normalize_code(entry.get("code")), str(entry.get("name") or name), entry, "stock_registry"

    matches = tushare_map.get(name) or tushare_map.get(cleaned) or []
    if len(matches) == 1:
        code = normalize_code(matches[0].get("code"))
        return code, str(matches[0].get("name") or name), stock_by_code.get(code), "Tushare.stock_basic"
    if len(matches) > 1:
        return "", name, None, "ambiguous_Tushare.stock_basic"
    return "", name, None, "unresolved"


def theme_is_confirmed(theme: dict[str, Any], confirmed_ratings: set[str]) -> tuple[bool, str]:
    tactical = str(theme.get("tactical_rating") or theme.get("rating") or "").strip()
    stage = str(theme.get("stage") or theme.get("current_a_share_trading_stage") or "").strip()
    status = str(theme.get("status") or "").strip()
    if status != "active":
        return False, f"status={status or 'unknown'}"
    if stage in EXCLUDED_STAGES:
        return False, f"stage={stage}"
    if tactical not in confirmed_ratings:
        return False, f"tactical_rating={tactical or 'unknown'} not in {sorted(confirmed_ratings)}"
    return True, "theme tactical rating confirmed"


def route_item(
    item: dict[str, Any],
    theme_confirmed: bool,
    theme_reason: str,
    profile_ok: bool,
    valuation: dict[str, Any] | None,
    code_resolved: bool,
) -> str:
    if not theme_confirmed:
        return "watch_only.theme_not_confirmed"
    if not code_resolved:
        return "ResearchFirst.code_unresolved"
    if not profile_ok:
        return "ResearchFirst.profile_missing"
    if valuation is None:
        return "ResearchFirst.valuation_missing"
    return "ready_for_review"


def item_reason(route: str, theme_reason: str) -> str:
    reasons = {
        "watch_only.theme_not_confirmed": f"所属主线未达到确认门槛：{theme_reason}",
        "ResearchFirst.code_unresolved": "代表股票名称未解析到唯一A股代码，需先确认代码。",
        "ResearchFirst.profile_missing": "缺少ETF/个股档案，不能进入操作建议。",
        "ResearchFirst.valuation_missing": "已有档案但缺少估值报告，需先补估值。",
        "ready_for_review": "主线已确认，档案和估值均存在，可进入盘前/盘中/操作建议复核。",
    }
    return reasons.get(route, route)


def make_candidate(
    *,
    kind: str,
    code: str,
    name: str,
    theme: dict[str, Any],
    theme_confirmed: bool,
    theme_reason: str,
    registry_entry: dict[str, Any] | None,
    valuation: dict[str, Any] | None,
    resolution_source: str,
) -> dict[str, Any]:
    profile_ok = profile_present(registry_entry, kind)
    resolved = bool(code) if kind == "stock" else bool(code)
    route = route_item(
        {},
        theme_confirmed=theme_confirmed,
        theme_reason=theme_reason,
        profile_ok=profile_ok,
        valuation=valuation,
        code_resolved=resolved,
    )
    return {
        "type": kind,
        "code": code or None,
        "name": name,
        "theme": theme.get("name"),
        "strategic_rating": theme.get("strategic_rating"),
        "tactical_rating": theme.get("tactical_rating") or theme.get("rating"),
        "stage": theme.get("stage") or theme.get("current_a_share_trading_stage"),
        "theme_confirmed": theme_confirmed,
        "route": route,
        "reason": item_reason(route, theme_reason),
        "resolution_source": resolution_source,
        "profile": {
            "status": "present" if profile_ok else "missing",
            "registry_status": registry_entry.get("status") if registry_entry else None,
            "last_profile_file": registry_entry.get("last_profile_file") if registry_entry else None,
            "last_profile_json": registry_entry.get("last_profile_json") if registry_entry else None,
        },
        "valuation": {
            "status": "present" if valuation else "missing",
            "latest_file": valuation.get("path") if valuation else None,
            "generated_at": valuation.get("generated_at") if valuation else None,
            "zone": valuation.get("zone") if valuation else None,
        },
    }


def render_md(data: dict[str, Any]) -> str:
    def table(items: list[dict[str, Any]], reason_title: str) -> str:
        if not items:
            return "| 类型 | 代码 | 名称 | 所属主线 | 状态 |\n| --- | --- | --- | --- | --- |\n| - | - | - | - | 无 |\n"
        rows = ["| 类型 | 代码 | 名称 | 所属主线 | 状态 |", "| --- | --- | --- | --- | --- |"]
        for item in items:
            rows.append(
                "| {type} | {code} | {name} | {theme} | {reason} |".format(
                    type=item.get("type") or "",
                    code=item.get("code") or "-",
                    name=item.get("name") or "",
                    theme=item.get("theme") or "",
                    reason=item.get(reason_title) or item.get("route") or "",
                )
            )
        return "\n".join(rows) + "\n"

    summary = data["summary"]
    ratings = " / ".join(data["selection_policy"]["confirmed_tactical_ratings"])
    lines = [
        "# 主线龙头候选池",
        "",
        f"- 生成时间：{data['generated_at']}",
        f"- 主线登记册：`{data['basis']['theme_registry']}`",
        f"- ETF登记册：`{data['basis']['etf_registry']}`",
        f"- 个股登记册：`{data['basis']['stock_registry']}`",
        f"- 估值目录：`{data['basis']['valuation_dir']}`",
        f"- 确认门槛：交易评级 {ratings}，且阶段不为 decline",
        "",
        "> 候选池不是可买清单。它只决定哪些标的可进入后续复核，最终动作仍由盘前、盘中、组合和操作建议模块决定。",
        "",
        "## 总览",
        "",
        "| 项目 | 数量 |",
        "| --- | ---: |",
        f"| 主线总数 | {summary['themes_total']} |",
        f"| 已确认主线 | {summary['themes_confirmed']} |",
        f"| 可进入复核 | {summary['ready_for_review']} |",
        f"| ResearchFirst | {summary['research_first']} |",
        f"| 仅观察 | {summary['watch_only']} |",
        "",
        "## 主线状态",
        "",
        "| 主线 | 战略评级 | 交易评级 | 阶段 | 是否进入确认池 | 原因 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for theme in data["themes"]:
        lines.append(
            "| {name} | {strategic} | {tactical} | {stage} | {confirmed} | {reason} |".format(
                name=theme.get("name") or "",
                strategic=theme.get("strategic_rating") or "",
                tactical=theme.get("tactical_rating") or "",
                stage=theme.get("stage") or "",
                confirmed="是" if theme.get("confirmed") else "否",
                reason=theme.get("confirmation_reason") or "",
            )
        )
    lines.extend(
        [
            "",
            "## 可进入复核",
            "",
            table(data["ready_for_review"], "reason"),
            "",
            "## ResearchFirst",
            "",
            table(data["research_first"], "reason"),
            "",
            "## 仅观察",
            "",
            table(data["watch_only"], "reason"),
            "",
            "## 数据来源和质量",
            "",
        ]
    )
    for source in data.get("data_sources", []):
        lines.append(f"- {source}")
    warnings = data.get("quality", {}).get("warnings") or []
    if warnings:
        lines.append("")
        lines.append("### 警告")
        for warning in warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"


def generate(args: argparse.Namespace) -> tuple[Path, Path, dict[str, Any]]:
    timestamp = args.timestamp or datetime.now().strftime("%Y-%m-%d_%H%M%S")
    confirmed_ratings = set(args.confirmed_rating)
    if args.include_b:
        confirmed_ratings.add("B")

    warnings: list[str] = []
    theme_registry = read_json(THEME_REGISTRY, {})
    etf_registry = read_json(ETF_REGISTRY, {})
    stock_registry = read_json(STOCK_REGISTRY, {})

    themes = theme_registry.get("themes") or []
    etfs = etf_registry.get("etfs") or []
    stocks = stock_registry.get("stocks") or []

    etf_by_code = registry_by_code(etfs)
    stock_by_code = registry_by_code(stocks)
    stock_by_name = registry_by_name(stocks)
    valuation_by_code = latest_valuation_map()
    tushare_map = {} if args.no_tushare else load_tushare_name_map(warnings)

    data: dict[str, Any] = {
        "module": "theme_leaders",
        "version": "1.0",
        "generated_at": timestamp,
        "basis": {
            "theme_registry": rel(THEME_REGISTRY),
            "theme_registry_version": theme_registry.get("version"),
            "theme_registry_last_updated": theme_registry.get("last_updated"),
            "etf_registry": rel(ETF_REGISTRY),
            "stock_registry": rel(STOCK_REGISTRY),
            "valuation_dir": rel(VALUATION_DIR),
        },
        "selection_policy": {
            "confirmed_tactical_ratings": sorted(confirmed_ratings),
            "exclude_stages": sorted(EXCLUDED_STAGES),
            "candidate_source": "theme_registry.related_etfs + theme_registry.representative_stocks",
            "operation_boundary": "候选池不是可买清单；操作建议必须另行读取市场仓位、组合约束、档案、估值和盘中规则。",
        },
        "summary": {
            "themes_total": len(themes),
            "themes_confirmed": 0,
            "ready_for_review": 0,
            "research_first": 0,
            "watch_only": 0,
        },
        "themes": [],
        "ready_for_review": [],
        "research_first": [],
        "watch_only": [],
        "all_candidates": [],
        "data_sources": [
            "theme_registry.related_etfs",
            "theme_registry.representative_stocks",
            "etf_registry profile status",
            "stock_registry profile status",
            "research/valuations latest files",
        ],
        "quality": {
            "status": "fresh",
            "warnings": warnings,
        },
    }
    if tushare_map:
        data["data_sources"].append("Tushare.stock_basic for stock name-code resolution")

    seen: set[tuple[str, str, str]] = set()
    for theme in themes:
        confirmed, theme_reason = theme_is_confirmed(theme, confirmed_ratings)
        if confirmed:
            data["summary"]["themes_confirmed"] += 1
        theme_record = {
            "name": theme.get("name"),
            "strategic_rating": theme.get("strategic_rating"),
            "tactical_rating": theme.get("tactical_rating") or theme.get("rating"),
            "stage": theme.get("stage") or theme.get("current_a_share_trading_stage"),
            "status": theme.get("status"),
            "score": theme.get("score"),
            "confirmed": confirmed,
            "confirmation_reason": theme_reason,
        }
        data["themes"].append(theme_record)

        for code_raw in theme.get("related_etfs") or []:
            code = normalize_code(code_raw)
            entry = etf_by_code.get(code) or etf_by_code.get(bare_code(code))
            name = entry.get("name") if entry else code
            valuation = valuation_by_code.get(code) or valuation_by_code.get(bare_code(code))
            key = ("etf", code, str(theme.get("name") or ""))
            if key in seen:
                continue
            seen.add(key)
            candidate = make_candidate(
                kind="etf",
                code=code,
                name=str(name or code),
                theme=theme,
                theme_confirmed=confirmed,
                theme_reason=theme_reason,
                registry_entry=entry,
                valuation=valuation,
                resolution_source="theme_registry.related_etfs",
            )
            data["all_candidates"].append(candidate)

        for stock_name in theme.get("representative_stocks") or []:
            code, resolved_name, entry, source = resolve_stock(
                str(stock_name),
                stock_by_name=stock_by_name,
                stock_by_code=stock_by_code,
                tushare_map=tushare_map,
            )
            valuation = valuation_by_code.get(code) or valuation_by_code.get(bare_code(code))
            key = ("stock", code or resolved_name, str(theme.get("name") or ""))
            if key in seen:
                continue
            seen.add(key)
            candidate = make_candidate(
                kind="stock",
                code=code,
                name=resolved_name,
                theme=theme,
                theme_confirmed=confirmed,
                theme_reason=theme_reason,
                registry_entry=entry,
                valuation=valuation,
                resolution_source=source,
            )
            data["all_candidates"].append(candidate)

    for candidate in data["all_candidates"]:
        route = str(candidate.get("route"))
        if route == "ready_for_review":
            data["ready_for_review"].append(candidate)
        elif route.startswith("ResearchFirst."):
            data["research_first"].append(candidate)
        else:
            data["watch_only"].append(candidate)

    data["summary"]["ready_for_review"] = len(data["ready_for_review"])
    data["summary"]["research_first"] = len(data["research_first"])
    data["summary"]["watch_only"] = len(data["watch_only"])
    if data["summary"]["themes_confirmed"] == 0:
        data["quality"]["warnings"].append(
            "No active theme met the confirmed tactical rating gate; all candidates remain watch_only."
        )

    json_path = OUTPUT_DIR / f"theme_leaders_{timestamp}.json"
    md_path = OUTPUT_DIR / f"theme_leaders_{timestamp}.md"
    write_json(json_path, data)
    md_path.write_text(render_md(data), encoding="utf-8")
    return md_path, json_path, data


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirmed-rating",
        action="append",
        default=list(DEFAULT_CONFIRMED_RATINGS),
        help="Tactical rating allowed into confirmed theme pool. Can be repeated.",
    )
    parser.add_argument("--include-b", action="store_true", help="Also treat tactical B as confirmed.")
    parser.add_argument("--no-tushare", action="store_true", help="Do not use Tushare for stock code resolution.")
    parser.add_argument("--timestamp", help="Override output timestamp YYYY-MM-DD_HHMMSS.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    md_path, json_path, data = generate(args)
    print(
        json.dumps(
            {
                "created": [rel(md_path), rel(json_path)],
                "summary": data["summary"],
                "quality": data["quality"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
