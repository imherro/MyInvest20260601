from __future__ import annotations

from web.backend.app.db import SessionLocal
from web.backend.app.services.allocation_consistency import AllocationConsistencyService


def test_allocation_consistency_passes(web_db):
    with SessionLocal() as session:
        result = AllocationConsistencyService(session).check()
    assert result["status"] == "ok"
