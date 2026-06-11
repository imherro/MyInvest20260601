from __future__ import annotations

import re
import string
from pathlib import Path
from typing import Any

import web.backend.app.repositories.subject_status_repo as subject_status_repo_module
from web.backend.app.db import SessionLocal
from web.backend.app.services.current_state import CurrentStateService
from web.backend.app.services.subject_status import SubjectStatusService


FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(amount|market_value|profit_amount|total_amount|total_asset|share_count|shares|quantity|qty|"
    r"available_qty|available_quantity|trade_amount|account|full_account|order|fill|deal)($|_)",
    re.IGNORECASE,
)
FORBIDDEN_PAGE_TERMS = [
    "total_asset",
    "market_value",
    "shares",
    "quantity",
    "account",
    "order_id",
    "fill_record",
    "deal_record",
    "总资产",
    "金额",
    "市值",
    "股数",
    "账号",
    "订单",
    "成交",
]
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
ROOT = Path(__file__).resolve().parents[3]


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


def test_subject_status_subject_count_matches_db_baseline(client):
    response = client.get("/api/subjects/status")
    assert response.status_code == 200
    data = response.json()["data"]

    with SessionLocal() as session:
        db_subject_count = CurrentStateService(session).table_counts()["subjects"]

    assert data["summary"]["subject_count"] == db_subject_count
    assert len(data["subjects"]) == db_subject_count


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


def test_subject_status_source_paths_are_repo_relative(client):
    response = client.get("/api/subjects/status")
    assert response.status_code == 200
    subjects = response.json()["data"]["subjects"]

    for subject in subjects:
        for source_path in (subject.get("source_paths") or {}).values():
            path = Path(str(source_path))
            assert not path.is_absolute()
            assert ".." not in path.parts
            assert not has_local_path(str(source_path))


def test_subject_status_missing_coverage_blocks_actions_but_not_action_plan_queue(client):
    response = client.get("/api/subjects/status")
    assert response.status_code == 200
    data = response.json()["data"]
    subjects = data["subjects"]

    missing_coverage = [
        item
        for item in subjects
        if item["missing_profile"] or item["missing_valuation"] or item["missing_liquidity"] or item["missing_theme_binding"]
    ]
    assert missing_coverage
    assert data["summary"]["research_first_count"] + data["summary"]["blocked_count"] == len(missing_coverage)
    for item in missing_coverage:
        assert item["research_first_status"] in {"research_first", "blocked"}
        assert item["gate_conclusion"] in {"research_first", "blocked"}

    research_first_response = client.get("/api/research-first/current")
    assert research_first_response.status_code == 200
    assert research_first_response.json()["data"]["items"] == []


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
    for term in FORBIDDEN_PAGE_TERMS:
        assert term not in html


def test_subject_status_detail_and_page_are_safe(client):
    for path in ["/api/subjects/status/511360.SH", "/subjects"]:
        response = client.get(path)
        assert response.status_code == 200
        if response.headers.get("content-type", "").startswith("application/json"):
            walk(response.json())
        else:
            assert not has_local_path(response.text)
            for term in FORBIDDEN_PAGE_TERMS:
                assert term not in response.text


def test_subject_status_service_and_repository_do_not_resolve_files_directly():
    service_source = (ROOT / "web" / "backend" / "app" / "services" / "subject_status.py").read_text(encoding="utf-8")
    repo_source = (ROOT / "web" / "backend" / "app" / "repositories" / "subject_status_repo.py").read_text(encoding="utf-8")

    for source in [service_source, repo_source]:
        assert ".read_text(" not in source
        assert "latest_index.files" not in source
        assert '["files"]' not in source
        assert "['files']" not in source
        assert "Path(" not in source

    assert "DatabaseService" in repo_source
    assert ".fetch_all(" in repo_source
    assert ".execute(" not in repo_source


