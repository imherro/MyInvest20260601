from __future__ import annotations

import re
from typing import Any


FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(amount|market_value|profit_amount|total_amount|total_asset|share_count|shares|quantity|qty|"
    r"available_qty|available_quantity|trade_amount|account|full_account|order|fill|deal)($|_)",
    re.IGNORECASE,
)
LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|/Users/|/home/)")


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
        "/api/current",
        "/api/action-plan/current",
        "/api/target-allocation/current",
        "/api/research-first/current",
        "/api/portfolio/current",
        "/api/intraday-rules/current",
        "/api/system-check/current",
        "/api/decision-log/current",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
        walk(response.json())
