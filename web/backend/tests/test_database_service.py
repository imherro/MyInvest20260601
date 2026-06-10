from __future__ import annotations

import json
from pathlib import Path

import pytest

from web.backend.app.db import SessionLocal
import web.backend.app.services.current_state as current_state_module
from web.backend.app.services.current_state import CurrentStateService
from web.backend.app.services.database import DatabaseService
from web.backend.app.services.ratio_only import RatioOnlyService


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
        for sql in [
            "DELETE FROM current_modules",
            "UPDATE current_modules SET updated_at = 'x'",
            "INSERT INTO current_modules(module) VALUES ('x')",
            "CREATE TABLE unsafe(id integer)",
            "DROP TABLE current_modules",
            "PRAGMA table_info(current_modules)",
        ]:
            with pytest.raises(ValueError, match="read-only"):
                database.fetch_all(sql)


def test_current_state_service_exposes_database_payload_fallback(web_db):
    with SessionLocal() as session:
        payload = CurrentStateService(session).current_artifact_payload("etf_registry", expected_key="etfs")

    assert isinstance(payload.get("etfs"), list)
    assert any(row.get("code") == "511360.SH" for row in payload["etfs"])
    RatioOnlyService.assert_safe(
        {
            "etf_count": len(payload["etfs"]),
            "has_cash_equivalent_profile": any(row.get("code") == "511360.SH" for row in payload["etfs"]),
        }
    )


def test_current_state_service_delegates_current_reads_to_database_service(monkeypatch):
    calls: list[tuple[str, object | None]] = []

    class FakeDatabaseService:
        def __init__(self, session):
            calls.append(("init", session))

        def current_modules(self):
            calls.append(("current_modules", None))
            return [{"module": "action_plan", "path": "research/actions/current.json"}]

        def source_for_module(self, module):
            calls.append(("source_for_module", module))
            return {"module": module, "path": "research/source.json"}

        def latest_index(self):
            calls.append(("latest_index", None))
            return {"generated_at": "2026-06-10", "modules": []}

        def current_artifact(self, module):
            calls.append(("current_artifact", module))
            return {"module": module, "path": "research/source.json", "raw_json": "{}"}

        def current_artifact_payload(self, module, expected_key=None):
            calls.append(("current_artifact_payload", (module, expected_key)))
            return {"items": []}

        def count_table(self, table):
            calls.append(("count_table", table))
            return 1

    sentinel_session = object()
    monkeypatch.setattr(current_state_module, "DatabaseService", FakeDatabaseService)

    service = current_state_module.CurrentStateService(sentinel_session)

    assert service.current_modules() == [{"module": "action_plan", "path": "research/actions/current.json"}]
    assert service.source_for_module("target_allocation") == {
        "module": "target_allocation",
        "path": "research/source.json",
    }
    assert service.latest_index() == {"generated_at": "2026-06-10", "modules": []}
    assert service.current_artifact("theme_registry") == {
        "module": "theme_registry",
        "path": "research/source.json",
        "raw_json": "{}",
    }
    assert service.current_artifact_payload("theme_registry", expected_key="themes") == {"items": []}
    counts = service.table_counts()

    assert ("init", sentinel_session) in calls
    assert ("current_modules", None) in calls
    assert ("source_for_module", "target_allocation") in calls
    assert ("latest_index", None) in calls
    assert ("current_artifact", "theme_registry") in calls
    assert ("current_artifact_payload", ("theme_registry", "themes")) in calls
    assert counts["current_modules"] == 1
    assert ("count_table", "current_modules") in calls


def test_database_service_fallback_rejects_absolute_and_parent_escape_paths():
    class AbsolutePathDatabaseService(DatabaseService):
        def __init__(self):
            pass

        def current_artifact(self, module):
            return {"module": module, "path": "C:/Users/example/secret.json", "raw_json": "{}"}

    class ParentEscapeDatabaseService(DatabaseService):
        def __init__(self):
            pass

        def current_artifact(self, module):
            return {"module": module, "path": "../research/latest_index.json", "raw_json": "{}"}

    assert AbsolutePathDatabaseService().current_artifact_payload("unsafe", expected_key="items") == {}
    assert ParentEscapeDatabaseService().current_artifact_payload("unsafe", expected_key="items") == {}


def test_theme_status_module_payload_is_database_service_backed():
    source = (ROOT / "web" / "backend" / "app" / "services" / "theme_status.py").read_text(encoding="utf-8")
    database_source = (ROOT / "web" / "backend" / "app" / "services" / "database.py").read_text(encoding="utf-8")

    assert "current_artifact_payload" in source
    assert ".read_text(" not in source
    assert "latest_index.files" not in source
    assert "latest_index.files" not in database_source
