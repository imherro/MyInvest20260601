from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

from web.backend.app.repositories import allocation_repo as allocation_repo_module


FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(total_asset|amount|market_value|shares|quantity|available_quantity|"
    r"trade_amount|profit_amount|account|full_account|order|fill|deal|"
    r"total_amount|share_count|available_qty|qty)($|_)",
    re.IGNORECASE,
)
LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:(?!//)[\\/]|\\\\|/Users/|/home/)")
ACTION_STATUSES = {"buy", "add", "reduce", "sell"}
ROOT = Path(__file__).resolve().parents[3]


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


def test_bucket_drilldown_api_structure_and_consistency(client):
    response = client.get("/api/buckets/drilldown?detail=full")
    assert response.status_code == 200
    payload = response.json()
    walk(payload)
    data = payload["data"]
    assert data["module"] == "allocation_bucket_drilldown"
    assert data["current_only"] is True
    assert data["safety"]["read_only"] is True
    assert data["safety"]["uses_latest_index_modules"] is True
    assert data["safety"]["uses_latest_index_files"] is False
    assert data["buckets"]
    assert data["summary"]["bucket_count"] == len(data["buckets"])

    target = client.get("/api/target-allocation/current").json()["data"]["target_allocation"]
    target_map = {row["bucket"]: row for row in target["buckets"]}
    for bucket in data["buckets"]:
        expected = target_map[bucket["bucket"]]
        assert bucket["actual_pct"] == expected["actual_pct"]
        assert bucket["target_pct"] == expected["target_pct"]
        assert bucket["gap_pct"] == expected["gap_pct"]
        assert bucket["gap_status"] in {"green", "yellow", "red", "unknown"}
        assert "subjects" in bucket
        for subject in bucket["subjects"]:
            assert subject["gate_conclusion"] not in ACTION_STATUSES
            assert subject["bucket"] == bucket["bucket"]


def test_bucket_drilldown_filter_and_missing(client):
    buckets = client.get("/api/buckets/drilldown").json()["data"]["buckets"]
    bucket = buckets[0]["bucket"]
    response = client.get(f"/api/buckets/drilldown?bucket={quote(bucket, safe='')}&detail=full")
    assert response.status_code == 200
    payload = response.json()
    walk(payload)
    rows = payload["data"]["buckets"]
    assert len(rows) == 1
    assert rows[0]["bucket"] == bucket

    missing = client.get("/api/buckets/drilldown?bucket=NO_SUCH_BUCKET")
    assert missing.status_code == 404
    walk(missing.json())


def test_subject_drilldown_api_structure_and_research_first(client):
    response = client.get("/api/subjects/drilldown?detail=full")
    assert response.status_code == 200
    payload = response.json()
    walk(payload)
    data = payload["data"]
    assert data["module"] == "allocation_subject_drilldown"
    assert data["current_only"] is True
    assert data["safety"]["read_only"] is True
    assert data["subjects"]
    assert data["summary"]["subject_count"] == len(data["subjects"])

    for subject in data["subjects"]:
        assert subject["gate_conclusion"] not in ACTION_STATUSES
        assert subject["research_first_status"] in {"pass", "research_first", "blocked", "unknown"}
        if subject["research_first_status"] in {"research_first", "blocked"}:
            assert (
                subject["blocking_reason"]
                or subject["profile_status"] != "pass"
                or subject["valuation_status"] != "pass"
                or subject["liquidity_status"] != "pass"
            )


def test_subject_drilldown_filter_511360_and_missing(client):
    response = client.get("/api/subjects/drilldown?subject=511360.SH&detail=full")
    assert response.status_code == 200
    payload = response.json()
    walk(payload)
    rows = payload["data"]["subjects"]
    assert len(rows) == 1
    cash = rows[0]
    assert cash["code"] == "511360.SH"
    assert cash["bucket"] == "cash_short"
    assert cash["subject_type"] == "cash_equivalent"
    assert cash["profile_status"] == "pass"
    assert cash["valuation_status"] == "pass"
    assert cash["liquidity_status"] == "pass"

    missing = client.get("/api/subjects/drilldown?subject=NO_SUCH_SUBJECT")
    assert missing.status_code == 404
    walk(missing.json())


def test_drilldown_pages_hooks_and_safety(client):
    bucket_page = client.get("/buckets/drilldown")
    assert bucket_page.status_code == 200
    bucket_html = bucket_page.text
    assert "Bucket Allocation Drilldown" in bucket_html
    assert "/api/buckets/drilldown?detail=full" in bucket_html
    assert "bucketDrilldownChart" in bucket_html
    assert "data-table-search=\"bucketDrilldownTable\"" in bucket_html
    assert "data-table-filter=\"bucketDrilldownTable\"" in bucket_html
    assert "bucketDrilldownRows" in bucket_html
    assert not LOCAL_PATH_RE.search(bucket_html)

    subject_page = client.get("/subjects/drilldown")
    assert subject_page.status_code == 200
    subject_html = subject_page.text
    assert "Subject Allocation Drilldown" in subject_html
    assert "/api/subjects/drilldown?detail=full" in subject_html
    assert "data-table-search=\"subjectDrilldownTable\"" in subject_html
    assert "data-table-filter=\"subjectDrilldownTable\"" in subject_html
    assert "subjectDrilldownRows" in subject_html
    assert not LOCAL_PATH_RE.search(subject_html)


def test_allocation_drilldown_does_not_use_latest_index_files():
    source = (ROOT / "web" / "backend" / "app" / "services" / "allocation_drilldown.py").read_text(encoding="utf-8")
    assert "latest_index.files" not in source
    assert "[\"files\"]" not in source
    assert "['files']" not in source
    assert ".read_text(" not in source
    assert ".execute(" not in source
    assert "AllocationRepository" in source


def test_allocation_repository_delegates_to_database_service(monkeypatch):
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    class FakeDatabaseService:
        def __init__(self, session):
            calls.append(("init", str(session), None))

        def fetch_one(self, sql, params=None):
            calls.append(("one", sql, params))
            if "FROM target_allocations" in sql:
                return {"id": 1, "generated_at": "2026-06-09", "basis_trade_date": "20260608"}
            if "FROM portfolio_snapshots" in sql:
                return {"id": 2, "generated_at": "2026-06-09", "basis_trade_date": "20260608"}
            return None

        def fetch_all(self, sql, params=None):
            calls.append(("all", sql, params))
            if "FROM bucket_allocations" in sql:
                return [{"bucket": "cash_short", "actual_pct": 10.0, "target_pct": 10.0, "gap_pct": 0.0}]
            if "FROM portfolio_positions" in sql:
                return [{"code": "511360.SH", "name": "cash", "bucket": "cash_short", "position_pct": 10.0}]
            return []

        def source_for_module(self, module):
            calls.append(("source", module, None))
            return {"module": module, "path": f"research/{module}.json"}

    monkeypatch.setattr(allocation_repo_module, "DatabaseService", FakeDatabaseService)

    repo = allocation_repo_module.AllocationRepository("sentinel")
    target = repo.target_allocation()
    portfolio = repo.portfolio_snapshot()
    sources = repo.source_modules(["target_allocation", "portfolio_snapshot"])

    assert target and target["buckets"][0]["bucket"] == "cash_short"
    assert portfolio and portfolio["positions"][0]["code"] == "511360.SH"
    assert sources["target_allocation"]["path"] == "research/target_allocation.json"
    sql_text = "\n".join(call[1] for call in calls if call[0] in {"one", "all"})
    assert "latest_index.files" not in sql_text
    for blocked in ["PRAGMA", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP"]:
        assert blocked not in sql_text.upper()


def test_allocation_repository_db_access_boundaries():
    source = (ROOT / "web" / "backend" / "app" / "repositories" / "allocation_repo.py").read_text(encoding="utf-8")
    assert "DatabaseService" in source
    assert ".fetch_one(" in source
    assert ".fetch_all(" in source
    assert ".execute(" not in source
    assert ".read_text(" not in source
    assert "latest_index.files" not in source
