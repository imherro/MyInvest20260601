from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "local" / "myinvest.sqlite"
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(amount|market_value|profit_amount|total_amount|total_asset|share_count|shares|quantity|qty|"
    r"available_qty|available_quantity|account|account_masked|full_account|order|deal|fill|trade_amount|"
    r"cost_price|raw_cost_price|current_price)($|_)",
    re.IGNORECASE,
)
LOCAL_ABS_PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\)")
MONEY_OR_SHARE_RE = re.compile(r"[-+]?\d+(?:\.\d+)?\s*(?:元|万元|亿元|股|份|手)")


app = FastAPI(title="MyInvest Current Read API", version="0.1.0")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


def assert_ratio_only(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            key_path = f"{path}.{key_text}"
            if FORBIDDEN_KEY_RE.search(key_text):
                raise ValueError(f"forbidden field {key_path}")
            assert_ratio_only(item, key_path)
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            assert_ratio_only(item, f"{path}[{idx}]")
    elif isinstance(value, str):
        if LOCAL_ABS_PATH_RE.search(value):
            raise ValueError(f"local absolute path at {path}")
        if MONEY_OR_SHARE_RE.search(value):
            raise ValueError(f"forbidden amount/share-like text at {path}")


def response_payload(data: dict[str, Any]) -> dict[str, Any]:
    try:
        assert_ratio_only(data)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="ratio-only sanitizer rejected response") from exc
    return data


