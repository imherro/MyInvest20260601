from __future__ import annotations

import re
from typing import Any


FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(amount|market_value|profit_amount|total_amount|total_asset|share_count|shares|quantity|qty|"
    r"available_qty|available_quantity|trade_amount|account|full_account|order|fill|deal)($|_)",
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


def test_current_apis_do_not_return_forbidden_fields(client):
    paths = [
        "/api/health",
        "/api/current",
        "/api/latest-index",
        "/api/modules/current",
        "/api/subjects/status",
        "/api/subjects/status/511360.SH",
        "/api/market-position/mapping",
        "/api/market-position/current",
        "/api/market-position/score/25",
        "/api/market-position/score/30",
        "/api/market-position/score/31",
        "/api/market-position/score/100",
        "/api/action-plan/current",
        "/api/target-allocation/current",
        "/api/target-allocation/shadow",
        "/api/target-allocation/shadow/compare",
        "/api/target-allocation/shadow/export?format=json",
        "/api/target-allocation/candidate-audit",
        "/api/target-allocation/candidate-audit?format=json",
        "/api/history/export",
        "/api/history/export?format=json",
        "/api/research-first/current",
        "/api/portfolio/current",
        "/api/intraday-rules/current",
        "/api/system-check/current",
        "/api/decision-log/current",
        "/api/allocation-consistency/current",
        "/api/export/review_package?format=json",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
        walk(response.json())
