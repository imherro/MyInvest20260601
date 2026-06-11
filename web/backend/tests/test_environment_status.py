from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts import check_hidden_unicode, run_web


LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:(?!//)[\\/]|\\\\|/Users/|/home/)")
SECRET_RE = re.compile(r"(?:\.env|token|secret|password|api key)", re.IGNORECASE)
FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(amount|market_value|profit_amount|total_amount|total_asset|share_count|shares|quantity|qty|"
    r"available_qty|available_quantity|trade_amount|account|full_account|order|fill|deal)($|_)",
    re.IGNORECASE,
)
ALLOWED_ENVIRONMENT_KEYS = {"$.safety.no_order_generation"}


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


def assert_environment_payload_safe(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    assert not LOCAL_PATH_RE.search(text)
    assert not SECRET_RE.search(text)
    for path, item in walk(payload):
        if isinstance(item, str):
            assert not LOCAL_PATH_RE.search(item), path
            assert not SECRET_RE.search(item), path
        elif isinstance(item, str):
            assert not SECRET_RE.search(item), path
        if path not in ALLOWED_ENVIRONMENT_KEYS:
            assert not FORBIDDEN_KEY_RE.search(str(item)), path


def test_environment_status_api_returns_safe_readonly_status(client):
    response = client.get("/api/environment/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["module"] == "environment_status"
    assert payload["readonly"] is True
    assert payload["read_only"] is True
    assert payload["current_only"] is True
    assert payload["ratio_only"] is True
    assert payload["safety"]["no_trading"] is True
    assert payload["safety"]["no_qmt_write"] is True
    assert payload["safety"]["no_order_generation"] is True
    assert payload["safety"]["research_current_mutation"] is False
    assert payload["paths"]["web_db_path"] == "temp/web_db/myinvest.sqlite"
    assert payload["web"]["default_host"] == "0.0.0.0"
    assert payload["web"]["default_port"] == 8000
    assert payload["web"]["phase10_recommended_port"] == 8010
    assert_environment_payload_safe(payload)


def test_environment_pages_render_safety_boundary(client):
    for path in ["/settings", "/environment"]:
        response = client.get(path)
        assert response.status_code == 200, path
        html = response.text
        assert "Workbench Settings" in html
        assert "read-only research workbench" in html
        assert "not a trading system" in html
        assert "does not connect to QMT write interfaces" in html
        assert "does not generate orders" in html
        assert "does not display money, share counts, or account identifiers" in html
        assert "trusted networks only" in html
        assert "data-environment-section=\"git\"" in html
        assert "environmentCheckRows" in html
        assert "/api/environment/status" in html
        assert not LOCAL_PATH_RE.search(html)


def test_environment_openapi_stays_readonly(client):
    schema = client.get("/openapi.json").json()
    mutating = []
    for path, methods in schema.get("paths", {}).items():
        if path.startswith("/api/"):
            mutating.extend(method.upper() for method in methods if method.upper() in {"POST", "PUT", "PATCH", "DELETE"})
    assert mutating == []


def test_run_web_default_host_remains_trusted_lan_contract():
    assert run_web.DEFAULT_HOST == "0.0.0.0"
    assert run_web.DEFAULT_PORT == 8000
    parser = run_web.build_parser()
    defaults = parser.parse_args([])
    assert defaults.host == "0.0.0.0"
    assert defaults.port == 8000


def test_regular_chinese_does_not_trigger_hidden_unicode_check(tmp_path: Path):
    path = tmp_path / "regular_chinese.txt"
    path.write_text("普通中文不触发 hidden Unicode check。\n", encoding="utf-8")
    assert check_hidden_unicode.scan_file(path) == []
    proc = subprocess.run(
        [sys.executable, "scripts/check_hidden_unicode.py", str(path)],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert proc.returncode == 0
    assert "Hidden Unicode check: OK" in proc.stdout
