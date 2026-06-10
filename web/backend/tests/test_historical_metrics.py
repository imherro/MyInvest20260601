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


def test_historical_metrics_api_structure_and_safety(client):
    response = client.get("/api/historical-metrics")
    assert response.status_code == 200
    payload = response.json()
    walk(payload)
    data = payload["data"]
    assert data["module"] == "historical_metrics"
    assert data["current_only"] is True
    assert data["safety"]["ratio_only"] is True
    assert data["safety"]["read_only"] is True
    assert data["safety"]["uses_latest_index_modules"] is True
    assert data["safety"]["uses_latest_index_files"] is False
    assert data["summary"]["entity_count"] == len(data["entities"])
    assert set(data["aggregations"]) >= {"buckets", "subjects", "themes", "decision_types"}
    assert set(data["series"]) >= {"bucket_gap", "market_score"}


def test_historical_metrics_bucket_rows_match_history_gap(client):
    metrics = client.get("/api/historical-metrics").json()["data"]
    history = client.get("/api/history/gap-summary").json()["data"]
    metric_buckets = {row["bucket"]: row for row in metrics["aggregations"]["buckets"]}
    history_buckets = {row["bucket"]: row for row in history["buckets"]}
    assert set(history_buckets) <= set(metric_buckets)
    for bucket, expected in history_buckets.items():
        actual = metric_buckets[bucket]
        for key in ["actual_pct", "target_pct", "gap_pct"]:
            assert actual[key] == expected[key]
        assert actual["status"] == expected["gap_status"]
        assert actual["point_count"] == expected["history_point_count"]


def test_historical_metrics_subject_theme_and_decision_aggregations(client):
    data = client.get("/api/historical-metrics").json()["data"]
    assert data["aggregations"]["subjects"]
    assert data["aggregations"]["themes"]
    assert data["aggregations"]["decision_types"]
    assert any(row["entity_id"] == "subject-511360.SH" for row in data["aggregations"]["subjects"])
    assert any(row["entity_type"] == "decision_type" for row in data["entities"])


def test_historical_metrics_detail_and_missing(client):
    data = client.get("/api/historical-metrics").json()["data"]
    entity_id = data["entities"][0]["entity_id"]
    response = client.get(f"/api/historical-metrics/{entity_id}")
    assert response.status_code == 200
    payload = response.json()
    walk(payload)
    assert payload["data"]["entity"]["entity_id"] == entity_id

    missing = client.get("/api/historical-metrics/NO_SUCH_ENTITY")
    assert missing.status_code == 404
    walk(missing.json())


def test_historical_metrics_page_hooks_and_safety(client):
    response = client.get("/historical-metrics")
    assert response.status_code == 200
    html = response.text
    assert "Historical Metrics" in html
    assert "/api/historical-metrics" in html
    assert "data-historical-metrics-chart" in html
    assert "historicalMetricsChart" in html
    assert "historicalMetricsTooltip" in html
    assert "data-table-search=\"historicalMetricTable\"" in html
    assert "data-table-filter=\"historicalMetricTable\"" in html
    assert "historicalMetricRows" in html
    assert not LOCAL_PATH_RE.search(html)


def test_historical_metrics_no_current_mutation(client):
    before = client.get("/api/latest-index").json()
    response = client.get("/api/historical-metrics")
    assert response.status_code == 200
    after = client.get("/api/latest-index").json()
    assert json.dumps(before, sort_keys=True) == json.dumps(after, sort_keys=True)
    text = json.dumps(response.json(), ensure_ascii=False, sort_keys=True).replace("\\", "/").lower()
    for term in ["temp/", "web_runtime", ".sqlite", ".db", ".env", ".zip", ".log"]:
        assert term not in text


def test_historical_metrics_openapi_is_read_only(client):
    schema = client.get("/openapi.json").json()
    mutating = []
    for path, methods in schema.get("paths", {}).items():
        if path.startswith("/api"):
            bad = sorted(set(methods) & {"post", "put", "patch", "delete"})
            if bad:
                mutating.append((path, bad))
    assert mutating == []


def test_historical_metrics_current_only_and_no_hardcoded_timestamps():
    source = open("web/backend/app/services/historical_metrics.py", encoding="utf-8").read()
    assert "latest_index.files" not in source
    assert "[\"files\"]" not in source
    assert "['files']" not in source
    assert "generate_action_plan.py" not in source
    assert "generate_target_allocation.py" not in source
    assert not TIMESTAMP_RE.search(source)
