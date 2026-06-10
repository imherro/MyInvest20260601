from __future__ import annotations

import json
from pathlib import Path

import pytest

from web.backend.app.db import SessionLocal
from web.backend.app.services.current_state import CurrentStateService
from web.backend.app.services.database import DatabaseService


ROOT = Path(__file__).resolve().parents[3]


def test_database_service_current_modules_match_latest_index_modules(web_db):
    latest = json.loads((ROOT / "research" / "latest_index.json").read_text(encoding="utf-8-sig"))

    with SessionLocal() as session:
        modules = {row["module"]: row for row in DatabaseService(session).current_modules()}

    assert modules["action_plan"]["path"] == latest["modules"]["action_plan"]["path"]
    assert modules["target_allocation"]["path"] == latest["modules"]["target_allocation"]["path"]
    assert "files" not in modules


def test_database_service_current_artifact_payload_uses_current_module_fallback(web_db):
    with SessionLocal() as session:
        database = DatabaseService(session)
        payload = database.current_artifact_payload("theme_registry", expected_key="themes")
        source = database.current_artifact("theme_registry")

    assert isinstance(payload.get("themes"), list)
    assert payload["themes"]
    assert source
    assert source["path"] == "research/themes/theme_registry.json"
    assert not Path(source["path"]).is_absolute()


def test_database_service_rejects_write_sql(web_db):
    with SessionLocal() as session:
        database = DatabaseService(session)
        with pytest.raises(ValueError, match="read-only"):
            database.fetch_all("DELETE FROM current_modules")


def test_current_state_service_exposes_database_payload_fallback(web_db):
    with SessionLocal() as session:
        payload = CurrentStateService(session).current_artifact_payload("etf_registry", expected_key="etfs")

    assert isinstance(payload.get("etfs"), list)
    assert any(row.get("code") == "511360.SH" for row in payload["etfs"])


def test_theme_status_module_payload_is_database_service_backed():
    source = (ROOT / "web" / "backend" / "app" / "services" / "theme_status.py").read_text(encoding="utf-8")

    assert "current_artifact_payload" in source
    assert ".read_text(" not in source
    assert "latest_index.files" not in source
