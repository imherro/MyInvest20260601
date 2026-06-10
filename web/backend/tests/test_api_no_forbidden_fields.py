from __future__ import annotations

import re
from typing import Any


FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(amount|market_value|profit_amount|total_amount|total_asset|share_count|shares|quantity|qty|"
    r"available_qty|available_quantity|trade_amount|account|full_account|order|fill|deal)($|_)",
    re.IGNORECASE,
)
LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:(?!//)[\\/]|\\\\|/Users/|/home/)")
ALLOWED_FORBIDDEN_KEY_PATHS = {"$.safety.no_order_generation"}


def walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, item in value.items():
            key_path = f"{path}.{key}"
            if key_path not in ALLOWED_FORBIDDEN_KEY_PATHS:
                assert not FORBIDDEN_KEY_RE.search(str(key)), f"forbidden key {key_path}"
            walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            walk(item, f"{path}[{idx}]")
    elif isinstance(value, str):
        assert not LOCAL_PATH_RE.search(value), f"local path at {path}"


def test_current_apis_do_not_return_forbidden_fields(client):
    paths = [
        "/api/health",
        "/api/environment/status",
        "/api/user/preferences",
        "/api/user/preferences/default",
        "/api/dashboard/summary",
        "/api/dashboard/user_metrics/default",
        "/api/dashboard/current",
        "/api/current",
        "/api/latest-index",
        "/api/modules/current",
        "/api/subjects/status",
        "/api/subjects/status/511360.SH",
        "/api/subjects/freshness",
        "/api/subjects/gap",
        "/api/themes/status",
        "/api/buckets/status",
        "/api/buckets/drilldown?detail=full",
        "/api/subjects/drilldown?detail=full",
        "/api/subjects/drilldown?subject=511360.SH&detail=full",
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
        "/api/history/gap-summary",
        "/api/research-first/current",
        "/api/portfolio/current",
        "/api/intraday-rules/current",
        "/api/system-check/current",
        "/api/decision-log/current",
        "/api/decision-timeline",
        "/api/decision-timeline/current-action-plan",
        "/api/historical-metrics",
        "/api/historical-metrics/bucket-attack_mainline",
        "/api/allocation-consistency/current",
        "/api/export/review_package?format=json",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
        walk(response.json())