def api_response(
    data: Any,
    source: dict[str, Any] | None = None,
    warnings: list[Any] | None = None,
    errors: list[Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "ok": not errors,
        "data": data,
        "warnings": warnings or [],
        "errors": errors or [],
        "source": source,
    }
    return response_payload(payload)


def connect_readonly() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise HTTPException(status_code=503, detail="database not built")
    uri = f"{DB_PATH.as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def rows(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn = connect_readonly()
    try:
        return [dict(row) for row in conn.execute(query, params).fetchall()]
    finally:
        conn.close()


def one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    conn = connect_readonly()
    try:
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def parse_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def latest_plan() -> dict[str, Any] | None:
    return one(
        """
        SELECT id, date, generated_at, basis_trade_date, action_state, recommendation_strength,
               one_line_conclusion, quality_status, staleness_status
        FROM action_plans
        ORDER BY id DESC
        LIMIT 1
        """
    )


def action_items(plan_id: int) -> list[dict[str, Any]]:
    items = rows(
        """
        SELECT priority, action_type, code, name, subject_type, bucket_role,
               current_position, suggested_change, target_position, recommendation_strength,
               needs_manual_confirmation, evidence_json, trigger_conditions_json,
               invalidation_conditions_json, risks_json, review_points_json
        FROM action_items
        WHERE action_plan_id = ?
        ORDER BY id
        """,
        (plan_id,),
    )
    for item in items:
        item["needs_manual_confirmation"] = bool(item["needs_manual_confirmation"])
        for key in [
            "evidence_json",
            "trigger_conditions_json",
            "invalidation_conditions_json",
            "risks_json",
            "review_points_json",
        ]:
            item[key.removesuffix("_json")] = parse_json(item.pop(key), [])
    return items


def research_first_items(plan_id: int | None = None) -> list[dict[str, Any]]:
    if plan_id is None:
        query = """
            SELECT code, name, subject_type, bucket_role, priority, reason,
                   blocking_reasons_json, required_research_json, source
            FROM research_first_items
            ORDER BY id
        """
        params: tuple[Any, ...] = ()
    else:
        query = """
            SELECT code, name, subject_type, bucket_role, priority, reason,
                   blocking_reasons_json, required_research_json, source
            FROM research_first_items
            WHERE action_plan_id = ?
            ORDER BY id
        """
        params = (plan_id,)
    items = rows(query, params)
    for item in items:
        item["blocking_reasons"] = parse_json(item.pop("blocking_reasons_json"), [])
        item["required_research"] = parse_json(item.pop("required_research_json"), [])
    return items


def current_modules() -> list[dict[str, Any]]:
    return rows(
        """
        SELECT module, code, name, path, generated_at, basis_trade_date, quality_status, staleness_status
        FROM current_modules
        ORDER BY module
        """
    )


def source_for_module(module: str) -> dict[str, Any] | None:
    return one(
        """
        SELECT module, path, generated_at, basis_trade_date, quality_status, staleness_status
        FROM current_modules
        WHERE module = ?
        """,
        (module,),
    )


def action_plan_current_data() -> dict[str, Any]:
    plan = latest_plan()
    if not plan:
        return {"action_plan": None, "items": [], "research_first": []}
    return {
        "action_plan": {k: v for k, v in plan.items() if k != "id"},
        "items": action_items(plan["id"]),
        "research_first": research_first_items(plan["id"]),
    }


def target_allocation() -> dict[str, Any] | None:
    target = one(
        """
        SELECT id, date, generated_at, basis_trade_date, market_state, market_position_score,
               recommended_equity_center, recommended_equity_range, recommended_bond_cash_center,
               recommended_bond_cash_range, offensive_bucket_status, one_line_conclusion
        FROM target_allocations
        ORDER BY id DESC
        LIMIT 1
        """
    )
    if not target:
        return None
    target["buckets"] = rows(
        """
        SELECT bucket_key, label, target_pct, actual_pct, gap_pct, color, priority, role, source
        FROM bucket_allocations
        WHERE target_allocation_id = ?
        ORDER BY id
        """,
        (target["id"],),
    )
    return target


def portfolio_snapshot() -> dict[str, Any] | None:
    snapshot = one(
        """
        SELECT id, date, generated_at, total_items, equity_weight_pct, bond_cash_weight_pct,
               cash_uninvested_pct, weight_sum_pct, one_line_conclusion, quality_status
        FROM portfolio_snapshots
        ORDER BY id DESC
        LIMIT 1
        """
    )
    if not snapshot:
        return None
    snapshot["positions"] = rows(
        """
        SELECT code, ts_code, name, position_type, weight_pct, day_change_pct, reference_pnl_pct,
               category, allocation_bucket, cost_basis_status
        FROM portfolio_positions
        WHERE snapshot_id = ?
        ORDER BY weight_pct DESC
        """,
        (snapshot["id"],),
    )
    return snapshot


def intraday_rules() -> dict[str, Any] | None:
    rules = one(
        """
        SELECT id, generated_at, last_updated, default_market_gate, allow_add_when_market_gate,
               allow_watch_when_market_gate, risk_reduce_always_allowed, manual_confirmation_required,
               staleness_status, staleness_reason, target_allocation_path, portfolio_snapshot_path,
               target_equity_pct, target_cash_short_pct, actual_equity_pct, actual_cash_short_pct
        FROM intraday_rules
        ORDER BY id DESC
        LIMIT 1
        """
    )
    if not rules:
        return None
    for key in [
        "allow_add_when_market_gate",
        "allow_watch_when_market_gate",
        "risk_reduce_always_allowed",
        "manual_confirmation_required",
    ]:
        rules[key] = bool(rules[key])
    rules["buckets"] = rows(
        """
        SELECT bucket_key, label, target_pct, actual_pct, gap_pct, color, note
        FROM intraday_bucket_rules
        WHERE intraday_rules_id = ?
        ORDER BY id
        """,
        (rules["id"],),
    )
    return rules


def system_check() -> dict[str, Any]:
    conn = connect_readonly()
    try:
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in [
                "artifacts",
                "current_modules",
                "market_scores",
                "subjects",
                "profiles",
                "valuations",
                "liquidity_gates",
                "portfolio_positions",
                "action_items",
                "research_first_items",
                "intraday_bucket_rules",
            ]
        }
    finally:
        conn.close()
    plan = latest_plan()
    intraday = intraday_rules()
    return {
        "database": "data/local/myinvest.sqlite",
        "mode": "read_only",
        "ratio_only_sanitizer": "ok",
        "counts": counts,
        "action_plan_status": {
            "quality": plan.get("quality_status") if plan else None,
            "staleness": plan.get("staleness_status") if plan else None,
        },
        "intraday_status": {
            "staleness": intraday.get("staleness_status") if intraday else None,
            "default_market_gate": intraday.get("default_market_gate") if intraday else None,
        },
    }


def decision_log_data() -> dict[str, Any]:
    return {
        "entries": rows(
            """
            SELECT entry_date, title, body, source_path
            FROM decision_log_entries
            ORDER BY id DESC
            LIMIT 30
            """
        )
    }


def market_score_data() -> dict[str, Any] | None:
    return one(
        """
        SELECT date, basis_trade_date, market_state, opportunity_score, crowding_penalty,
               market_position_score, equity_allocation_range, bond_cash_allocation_range,
               offensive_bucket_status, one_line_conclusion
        FROM market_scores
        ORDER BY id DESC
        LIMIT 1
        """
    )


