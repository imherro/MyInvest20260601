from __future__ import annotations


def test_action_plan_api_returns_actions(client):
    response = client.get("/api/action-plan/current")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["action_plan"]["actions"]
