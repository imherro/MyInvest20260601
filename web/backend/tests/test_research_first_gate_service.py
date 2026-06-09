from __future__ import annotations

from web.backend.app.db import SessionLocal
from web.backend.app.services.research_first_gate import ResearchFirstGateService


def test_research_first_gate_service_passes(web_db):
    with SessionLocal() as session:
        result = ResearchFirstGateService(session).check()
    assert result["status"] == "ok"
