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

    for path, marker in [
        ("/history", "History"),
        ("/market/history", "Market History"),
        ("/positions/history?bucket=defense", "Position History"),
        ("/actions/history?action_type=Reduce", "Action History"),
        ("/history/quality", "History Quality"),
    ]:
        page = client.get(path)
        assert page.status_code == 200
        assert marker in page.text

    valuation = client.get("/securities/688333.SH/valuation")
    assert valuation.status_code == 200
    assert "/positions/history?code=688333.SH" in valuation.text
    assert "/actions/history?code=688333.SH" in valuation.text
