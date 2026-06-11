from __future__ import annotations

import re

from web.backend.app.services.decision_assistant import DecisionAssistantService
from web.backend.app.services.ratio_only import RatioOnlyService


LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:(?!//)[\\/]|\\\\|/Users/|/home/)")


def test_decision_assistant_service_payload_is_safe(client, web_db):
    from web.backend.app.db import SessionLocal

    with SessionLocal() as session:
        payload = DecisionAssistantService(session).daily()

    RatioOnlyService.assert_safe(payload)
    assert payload["module"] == "decision_assistant_daily"
    assert payload["current_only"] is True
    assert payload["safety"]["read_only"] is True
    assert payload["safety"]["trading_feature"] is False
    assert payload["today"]["market_score"] is not None
    assert len(payload["risk_heatmap"]["items"]) >= 6
    assert len(payload["next_steps"]) >= 4
    assert "research_priorities" in payload
    assert "scenario_simulation" in payload
    assert "allocation_drift" in payload
    assert "review_loop" in payload
    assert "history_visuals" in payload
    assert "explanations" in payload


def test_decision_assistant_api(client):
    response = client.get("/api/assistant/daily")
    assert response.status_code == 200
    payload = response.json()
    RatioOnlyService.assert_safe(payload)
    assert payload["ok"] is True
    data = payload["data"]
    assert data["today"]["system_status"]
    assert data["risk_heatmap"]["summary"]["item_count"] == len(data["risk_heatmap"]["items"])
    assert data["scenario_simulation"]["summary"]["scenario_count"] == len(data["scenario_simulation"]["items"])
    assert all("href" in item for item in data["next_steps"])


def test_decision_assistant_page(client):
    response = client.get("/assistant")
    assert response.status_code == 200
    html = response.text
    assert "每日指挥台" in html
    assert "/api/assistant/daily" in html
    for marker in [
        'data-assistant-section="today"',
        'data-assistant-section="next-steps"',
        'data-assistant-section="risk-heatmap"',
        'data-assistant-section="research-priorities"',
        'data-assistant-section="scenario-simulation"',
        'data-assistant-section="allocation-drift"',
        'data-assistant-section="review-loop"',
        'data-assistant-section="history-visuals"',
        'data-assistant-section="explanations"',
    ]:
        assert marker in html
    assert not LOCAL_PATH_RE.search(html)