def allocation_consistency_data() -> dict[str, Any]:
    target = target_allocation()
    intraday = intraday_rules()
    mismatches: list[dict[str, Any]] = []
    target_buckets = {
        item["bucket_key"]: item
        for item in (target or {}).get("buckets", [])
    }
    rule_buckets = {
        item["bucket_key"]: item
        for item in (intraday or {}).get("buckets", [])
    }
    for key in sorted(set(target_buckets) | set(rule_buckets)):
        left = target_buckets.get(key)
        right = rule_buckets.get(key)
        if not left or not right:
            mismatches.append({"bucket_key": key, "field": "presence", "target": bool(left), "intraday": bool(right)})
            continue
        for field in ["target_pct", "actual_pct", "gap_pct"]:
            left_value = left.get(field)
            right_value = right.get(field)
            if left_value is None or right_value is None:
                continue
            if abs(float(left_value) - float(right_value)) > 0.05:
                mismatches.append({"bucket_key": key, "field": field, "target": left_value, "intraday": right_value})
    return {"status": "ok" if not mismatches else "fail", "mismatches": mismatches}


@app.get("/api/health")
def api_health() -> dict[str, Any]:
    payload = {
        "ok": DB_PATH.exists(),
        "app": "MyInvest Web",
        "mode": "read-only",
        "current_only": True,
        "database": "data/local/myinvest.sqlite",
    }
    return response_payload(payload)


@app.get("/api/latest-index")
def api_latest_index() -> dict[str, Any]:
    data = {"generated_at": None, "modules": current_modules()}
    generated = [item.get("generated_at") for item in data["modules"] if item.get("generated_at")]
    if generated:
        data["generated_at"] = max(generated)
    return api_response(data, source={"path": "research/latest_index.json"})


@app.get("/api/modules/current")
def api_modules_current() -> dict[str, Any]:
    return api_response({"modules": current_modules()}, source={"path": "research/latest_index.json"})


@app.get("/api/current")
def api_current() -> dict[str, Any]:
    return api_response({"modules": current_modules(), "system_check": system_check()}, source={"path": "research/latest_index.json"})


@app.get("/api/action-plan/current")
def api_action_plan_current() -> dict[str, Any]:
    return api_response(action_plan_current_data(), source=source_for_module("action_plan"))


@app.get("/api/target-allocation/current")
def api_target_allocation_current() -> dict[str, Any]:
    return api_response({"target_allocation": target_allocation()}, source=source_for_module("target_allocation"))


@app.get("/api/research-first/current")
def api_research_first_current() -> dict[str, Any]:
    return api_response({"items": research_first_items()}, source=source_for_module("action_plan"))


@app.get("/api/portfolio/current")
def api_portfolio_current() -> dict[str, Any]:
    return api_response({"portfolio": portfolio_snapshot()}, source=source_for_module("portfolio_snapshot"))


@app.get("/api/intraday-rules/current")
def api_intraday_rules_current() -> dict[str, Any]:
    return api_response({"intraday_rules": intraday_rules()}, source=source_for_module("intraday_rules"))


@app.get("/api/system-check/current")
def api_system_check_current() -> dict[str, Any]:
    return api_response(system_check(), source={"path": "data/local/myinvest.sqlite"})


@app.get("/api/decision-log/current")
def api_decision_log_current() -> dict[str, Any]:
    return api_response(decision_log_data(), source={"path": "research/logs/decision_log.md"})


@app.get("/api/market-score/current")
def api_market_score_current() -> dict[str, Any]:
    return api_response({"market_score": market_score_data()}, source=source_for_module("market_score"))


@app.get("/api/theme-leaders/current")
def api_theme_leaders_current() -> dict[str, Any]:
    return api_response({"theme_leaders": source_for_module("theme_leaders")}, source=source_for_module("theme_leaders"))


@app.get("/api/sensitive-scan/current")
def api_sensitive_scan_current() -> dict[str, Any]:
    check = system_check()
    return api_response(
        {
            "status": "ok",
            "ratio_only_sanitizer": check["ratio_only_sanitizer"],
            "tables_scanned": sorted(check["counts"].keys()),
        },
        source={"path": "data/local/myinvest.sqlite"},
    )


@app.get("/api/allocation-consistency/current")
def api_allocation_consistency_current() -> dict[str, Any]:
    return api_response(allocation_consistency_data(), source=source_for_module("intraday_rules"))


