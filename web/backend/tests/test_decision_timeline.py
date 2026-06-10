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


def test_decision_timeline_api_structure_and_safety(client):
    response = client.get("/api/decision-timeline")
    assert response.status_code == 200
    payload = response.json()
    walk(payload)
    data = payload["data"]
    assert data["module"] == "decision_timeline"
    assert data["current_only"] is True
    assert data["safety"]["ratio_only"] is True
    assert data["safety"]["read_only"] is True
    assert data["safety"]["uses_latest_index_modules"] is True
    assert data["safety"]["uses_latest_index_files"] is False
    assert data["summary"]["event_count"] == len(data["events"])
    assert {"action_plan", "target_allocation", "decision_log"} <= {event["event_type"] for event in data["events"]}
    assert data["summary"]["decision_log_count"] > 0


def test_decision_timeline_current_action_and_target_events(client):
    data = client.get("/api/decision-timeline").json()["data"]
    events = {event["event_id"]: event for event in data["events"]}
    action_event = events["current-action-plan"]
    target_event = events["current-target-allocation"]

    action_plan = client.get("/api/action-plan/current").json()["data"]["action_plan"]
    target = client.get("/api/target-allocation/current").json()["data"]["target_allocation"]

    assert action_event["timestamp"] == action_plan["generated_at"]
    assert action_event["details"]["action_count"] == len(action_plan["actions"])
    assert action_event["details"]["research_first_count"] == len(action_plan["research_first"])
    assert target_event["timestamp"] == target["generated_at"]
    assert target_event["details"]["bucket_count"] == len(target["buckets"])
    assert target_event["details"]["buckets"] == target["buckets"]


def test_decision_timeline_detail_and_missing(client):
    data = client.get("/api/decision-timeline").json()["data"]
    event_id = data["events"][0]["event_id"]
    response = client.get(f"/api/decision-timeline/{event_id}")
    assert response.status_code == 200
    payload = response.json()
    walk(payload)
    assert payload["data"]["event"]["event_id"] == event_id

    missing = client.get("/api/decision-timeline/NO_SUCH_EVENT")
    assert missing.status_code == 404
    walk(missing.json())


def test_decision_timeline_page_hooks_and_safety(client):
    response = client.get("/decision-timeline")
    assert response.status_code == 200
    html = response.text
    assert "Decision Timeline" in html
    assert "/api/decision-timeline" in html
    assert "data-decision-timeline-chart" in html
    assert "decisionTimelineChart" in html
    assert "decisionTimelineTooltip" in html
    assert "data-table-search=\"decisionTimelineTable\"" in html
    assert "data-table-filter=\"decisionTimelineTable\"" in html
    assert "decisionTimelineRows" in html
    assert not LOCAL_PATH_RE.search(html)


def test_decision_timeline_no_current_mutation(client):
    before = client.get("/api/latest-index").json()
    response = client.get("/api/decision-timeline")
    assert response.status_code == 200
    after = client.get("/api/latest-index").json()
    assert json.dumps(before, sort_keys=True) == json.dumps(after, sort_keys=True)
    text = json.dumps(response.json(), ensure_ascii=False, sort_keys=True).replace("\\", "/").lower()
    for term in ["temp/", "web_runtime", ".sqlite", ".db", ".env", ".zip", ".log"]:
        assert term not in text


def test_decision_timeline_openapi_is_read_only(client):
    schema = client.get("/openapi.json").json()
    mutating = []
    for path, methods in schema.get("paths", {}).items():
        if path.startswith("/api"):
            bad = sorted(set(methods) & {"post", "put", "patch", "delete"})
            if bad:
                mutating.append((path, bad))
    assert mutating == []


def test_decision_timeline_current_only_and_no_hardcoded_timestamps():
    source = open("web/backend/app/services/decision_timeline.py", encoding="utf-8").read()
    assert "latest_index.files" not in source
    assert "[\"files\"]" not in source
    assert "['files']" not in source
    assert "generate_action_plan.py" not in source
    assert "generate_target_allocation.py" not in source
    assert not TIMESTAMP_RE.search(source)