def test_subject_status_repository_delegates_sql_to_database_service(monkeypatch):
    calls: list[str] = []

    class FakeDatabaseService:
        def __init__(self, session):
            calls.append(f"init:{session}")

        def fetch_all(self, sql, params=None):
            calls.append(sql)
            return [
                {
                    "code": "511360.SH",
                    "name": "短融ETF",
                    "subject_type": "cash_equivalent",
                    "bucket": "cash_short",
                    "subject_status": "eligible_for_review",
                    "profile_status_raw": "pass",
                    "profile_generated_at": "2026-06-09",
                    "profile_basis_date": "20260608",
                    "profile_source_path": "research/etfs/511360_profile.json",
                    "valuation_status_raw": "pass",
                    "valuation_generated_at": "2026-06-09",
                    "valuation_basis_date": "20260608",
                    "valuation_source_path": "research/etfs/511360_valuation.json",
                    "liquidity_status_raw": "pass",
                    "liquidity_valuation_status_raw": "pass",
                    "duration_boundary_confirmed": True,
                    "interest_rate_risk_disclosed": True,
                    "credit_risk_disclosed": True,
                    "liquidity_risk_disclosed": True,
                    "liquidity_generated_at": "2026-06-09",
                    "liquidity_profile_source_path": "research/etfs/511360_profile.json",
                    "liquidity_valuation_source_path": "research/etfs/511360_valuation.json",
                    "missing_profile": False,
                    "missing_valuation": False,
                    "missing_liquidity": False,
                    "missing_theme_binding": False,
                    "allowed_conclusion": "eligible_for_review",
                    "blocking_reason": None,
                }
            ]

    monkeypatch.setattr(subject_status_repo_module, "DatabaseService", FakeDatabaseService)

    repo = subject_status_repo_module.SubjectStatusRepository("sentinel")
    rows = repo.list_subject_status_rows()

    assert rows[0]["code"] == "511360.SH"
    assert calls[0] == "init:sentinel"
    assert "WITH latest_positions" in calls[1]
    assert "latest_index.files" not in calls[1]
    assert "PRAGMA" not in calls[1].upper()
    assert "INSERT" not in calls[1].upper()
    assert "UPDATE" not in calls[1].upper()
    assert "DELETE" not in calls[1].upper()


def test_subject_status_service_output_with_repository_rows_is_stable(monkeypatch):
    class FakeRepository:
        def __init__(self, session):
            pass

        def list_subject_status_rows(self):
            return [
                {
                    "code": "511360.SH",
                    "name": "短融ETF",
                    "subject_type": "cash_equivalent",
                    "bucket": "bond_cash",
                    "subject_status": "eligible_for_review",
                    "profile_status_raw": "pass",
                    "profile_generated_at": "2026-06-09",
                    "profile_basis_date": "20260608",
                    "profile_source_path": "research/etfs/511360_profile.json",
                    "valuation_status_raw": "pass",
                    "valuation_generated_at": "2026-06-09",
                    "valuation_basis_date": "20260608",
                    "valuation_source_path": "research/etfs/511360_valuation.json",
                    "liquidity_status_raw": "pass",
                    "liquidity_generated_at": "2026-06-09",
                    "liquidity_profile_source_path": "research/etfs/511360_profile.json",
                    "liquidity_valuation_source_path": "research/etfs/511360_valuation.json",
                    "missing_profile": False,
                    "missing_valuation": False,
                    "missing_liquidity": False,
                    "missing_theme_binding": False,
                    "allowed_conclusion": "buy",
                    "blocking_reason": None,
                }
            ]

        def get_subject_status_row(self, code):
            return self.list_subject_status_rows()[0] if code == "511360.SH" else None

    import web.backend.app.services.subject_status as subject_status_module

    monkeypatch.setattr(subject_status_module, "SubjectStatusRepository", FakeRepository)

    service = SubjectStatusService("sentinel")
    payload = service.list_statuses()
    subject = payload["subjects"][0]

    assert payload["summary"]["subject_count"] == 1
    assert subject["bucket"] == "cash_short"
    assert subject["profile_status"] == "pass"
    assert subject["valuation_status"] == "pass"
    assert subject["liquidity_status"] == "pass"
    assert subject["research_first_status"] == "pass"
    assert subject["gate_conclusion"] == "blocked"
    walk(payload)
