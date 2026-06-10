from __future__ import annotations

import re
import subprocess
import sys
from typing import Any

from scripts import run_web


FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(total_asset|amount|market_value|shares|quantity|available_quantity|"
    r"trade_amount|profit_amount|account|full_account|order|fill|deal|"
    r"total_amount|share_count|available_qty|qty)($|_)",
    re.IGNORECASE,
)
FORBIDDEN_TEXT_RE = re.compile(
    r"(total asset|market value|profit amount|trade amount|share count|available quantity|"
    r"full account|order id|fill record|deal record|"
    r"\u603b\u8d44\u4ea7|\u91d1\u989d|\u5e02\u503c|\u80a1\u6570|\u6570\u91cf|"
    r"\u53ef\u7528\u6570\u91cf|\u4ea4\u6613\u91d1\u989d|\u76c8\u4e8f\u91d1\u989d|"
    r"\u8d26\u53f7|\u8ba2\u5355|\u6210\u4ea4)",
    re.IGNORECASE,
)
LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:(?!//)[\\/]|\\\\|/Users/|/home/)")


def walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, item in value.items():
            assert not FORBIDDEN_KEY_RE.search(str(key)), f"forbidden key {path}.{key}"
            walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            walk(item, f"{path}[{idx}]")
    elif isinstance(value, str):
        assert not LOCAL_PATH_RE.search(value), f"local path at {path}"
        assert not FORBIDDEN_TEXT_RE.search(value), f"forbidden text at {path}"


def test_dashboard_api_current_summary(client):
    response = client.get("/api/dashboard/current")
    assert response.status_code == 200
    payload = response.json()
    walk(payload)
    data = payload["data"]
    assert data["module"] == "dashboard_current"
    assert data["current_only"] is True
    for key in [
        "system_status",
        "market_position",
        "action_plan_summary",
        "allocation_summary",
        "subject_status_summary",
        "subject_gap_summary",
        "quick_links",
    ]:
        assert key in data
    assert isinstance(data["allocation_summary"]["bucket_gaps"], list)
    assert data["action_plan_summary"]["action_count"] >= 0
    assert data["subject_status_summary"]["subject_count"] >= 0
    assert data["subject_gap_summary"]["green_count"] >= 0
    cash_gate = data["subject_status_summary"].get("cash_equivalent_gate")
    if cash_gate:
        assert cash_gate["code"] == "511360.SH"
        assert cash_gate["bucket"] == "cash_short"


def test_dashboard_pages_render_and_use_dashboard_api(client):
    for path in ["/", "/dashboard"]:
        response = client.get(path)
        assert response.status_code == 200
        html = response.text
        assert "Research Dashboard" in html
        assert "/api/dashboard/current" in html
        assert "data-dashboard-section=\"system-status\"" in html
        assert "data-dashboard-section=\"market-position\"" in html
        assert "data-dashboard-section=\"action-plan-summary\"" in html
        assert "data-dashboard-section=\"allocation-summary\"" in html
        assert "data-dashboard-section=\"subject-summaries\"" in html
        assert "data-dashboard-section=\"quick-links\"" in html
        assert "bucketGapChart" in html
        assert not LOCAL_PATH_RE.search(html)
        assert not FORBIDDEN_TEXT_RE.search(html)


def test_dashboard_quick_links_resolve(client):
    data = client.get("/api/dashboard/current").json()["data"]
    links = data["quick_links"]
    assert {item["label"] for item in links} >= {
        "Action Plan",
        "Target Allocation",
        "Subject Status",
        "Subject Gap",
        "Themes",
        "Buckets",
        "Portfolio",
        "Intraday Rules",
        "Decision Log",
        "Decision Timeline",
        "History Snapshot",
    }
    for item in links:
        response = client.get(item["href"])
        assert response.status_code == 200, item


def test_dashboard_openapi_is_read_only(client):
    schema = client.get("/openapi.json").json()
    mutating = []
    for path, methods in schema.get("paths", {}).items():
        if path.startswith("/api"):
            bad = sorted(set(methods) & {"post", "put", "patch", "delete"})
            if bad:
                mutating.append((path, bad))
    assert mutating == []


def test_run_web_defaults_and_help():
    assert run_web.DEFAULT_HOST == "0.0.0.0"
    assert run_web.DEFAULT_PORT == 8000
    assert run_web.APP_IMPORT == "web.backend.app.main:app"
    run_web.ensure_repo_on_path()
    __import__("web.backend.app.main")
    parser = run_web.build_parser()
    args = parser.parse_args([])
    assert args.host == "0.0.0.0"
    assert args.port == 8000
    override = parser.parse_args(["--host", "127.0.0.1", "--port", "8100", "--reload"])
    assert override.host == "127.0.0.1"
    assert override.port == 8100
    assert override.reload is True
    proc = subprocess.run(
        [sys.executable, "scripts/run_web.py", "--help"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert proc.returncode == 0
    assert "--host" in proc.stdout
    assert "--port" in proc.stdout
