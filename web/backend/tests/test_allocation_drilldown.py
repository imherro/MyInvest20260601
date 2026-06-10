from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote


FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(total_asset|amount|market_value|shares|quantity|available_quantity|"
    r"trade_amount|profit_amount|account|full_account|order|fill|deal|"
    r"total_amount|share_count|available_qty|qty)($|_)",
    re.IGNORECASE,
)
LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:(?!//)[\\/]|\\\\|/Users/|/home/)")
ACTION_STATUSES = {"buy", "add", "reduce", "sell"}


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
    source = open("web/backend/app/services/allocation_drilldown.py", encoding="utf-8").read()
    assert "latest_index.files" not in source
    assert "[\"files\"]" not in source
    assert "['files']" not in source
