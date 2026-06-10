from __future__ import annotations


def test_action_plan_api_returns_actions(client):
    response = client.get("/api/action-plan/current")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["action_plan"]["actions"]


def test_action_plan_api_source_is_current_module(client):
    response = client.get("/api/action-plan/current")
    assert response.status_code == 200
    source = response.json()["source"]
    modules = client.get("/api/modules/current").json()["data"]["modules"]
    action_module = next(item for item in modules if item["module"] == "action_plan")
    assert source["path"] == action_module["path"]
