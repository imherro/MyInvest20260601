from __future__ import annotations

import re
import string
from typing import Any


FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(amount|market_value|profit_amount|total_amount|total_asset|share_count|shares|quantity|qty|"
    r"available_qty|available_quantity|trade_amount|account|full_account|order|fill|deal)($|_)",
    re.IGNORECASE,
)
BACKSLASH = chr(92)


def has_local_path(value: str) -> bool:
    user_home = "/" + "Users" + "/"
    unix_home = "/" + "home" + "/"
    if user_home in value or unix_home in value:
        return True
    if value.startswith(BACKSLASH + BACKSLASH):
        return True
    return any(f"{letter}:{BACKSLASH}" in value or f"{letter}:/" in value for letter in string.ascii_letters)


def walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, item in value.items():
            assert not FORBIDDEN_KEY_RE.search(str(key)), f"forbidden key {path}.{key}"
            walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            walk(item, f"{path}[{idx}]")
    elif isinstance(value, str):
        assert not has_local_path(value), f"local path at {path}"


def test_subject_freshness_endpoint_contract(client):
    response = client.get("/api/subjects/freshness")
    assert response.status_code == 200
    payload = response.json()
    walk(payload)

    data = payload["data"]
    assert data["current_only"] is True
    assert data["rows"]
    assert data["summary"]["subject_count"] == len(data["rows"])
    assert isinstance(data["summary"]["stale_count"], int)
    for row in data["rows"]:
        assert {
            "code",
            "name",
            "subject_type",
            "bucket",
            "last_update_timestamp",
            "basis_trade_date",
            "staleness_flag",
            "staleness_reason",
            "source_paths",
        } <= set(row)
        assert isinstance(row["staleness_flag"], bool)


def test_subject_gap_endpoint_contract_and_bucket_consistency(client):
    response = client.get("/api/subjects/gap")
    assert response.status_code == 200
    payload = response.json()
    walk(payload)

    data = payload["data"]
    assert data["current_only"] is True
    assert data["rows"]
    assert data["summary"]["subject_count"] == len(data["rows"])
    assert set(data["summary"]) >= {"green_count", "yellow_count", "red_count", "unknown_count", "stale_count"}

    target = client.get("/api/target-allocation/current").json()["data"]["target_allocation"]
    bucket_map = {row["bucket"]: row for row in target["buckets"]}
    for row in data["rows"]:
        assert {
            "code",
            "name",
            "subject_type",
            "bucket",
            "position_pct",
            "actual_pct",
            "target_pct",
            "gap_pct",
            "gap_status",
            "last_update_timestamp",
            "staleness_flag",
            "source_paths",
        } <= set(row)
        assert row["gap_status"] in {"green", "yellow", "red", "unknown"}
        if row["bucket"] in bucket_map and row["actual_pct"] is not None:
            expected = bucket_map[row["bucket"]]
            assert row["actual_pct"] == expected["actual_pct"]
            assert row["target_pct"] == expected["target_pct"]
            assert row["gap_pct"] == expected["gap_pct"]


def test_subject_gap_511360_uses_cash_short_bucket(client):
    rows = client.get("/api/subjects/gap").json()["data"]["rows"]
    cash = next((row for row in rows if row["code"] == "511360.SH"), None)
    assert cash is not None
    assert cash["bucket"] == "cash_short"
    assert cash["position_pct"] is not None
    assert cash["actual_pct"] is not None
    assert cash["target_pct"] is not None


def test_subject_gap_page_hooks(client):
    response = client.get("/subjects/gap")
    assert response.status_code == 200
    html = response.text
    assert "Data Freshness & Gap Center" in html
    assert "data-table-search=\"subjectGapTable\"" in html
    assert "data-sort=\"number\"" in html
    assert "subjectGapRows" in html
    assert not has_local_path(html)
