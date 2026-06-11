from __future__ import annotations

import subprocess
import sys


def prepare_history_db() -> None:
    subprocess.run(
        [sys.executable, "scripts/db_migrate.py", "--db", "temp/history_db/myinvest_history.sqlite3", "--reset"],
        check=True,
    )
    subprocess.run(
        [sys.executable, "scripts/db_ingest_research_artifacts.py", "--db", "temp/history_db/myinvest_history.sqlite3", "--all"],
        check=True,
    )


def test_history_workbench_apis_and_pages(client):
    prepare_history_db()

    market = client.get("/api/market/history?limit=5")
    assert market.status_code == 200
    assert market.json()["ok"] is True
    assert market.json()["data"]["rows"]

    positions = client.get("/api/positions/history?bucket=defense&limit=5")
    assert positions.status_code == 200
    assert positions.json()["ok"] is True
    assert positions.json()["data"]["rows"]

    actions = client.get("/api/actions/history?action_type=Reduce&limit=5")
    assert actions.status_code == 200
    assert actions.json()["ok"] is True
    assert actions.json()["data"]["rows"]

    quality = client.get("/api/history/quality")
    assert quality.status_code == 200
    assert quality.json()["data"]["summary"]["fail_count"] == 0

    coverage = client.get("/api/history/coverage")
    assert coverage.status_code == 200
    assert coverage.json()["data"]["summary"]["artifact_count"] > 0

    security = client.get("/api/securities/688333.SH/history")
    assert security.status_code == 200
    assert security.json()["data"]["summary"]["valuation_count"] > 0
    assert "ratio-only" in security.json()["data"]["note"]

    for path, marker in [
        ("/history", "History"),
        ("/securities/688333.SH/history", "Security History"),
        ("/market/history", "Market History"),
        ("/positions/history?bucket=defense", "Position History"),
        ("/actions/history?action_type=Reduce", "Action History"),
        ("/history/quality", "History Quality"),
        ("/history/coverage", "History Coverage"),
    ]:
        page = client.get(path)
        assert page.status_code == 200
        assert marker in page.text

    valuation = client.get("/securities/688333.SH/valuation")
    assert valuation.status_code == 200
    assert "/securities/688333.SH/history" in valuation.text
    assert "/positions/history?code=688333.SH" in valuation.text
    assert "/actions/history?code=688333.SH" in valuation.text
    security_page = client.get("/securities/688333.SH/history")
    assert "ratio-only" in security_page.text
