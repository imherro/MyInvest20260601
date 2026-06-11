from __future__ import annotations

import subprocess
import sys
import warnings
from collections.abc import Generator
from pathlib import Path

import pytest
from starlette.exceptions import StarletteDeprecationWarning


warnings.filterwarnings(
    "ignore",
    message=r"Using `httpx` with `starlette\.testclient` is deprecated; install `httpx2` instead\.",
    category=StarletteDeprecationWarning,
)

from starlette.testclient import TestClient  # noqa: E402


ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session", autouse=True)
def web_db() -> Path:
    subprocess.run(
        [sys.executable, "scripts/ingest_current_state.py"],
        cwd=ROOT,
        check=True,
    )
    return ROOT / "temp" / "web_db" / "myinvest.sqlite"


@pytest.fixture(autouse=True)
def close_database_connections() -> Generator[None, None, None]:
    yield
    from web.backend.app.db import engine

    engine.dispose()


@pytest.fixture()
def client(web_db: Path) -> Generator[TestClient, None, None]:
    from web.backend.app.main import app

    with TestClient(app) as test_client:
        yield test_client
