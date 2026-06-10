from __future__ import annotations

from web.backend.app.db import SessionLocal
from web.backend.app.services.allocation_consistency import AllocationConsistencyService


def test_allocation_consistency_passes(web_db):
    with SessionLocal() as session:
        result = AllocationConsistencyService(session).check()
    assert result["status"] == "ok"


def test_target_allocation_matches_intraday_rules_api(client):
    target = client.get("/api/target-allocation/current").json()["data"]["target_allocation"]
    intraday = client.get("/api/intraday-rules/current").json()["data"]["intraday_rules"]
    target_buckets = {item["bucket"]: item for item in target["buckets"]}
    intraday_buckets = {item["bucket"]: item for item in intraday["buckets"]}
    assert set(target_buckets) == set(intraday_buckets)
    for bucket, target_row in target_buckets.items():
        intraday_row = intraday_buckets[bucket]
        for field in ["actual_pct", "target_pct", "gap_pct"]:
            assert abs(float(target_row[field]) - float(intraday_row[field])) <= 0.05
