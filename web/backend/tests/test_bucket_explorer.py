from __future__ import annotations

import re
from typing import Any


FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(total_asset|amount|market_value|shares|quantity|available_quantity|"
    r"trade_amount|profit_amount|account|full_account|order|fill|deal|"
    r"total_amount|share_count|available_qty|qty)($|_)",
    re.IGNORECASE,
)
LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:(?!//)[\\/]|\\\\|/Users/|/home/)")
ACTION_STATUSES = {"buy", "add", "reduce", "sell"}
TIMESTAMP_RE = re.compile(r"20\d{2}[-_]?\d{2}[-_]?\d{2}[_-]\d{6}")


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


def test_bucket_explorer_api_structure_and_safety(client):
    response = client.get("/api/buckets/status")
    assert response.status_code == 200
    payload = response.json()
    walk(payload)
    data = payload["data"]
    assert data["module"] == "bucket_explorer"
    assert data["current_only"] is True
    assert data["safety"] == {"ratio_only": True, "current_only": True}
    assert set(data["summary"]) >= {
        "bucket_count",
        "overweight_count",
        "underweight_count",
        "research_first_count",
        "blocked_count",
    }
    assert isinstance(data["buckets"], list)
    assert data["summary"]["bucket_count"] == len(data["buckets"])


def test_bucket_explorer_contains_target_buckets_and_subjects(client):
    target = client.get("/api/target-allocation/current").json()["data"]["target_allocation"]
    target_buckets = {row["bucket"] for row in target["buckets"]}
    data = client.get("/api/buckets/status").json()["data"]
    bucket_names = {row["bucket"] for row in data["buckets"]}
    assert target_buckets <= bucket_names
    for bucket in data["buckets"]:
        assert set(bucket) >= {
            "bucket",
            "actual_pct",
            "target_pct",
            "gap_pct",
            "gap_status",
            "subject_count",
            "pass_count",
            "research_first_count",
            "stale_count",
            "risk_notes",
            "subjects",
        }
        assert bucket["gap_status"] not in ACTION_STATUSES
        for subject in bucket["subjects"]:
            assert subject["gate_conclusion"] not in ACTION_STATUSES
            assert set(subject) >= {
                "code",
                "name",
                "subject_type",
                "position_pct",
                "profile_status",
                "valuation_status",
                "liquidity_status",
                "research_first_status",
                "gate_conclusion",
                "blocking_reason",
                "source_paths",
            }


def test_cash_short_and_legacy_watch_are_neutral(client):
    data = client.get("/api/buckets/status").json()["data"]
    buckets = {row["bucket"]: row for row in data["buckets"]}
    if "cash_short" in buckets:
        assert any(subject.get("code") == "511360.SH" for subject in buckets["cash_short"]["subjects"])
    if "legacy_watch" in buckets:
        legacy = buckets["legacy_watch"]
        if legacy.get("actual_pct", 0) > 0 and legacy.get("target_pct") == 0:
            assert legacy["gap_status"] == "zero_target_nonzero_actual"
            assert legacy["gap_status"] not in ACTION_STATUSES


def test_bucket_detail_and_missing(client):
    data = client.get("/api/buckets/status").json()["data"]
    if data["buckets"]:
        bucket = data["buckets"][0]["bucket"]
        response = client.get(f"/api/buckets/status/{bucket}")
        assert response.status_code == 200
        walk(response.json())
        assert response.json()["data"]["bucket"]["bucket"] == bucket
    missing = client.get("/api/buckets/status/NO_SUCH_BUCKET")
    assert missing.status_code == 404
    walk(missing.json())


def test_buckets_page_hooks_and_safety(client):
    response = client.get("/buckets")
    assert response.status_code == 200
    html = response.text
    assert "Bucket Explorer" in html
    assert "/api/buckets/status" in html
    assert "data-table-search=\"bucketTable\"" in html
    assert "data-table-search=\"bucketSubjectTable\"" in html
    assert "data-table-filter=\"bucketTable\"" in html
    assert "data-table-filter=\"bucketSubjectTable\"" in html
    assert "data-filter-key=\"gap_status\"" in html
    assert "data-filter-key=\"gate_conclusion\"" in html
    assert "bucketRows" in html
    assert "bucketSubjectRows" in html
    assert not LOCAL_PATH_RE.search(html)


def test_bucket_openapi_is_read_only(client):
    schema = client.get("/openapi.json").json()
    mutating = []
    for path, methods in schema.get("paths", {}).items():
        if path.startswith("/api"):
            bad = sorted(set(methods) & {"post", "put", "patch", "delete"})
            if bad:
                mutating.append((path, bad))
    assert mutating == []


def test_bucket_explorer_current_only_and_no_hardcoded_timestamps():
    source = open("web/backend/app/services/bucket_explorer.py", encoding="utf-8").read()
    assert ".read_text(" not in source
    assert ".execute(" not in source
    assert "latest_index.files" not in source
    assert "[\"files\"]" not in source
    assert "['files']" not in source
    assert not TIMESTAMP_RE.search(source)
