from __future__ import annotations

import json


def test_latest_index_api_uses_modules_action_plan(client):
    response = client.get("/api/latest-index")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    modules = {item["module"]: item for item in payload["data"]["modules"]}

    with open("research/latest_index.json", encoding="utf-8-sig") as handle:
        latest = json.load(handle)
    assert modules["action_plan"]["path"] == latest["modules"]["action_plan"]["path"]
