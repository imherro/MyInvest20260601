from __future__ import annotations

import json
import re
from typing import Any

import pytest

from web.backend.app.db import SessionLocal
from web.backend.app.repositories.user_preferences_repo import UserPreferencesRepository


LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:(?!//)[\\/]|\\\\|/Users/|/home/)")
SECRET_RE = re.compile(r"(?:\.env|token|secret|password|api key)", re.IGNORECASE)
FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(amount|market_value|profit_amount|total_amount|total_asset|share_count|shares|quantity|qty|"
    r"available_qty|available_quantity|trade_amount|account|full_account|order|fill|deal|"
    r"cost_price|raw_cost_price|current_price|qmt_timetag)($|_)",
    re.IGNORECASE,
)


def walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, item in value.items():
            key_path = f"{path}.{key}"
            yield key_path, key
            yield from walk(item, key_path)
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            yield from walk(item, f"{path}[{idx}]")
    else:
        yield path, value


def assert_preferences_payload_safe(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)
    assert not LOCAL_PATH_RE.search(serialized)
    assert not SECRET_RE.search(serialized)
    for path, item in walk(payload):
        if isinstance(item, str):
            assert not LOCAL_PATH_RE.search(item), path
            assert not SECRET_RE.search(item), path
        assert not FORBIDDEN_KEY_RE.search(str(item)), path


def test_default_user_preferences_api_returns_safe_payload(client):
    response = client.get("/api/user/preferences")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    preferences = payload["data"]["preferences"]
    assert preferences["module"] == "user_preferences"
    assert preferences["user_id"] == "default"
    assert preferences["display"]["number_format"] == "ratio_pp"
    assert preferences["dashboard"]["refresh_seconds"] == 60
    assert preferences["tables"]["page_size"] == 12
    assert preferences["safety"]["read_only"] is True
    assert preferences["safety"]["ratio_only"] is True
    assert preferences["safety"]["current_only"] is True
    assert preferences["safety"]["uses_database_service"] is True
    assert preferences["safety"]["trading_disabled"] is True
    assert preferences["safety"]["qmt_write_disabled"] is True
    assert preferences["sources"]["current_module_count"] > 0
    assert_preferences_payload_safe(payload)


def test_named_user_preferences_api_returns_default_or_safe_404(client):
    response = client.get("/api/user/preferences/default")
    assert response.status_code == 200
    assert response.json()["data"]["preferences"]["user_id"] == "default"

    response = client.get("/api/user/preferences/unknown_user")
    assert response.status_code == 404
    payload = response.json()
    assert payload["detail"] == "user preferences not found"
    assert_preferences_payload_safe(payload)


def test_preferences_page_renders_refresh_and_table_hooks(client):
    response = client.get("/preferences")
    assert response.status_code == 200
    html = response.text
    assert "Workbench Preferences" in html
    assert "/api/user/preferences" in html
    assert "data-preferences-section=\"display\"" in html
    assert "data-preferences-section=\"dashboard\"" in html
    assert "data-preferences-section=\"safety\"" in html
    assert "data-status-card=\"pref-readonly\"" in html
    assert "data-bind=\"pref_refresh\"" in html
    assert "preferenceRows" in html
    assert "preferenceSourceRows" in html
    assert not LOCAL_PATH_RE.search(html)


def test_user_preferences_repository_rejects_write_sql():
    with SessionLocal() as session:
        repo = UserPreferencesRepository(session)
        with pytest.raises(ValueError):
            repo.one("UPDATE system_check_results SET status = status")
