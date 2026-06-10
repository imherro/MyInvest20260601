from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote


FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(total_asset|amount|market_value|shares|quantity|available_quantity|"
    r"trade_amount|profit_amount|account|full_account|order|fill|deal|"
    r"total_amount|share_count|available_qty|qty)($|_)",
    re.IGNORECASE,
)
LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:(?!//)[\\/]|\\\\|/Users/|/home/)")
ACTION_STATUSES = {"buy", "add", "reduce", "sell"}


def walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, item in value.items():
            assert not FORBIDDEN_KEY_RE.search(str(key)), f"forbidden key {path}.{key}"
            walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            walk(item, f"{path}[{idx}]")
    elif isinstance(value, str):
        assert not LOCAL_PATH_RE.search(value), f"local path at {path}"


def test_theme_status_api_structure_and_safety(client):
    response = client.get("/api/themes/status")
    assert response.status_code == 200
    payload = response.json()
    walk(payload)
    data = payload["data"]
    assert data["module"] == "theme_research_status"
    assert data["current_only"] is True
    assert data["safety"] == {"ratio_only": True, "current_only": True}
    assert isinstance(data["themes"], list)
    assert set(data["summary"]) >= {
        "theme_count",
        "confirmed_count",
        "watch_count",
        "research_first_count",
        "stale_count",
        "conflict_count",
    }
    assert data["summary"]["theme_count"] == len(data["themes"])
    if data["themes"]:
        theme = data["themes"][0]
        assert set(theme) >= {
            "theme_name",
            "strategic_rating",
            "tactical_rating",
            "stage",
            "status",
            "associated_etfs",
            "associated_stocks",
            "leaders",
            "conflicts",
            "data_quality_status",
        }
        assert theme["status"] not in ACTION_STATUSES
        for row in [*theme["associated_etfs"], *theme["associated_stocks"]]:
            assert row.get("gate_conclusion") not in ACTION_STATUSES


def test_theme_status_detail_and_missing(client):
    data = client.get("/api/themes/status").json()["data"]
    if data["themes"]:
        name = data["themes"][0]["theme_name"]
        response = client.get(f"/api/themes/status/{quote(name, safe='')}")
        assert response.status_code == 200
        walk(response.json())
        assert response.json()["data"]["theme"]["theme_name"] == name
    missing = client.get("/api/themes/status/NO_SUCH_THEME")
    assert missing.status_code == 404
    walk(missing.json())


def test_themes_page_hooks_and_safety(client):
    response = client.get("/themes")
    assert response.status_code == 200
    html = response.text
    assert "Theme Research Center" in html
    assert "/api/themes/status" in html
    assert "data-table-search=\"themesTable\"" in html
    assert "data-table-filter=\"themesTable\"" in html
    assert "data-filter-key=\"status\"" in html
    assert "data-filter-key=\"tactical_rating\"" in html
    assert "data-filter-key=\"stage\"" in html
    assert "themesRows" in html
    assert not LOCAL_PATH_RE.search(html)


def test_theme_status_does_not_use_latest_index_files():
    source = open("web/backend/app/services/theme_status.py", encoding="utf-8").read()
    assert "current_artifact_payload" in source
    assert ".read_text(" not in source
    assert ".execute(" not in source
    assert "latest_index.files" not in source
    assert "[\"files\"]" not in source
    assert "['files']" not in source
