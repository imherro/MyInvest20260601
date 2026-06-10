from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from web.backend.app.repositories import bucket_history_repo as bucket_history_repo_module


FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(total_asset|amount|market_value|shares|quantity|available_quantity|"
    r"trade_amount|profit_amount|account|full_account|order|fill|deal|"
    r"total_amount|share_count|available_qty|qty)($|_)",
    re.IGNORECASE,
)
LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:(?!//)[\\/]|\\\\|/Users/|/home/)")
TIMESTAMP_RE = re.compile(r"20\d{2}[-_]?\d{2}[-_]?\d{2}[_-]\d{6}")
ROOT = Path(__file__).resolve().parents[3]


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
    source = (ROOT / "web" / "backend" / "app" / "services" / "history_gap_dashboard.py").read_text(encoding="utf-8")
    assert "latest_index.files" not in source
    assert "[\"files\"]" not in source
    assert "['files']" not in source
    assert ".read_text(" not in source
    assert ".execute(" not in source
    assert "BucketHistoryRepository" in source
    assert not TIMESTAMP_RE.search(source)


def test_bucket_history_repository_delegates_to_database_service(monkeypatch):
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    class FakeDatabaseService:
        def __init__(self, session):
            calls.append(("init", str(session), None))

        def fetch_one(self, sql, params=None):
            calls.append(("one", sql, params))
            return {"id": 1, "generated_at": "2026-06-09", "basis_trade_date": "20260608"}

        def fetch_all(self, sql, params=None):
            calls.append(("all", sql, params))
            return [{"bucket": "cash_short", "actual_pct": 10.0, "target_pct": 10.0, "gap_pct": 0.0}]

        def source_for_module(self, module):
            calls.append(("source", module, None))
            return {"module": module, "path": f"research/{module}.json"}

    monkeypatch.setattr(bucket_history_repo_module, "DatabaseService", FakeDatabaseService)

    repo = bucket_history_repo_module.BucketHistoryRepository("sentinel")
    target = repo.current_target_allocation()
    sources = repo.source_modules(["target_allocation"])

    assert target and target["buckets"][0]["bucket"] == "cash_short"
    assert sources["target_allocation"]["path"] == "research/target_allocation.json"
    sql_text = "\n".join(call[1] for call in calls if call[0] in {"one", "all"})
    for blocked in ["PRAGMA", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP"]:
        assert blocked not in sql_text.upper()


def test_bucket_history_repository_db_access_boundaries():
    source = (ROOT / "web" / "backend" / "app" / "repositories" / "bucket_history_repo.py").read_text(
        encoding="utf-8"
    )
    assert "DatabaseService" in source
    assert ".fetch_one(" in source
    assert ".fetch_all(" in source
    assert ".execute(" not in source
    assert ".read_text(" not in source
    assert "latest_index.files" not in source
