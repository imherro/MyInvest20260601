from __future__ import annotations

from web.backend.app.db import SessionLocal
from web.backend.app.services.research_first_gate import ResearchFirstGateService


def test_research_first_gate_service_passes(web_db):
    with SessionLocal() as session:
        result = ResearchFirstGateService(session).check()
    assert result["status"] == "ok"


def test_research_first_api_exposes_gate_state(client):
    response = client.get("/api/research-first/current")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["gate"]["status"] == "ok"
    for item in payload["data"]["items"]:
        assert item["allowed_conclusion"] in {"research_first", "block", "blocked", None}
