from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session", autouse=True)
def web_db() -> Path:
    subprocess.run(
        [sys.executable, "scripts/ingest_current_state.py"],
        cwd=ROOT,
        check=True,
    )
    return ROOT / "temp" / "web_db" / "myinvest.sqlite"


@pytest.fixture()
def client(web_db: Path) -> TestClient:
    from web.backend.app.main import app

    return TestClient(app)
