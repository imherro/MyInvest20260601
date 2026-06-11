from __future__ import annotations

import subprocess
import sys


def test_valuation_history_api_and_page(client):
    subprocess.run(
        [sys.executable, "scripts/db_migrate.py", "--db", "temp/history_db/myinvest_history.sqlite3", "--reset"],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "scripts/db_ingest_research_artifacts.py",
            "--db",
            "temp/history_db/myinvest_history.sqlite3",
            "--path",
            "research/valuations",
        ],
        check=True,
    )

    response = client.get("/api/securities/688333.SH/valuation-history")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    rows = payload["data"]["rows"]
    assert rows
    assert rows[-1]["reasonable_min"] is not None

    page = client.get("/securities/688333.SH/valuation")
    assert page.status_code == 200
    assert "Valuation History" in page.text
    assert "688333.SH" in page.text
    assert "不是组合级买卖建议" in page.text
