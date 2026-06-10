from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WEB_ROOT = ROOT / "web"
BACKEND_ROOT = WEB_ROOT / "backend"
APP_ROOT = BACKEND_ROOT / "app"
TEMPLATE_DIR = APP_ROOT / "templates"
STATIC_DIR = APP_ROOT / "static"

LATEST_INDEX_PATH = ROOT / "research" / "latest_index.json"
DECISION_LOG_PATH = ROOT / "research" / "logs" / "decision_log.md"
WEB_DB_DIR = ROOT / "temp" / "web_db"
WEB_RUNTIME_DIR = ROOT / "temp" / "web_runtime"
DB_PATH = WEB_DB_DIR / "myinvest.sqlite"

EXECUTABLE_ACTIONS = {"buy", "add", "reduce", "sell"}
CURRENT_CONFIG_MODULES = {
    "bucket_registry",
    "intraday_watchlist",
    "liquidity_gate_registry",
    "market_position_mapping",
}
REQUIRED_CURRENT_MODULES = {
    "action_plan",
    "target_allocation",
    "intraday_rules",
    "portfolio_snapshot",
    "market_score",
    "market_position_mapping",
    "bucket_registry",
    "liquidity_gate_registry",
    "etf_registry",
}
