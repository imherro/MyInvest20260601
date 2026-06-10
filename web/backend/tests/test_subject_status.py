from __future__ import annotations

import re
import string
from typing import Any


FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(amount|market_value|profit_amount|total_amount|total_asset|share_count|shares|quantity|qty|"
    r"available_qty|available_quantity|trade_amount|account|full_account|order|fill|deal)($|_)",
    re.IGNORECASE,
)
ACTION_CONCLUSIONS = {"buy", "add", "reduce", "sell"}
ALLOWED_GATE_CONCLUSIONS = {
    "eligible_for_review",
    "research_first",
    "watch",
    "hold",
    "no_action",
    "unknown",
    "blocked",
}
BACKSLASH = chr(92)


def has_local_path(value: str) -> bool:
    user_home = "/" + "Users" + "/"
    unix_home = "/" + "home" + "/"
    if user_home in value or unix_home in value:
        return True
    if value.startswith(BACKSLASH + BACKSLASH):
        return True
    return any(f"{letter}:{BACKSLASH}" in value or f"{letter}:/" in value for letter in string.ascii_letters)


def walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, item in value.items():
            assert not FORBIDDEN_KEY_RE.search(str(key)), f"forbidden key {path}.{key}"
            walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            walk(item, f"{path}[{idx}]")
    elif isinstance(value, str):
        assert not has_local_path(value), f"local path at {path}"


def test_subject_status_endpoint_contract(client):
    response = client.get("/api/subjects/status")
    assert response.status_code == 200
    payload = response.json()
    walk(payload)

    data = payload["data"]
    assert data["current_only"] is True
    assert "subjects" in data
    assert "summary" in data
    assert data["summary"]["subject_count"] == len(data["subjects"])
    assert data["subjects"]

    required = {
        "code",
        "name",
        "subject_type",
        "bucket",
        "profile_status",
        "valuation_status",
        "liquidity_status",
        "research_first_status",
        "gate_conclusion",
        "blocking_reason",
        "source_paths",
        "generated_at",
        "basis_trade_date",
    }
    for item in data["subjects"]:
        assert required <= set(item)
        assert item["gate_conclusion"] in ALLOWED_GATE_CONCLUSIONS
        assert item["gate_conclusion"] not in ACTION_CONCLUSIONS


def test_subject_status_511360_cash_equivalent_gate(client):
    response = client.get("/api/subjects/status/511360.SH")
    assert response.status_code == 200
    payload = response.json()
    walk(payload)
    subject = payload["data"]["subject"]

    assert subject["code"] == "511360.SH"
    assert subject["subject_type"] == "cash_equivalent"
    assert subject["bucket"] == "cash_short"
    assert subject["profile_status"] == "pass"
    assert subject["valuation_status"] == "pass"
    assert subject["liquidity_status"] == "pass"
    assert subject["research_first_status"] == "pass"
    assert subject["gate_conclusion"] == "eligible_for_review"
    assert subject["source_paths"]


def test_subject_status_research_first_items_are_neutral(client):
    response = client.get("/api/subjects/status")
    assert response.status_code == 200
    subjects = response.json()["data"]["subjects"]

    blocked = [
        item
        for item in subjects
        if item["missing_profile"] or item["missing_valuation"] or item["missing_liquidity"] or item["missing_theme_binding"]
    ]
    assert blocked
    for item in blocked:
        assert item["research_first_status"] in {"research_first", "blocked"}
        assert item["gate_conclusion"] in {"research_first", "blocked"}


def test_subject_status_missing_code_is_safe_404(client):
    response = client.get("/api/subjects/status/NO_SUCH_CODE")
    assert response.status_code == 404
    payload = response.json()
    walk(payload)
    assert payload["detail"] == "subject status not found"


def test_subject_status_openapi_is_read_only(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    for route, methods in schema["paths"].items():
        if route.startswith("/api/"):
            assert not (set(methods) & {"post", "put", "patch", "delete"}), route


def test_subject_status_page(client):
    response = client.get("/subjects")
    assert response.status_code == 200
    html = response.text
    assert "Subject Research Status" in html
    assert "data-table-search=\"subjectsTable\"" in html
    assert "data-sort=\"text\"" in html
    assert "subjectsRows" in html
    assert not has_local_path(html)
