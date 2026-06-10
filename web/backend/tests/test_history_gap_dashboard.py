from __future__ import annotations

import json
import re
from typing import Any


FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(total_asset|amount|market_value|shares|quantity|available_quantity|"
    r"trade_amount|profit_amount|account|full_account|order|fill|deal|"
    r"total_amount|share_count|available_qty|qty)($|_)",
    re.IGNORECASE,
)
LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:(?!//)[\\/]|\\\\|/Users/|/home/)")
TIMESTAMP_RE = re.compile(r"20\d{2}[-_]?\d{2}[-_]?\d{2}[_-]\d{6}")


def walk(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            assert not FORBIDDEN_KEY_RE.search(str(key)), f"forbidden key {path}.{key}"
            walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            walk(item, f"{path}[{idx}]")
    elif isinstance(value, str):
        assert not LOCAL_PATH_RE.search(value), f"local path at {path}"


def test_history_gap_dashboard_api_structure_and_safety(client):
    response = client.get("/api/history/gap-summary")
    assert response.status_code == 200
    payload = response.json()
    walk(payload)
    data = payload["data"]
    assert data["module"] == "history_gap_dashboard"
    assert data["current_only"] is True
    assert data["safety"]["ratio_only"] is True
    assert data["safety"]["current_only"] is True
    assert set(data["summary"]) >= {
        "bucket_count",
        "green_count",
        "yellow_count",
        "red_count",
        "unknown_count",
        "alert_count",
        "history_source_count",
    }
    assert data["summary"]["bucket_count"] == len(data["buckets"])


def test_history_gap_dashboard_bucket_rows_match_current_target(client):
    target = client.get("/api/target-allocation/current").json()["data"]["target_allocation"]
    expected = {row["bucket"]: row for row in target["buckets"]}
    data = client.get("/api/history/gap-summary").json()["data"]
    buckets = {row["bucket"]: row for row in data["buckets"]}
    assert set(expected) <= set(buckets)
    for bucket, row in expected.items():
        actual = buckets[bucket]
        for key in ["actual_pct", "target_pct", "gap_pct"]:
            assert actual[key] == row[key]
        assert actual["gap_status"] in {"green", "yellow", "red", "unknown"}
        assert actual["alert_status"] in {"ok", "review", "attention", "unknown"}
        assert actual["history_point_count"] >= 1
        assert any(point["source_kind"] == "current_reference" for point in actual["timeline"])


def test_history_gap_dashboard_detail_and_missing(client):
    data = client.get("/api/history/gap-summary").json()["data"]
    if data["buckets"]:
        bucket = data["buckets"][0]["bucket"]
        response = client.get(f"/api/history/gap-summary/{bucket}")
        assert response.status_code == 200
        walk(response.json())
        assert response.json()["data"]["bucket"]["bucket"] == bucket
    missing = client.get("/api/history/gap-summary/NO_SUCH_BUCKET")
    assert missing.status_code == 404
    walk(missing.json())


def test_history_gap_dashboard_page_hooks_and_safety(client):
    response = client.get("/history/gap-dashboard")
    assert response.status_code == 200
    html = response.text
    assert "History Gap Dashboard" in html
    assert "/api/history/gap-summary" in html
    assert "data-history-gap-chart" in html
    assert "historyGapChart" in html
    assert "historyGapTooltip" in html
    assert "data-table-search=\"historyGapTable\"" in html
    assert "data-table-filter=\"historyGapTable\"" in html
    assert "data-table-search=\"historyEntryTable\"" in html
    assert "historyGapRows" in html
    assert "historyEntryRows" in html
    assert not LOCAL_PATH_RE.search(html)


def test_history_gap_dashboard_no_runtime_or_current_mutation(client):
    before = client.get("/api/latest-index").json()
    response = client.get("/api/history/gap-summary")
    assert response.status_code == 200
    after = client.get("/api/latest-index").json()
    assert json.dumps(before, sort_keys=True) == json.dumps(after, sort_keys=True)
    text = json.dumps(response.json(), ensure_ascii=False, sort_keys=True).replace("\\", "/").lower()
    for term in ["temp/", "web_runtime", ".sqlite", ".db", ".env", ".zip", ".log"]:
        assert term not in text


def test_history_gap_dashboard_openapi_is_read_only(client):
    schema = client.get("/openapi.json").json()
    mutating = []
    for path, methods in schema.get("paths", {}).items():
        if path.startswith("/api"):
            bad = sorted(set(methods) & {"post", "put", "patch", "delete"})
            if bad:
                mutating.append((path, bad))
    assert mutating == []


def test_history_gap_dashboard_current_only_and_no_hardcoded_timestamps():
    source = open("web/backend/app/services/history_gap_dashboard.py", encoding="utf-8").read()
    assert "latest_index.files" not in source
    assert "[\"files\"]" not in source
    assert "['files']" not in source
    assert not TIMESTAMP_RE.search(source)