@app.get("/api/registries/etfs/current")
def api_etf_registry_current() -> dict[str, Any]:
    return api_response(
        {
            "registry": source_for_module("etf_registry"),
            "subjects": rows(
                """
                SELECT code, name, subject_type, bucket_role, allocation_bucket, profile_status, stance
                FROM subjects
                WHERE subject_type = 'ETF' OR code LIKE '%.SH' OR code LIKE '%.SZ'
                ORDER BY code
                """
            ),
        },
        source=source_for_module("etf_registry"),
    )


@app.get("/api/registries/stocks/current")
def api_stock_registry_current() -> dict[str, Any]:
    return api_response({"registry": source_for_module("stock_registry")}, source=source_for_module("stock_registry"))


@app.get("/api/registries/buckets/current")
def api_bucket_registry_current() -> dict[str, Any]:
    return api_response(
        {"registry": source_for_module("bucket_registry"), "buckets": (target_allocation() or {}).get("buckets", [])},
        source=source_for_module("bucket_registry"),
    )


@app.get("/api/registries/liquidity-gates/current")
def api_liquidity_gates_current() -> dict[str, Any]:
    return api_response(
        {
            "registry": source_for_module("liquidity_gate_registry"),
            "gates": rows(
                """
                SELECT code, name, bucket_role, liquidity_status, liquidity_basis, valuation_status,
                       duration_boundary_confirmed, cash_equivalent_boundary,
                       interest_rate_risk_disclosed, credit_risk_disclosed, liquidity_risk_disclosed,
                       source_profile, valuation_source
                FROM liquidity_gates
                ORDER BY code
                """
            ),
        },
        source=source_for_module("liquidity_gate_registry"),
    )


@app.get("/api/registries/market-position-mapping/current")
def api_market_position_mapping_current() -> dict[str, Any]:
    return api_response(
        {
            "registry": source_for_module("market_position_mapping"),
            "ranges": rows(
                """
                SELECT score_min, score_max, market_state, equity_allocation_range,
                       bond_cash_allocation_range, offensive_bucket_status
                FROM market_position_mappings
                ORDER BY score_min
                """
            ),
        },
        source=source_for_module("market_position_mapping"),
    )


def page_context(request: Request, page: str, **extra: Any) -> dict[str, Any]:
    context = {"request": request, "page": page}
    context.update(extra)
    return context


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        page_context(
            request,
            "dashboard",
            modules=response_payload({"modules": current_modules()})["modules"],
            plan=response_payload({"plan": latest_plan()})["plan"],
            target=response_payload({"target": target_allocation()})["target"],
            portfolio=response_payload({"portfolio": portfolio_snapshot()})["portfolio"],
            checks=response_payload(system_check()),
        ),
    )


@app.get("/action-plan", response_class=HTMLResponse)
def action_plan_page(request: Request) -> HTMLResponse:
    data = action_plan_current_data()
    return templates.TemplateResponse(request, "action_plan.html", page_context(request, "action-plan", **data))


@app.get("/target-allocation", response_class=HTMLResponse)
def target_allocation_page(request: Request) -> HTMLResponse:
    data = {"target_allocation": target_allocation()}
    return templates.TemplateResponse(request, "target_allocation.html", page_context(request, "target-allocation", **data))


@app.get("/research-first", response_class=HTMLResponse)
def research_first_page(request: Request) -> HTMLResponse:
    data = {"items": research_first_items()}
    return templates.TemplateResponse(request, "research_first.html", page_context(request, "research-first", **data))


@app.get("/portfolio", response_class=HTMLResponse)
def portfolio_page(request: Request) -> HTMLResponse:
    data = {"portfolio": portfolio_snapshot()}
    return templates.TemplateResponse(request, "portfolio.html", page_context(request, "portfolio", **data))


@app.get("/intraday-rules", response_class=HTMLResponse)
def intraday_rules_page(request: Request) -> HTMLResponse:
    data = {"intraday_rules": intraday_rules()}
    return templates.TemplateResponse(request, "intraday_rules.html", page_context(request, "intraday-rules", **data))


@app.get("/decision-log", response_class=HTMLResponse)
def decision_log_page(request: Request) -> HTMLResponse:
    data = decision_log_data()
    return templates.TemplateResponse(request, "decision_log.html", page_context(request, "decision-log", **data))


@app.get("/system-checks", response_class=HTMLResponse)
def system_checks_page(request: Request) -> HTMLResponse:
    data = system_check()
    return templates.TemplateResponse(request, "system_checks.html", page_context(request, "system-checks", checks=data))
