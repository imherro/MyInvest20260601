from __future__ import annotations

import io
import json
import sqlite3
import subprocess
import sys
import zipfile
from contextlib import closing
from pathlib import Path
from typing import Any

from web.backend.app.db import SessionLocal
from web.backend.app.services.ratio_only import RatioOnlyService
from web.backend.app.services.target_allocation_export import ZIP_FILES, TargetAllocationControlledExportService


ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "temp" / "web_db" / "myinvest.sqlite"
EXPORT_DIR = ROOT / "temp" / "web_exports"


def assert_ratio_only(value: Any) -> None:
    RatioOnlyService.assert_safe(value)


def conn(web_db: Path) -> sqlite3.Connection:
    assert web_db == DB_PATH
    connection = sqlite3.connect(web_db)
    connection.row_factory = sqlite3.Row
    return connection


def current_state_snapshot(web_db: Path) -> dict[str, Any]:
    with closing(conn(web_db)) as db:
        modules = [dict(row) for row in db.execute("SELECT module, artifact_id, updated_at FROM current_modules ORDER BY module")]
        current_artifacts = [
            dict(row)
            for row in db.execute("SELECT module, path, is_current FROM artifacts WHERE is_current = 1 ORDER BY module, path")
        ]
        artifact_count = db.execute("SELECT COUNT(*) AS count FROM artifacts").fetchone()["count"]
    return {
        "latest_index": (ROOT / "research" / "latest_index.json").read_bytes(),
        "current_modules": modules,
        "current_artifacts": current_artifacts,
        "artifact_count": artifact_count,
        "allocation_files": sorted(path.name for path in (ROOT / "research" / "allocation").glob("target_allocation_*.json")),
        "action_files": sorted(path.name for path in (ROOT / "research" / "actions").glob("action_plan_*.json")),
    }


def read_zip_payloads(content: bytes) -> dict[str, Any]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = set(archive.namelist())
        assert names == ZIP_FILES
        return {name: json.loads(archive.read(name).decode("utf-8")) for name in names}


def run_cli(*args: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "scripts/export_target_allocation_shadow.py", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )
    return json.loads(proc.stdout)


def test_controlled_export_payload_builds(web_db):
    with SessionLocal() as session:
        payload = TargetAllocationControlledExportService(session).build_export_payload()
    assert payload["export_mode"] == "controlled_shadow"
    assert payload["status"] == "matched"
    assert payload["compare"]["matched"] is True
    assert payload["compare"]["diffs"] == []
    assert payload["compare"]["unsupported_fields"] == []
    assert {"shadow", "compare", "provenance", "safety", "system_checks"} <= set(payload)
    assert payload["safety"]["writes_research_files"] is False
    assert payload["safety"]["updates_latest_index"] is False
    assert payload["safety"]["updates_current_modules"] is False
    assert payload["safety"]["generates_action_plan"] is False
    assert_ratio_only(payload)


def test_controlled_export_json_bytes(web_db):
    with SessionLocal() as session:
        service = TargetAllocationControlledExportService(session)
        data = json.loads(service.build_json_bytes().decode("utf-8"))
    assert data["compare"]["matched"] is True
    assert data["compare"]["diffs"] == []
    assert data["compare"]["unsupported_fields"] == []
    assert_ratio_only(data)


def test_controlled_export_zip_bytes(web_db):
    with SessionLocal() as session:
        content = TargetAllocationControlledExportService(session).build_zip_bytes()
    payloads = read_zip_payloads(content)
    for payload in payloads.values():
        assert_ratio_only(payload)
    assert payloads["compare_result.json"]["matched"] is True
    assert payloads["compare_result.json"]["diffs"] == []


def test_controlled_export_cli_dry_run_does_not_write(web_db):
    before = set(EXPORT_DIR.glob("*")) if EXPORT_DIR.exists() else set()
    summary = run_cli("--dry-run")
    after = set(EXPORT_DIR.glob("*")) if EXPORT_DIR.exists() else set()
    assert after == before
    assert summary["matched"] is True
    assert summary["diff_count"] == 0
    assert summary["unsupported_field_count"] == 0
    assert summary["output_path"] is None
    assert_ratio_only(summary)


def test_controlled_export_cli_json_export(web_db):
    summary = run_cli("--format", "json")
    try:
        output = ROOT / summary["output_path"]
        assert output.is_file()
        assert output.parent == EXPORT_DIR
        assert summary["matched"] is True
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["compare"]["matched"] is True
        assert_ratio_only(data)
    finally:
        if summary.get("output_path"):
            (ROOT / summary["output_path"]).unlink(missing_ok=True)


def test_controlled_export_cli_zip_export(web_db):
    summary = run_cli("--format", "zip")
    try:
        output = ROOT / summary["output_path"]
        assert output.is_file()
        assert output.parent == EXPORT_DIR
        payloads = read_zip_payloads(output.read_bytes())
        for payload in payloads.values():
            assert_ratio_only(payload)
    finally:
        if summary.get("output_path"):
            (ROOT / summary["output_path"]).unlink(missing_ok=True)


def test_controlled_export_api_json(client):
    response = client.get("/api/target-allocation/shadow/export?format=json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["compare"]["matched"] is True
    assert payload["data"]["compare"]["diffs"] == []
    assert_ratio_only(payload)


def test_controlled_export_api_zip(client):
    response = client.get("/api/target-allocation/shadow/export?format=zip")
    assert response.status_code == 200
    assert "application/zip" in response.headers["content-type"]
    payloads = read_zip_payloads(response.content)
    for payload in payloads.values():
        assert_ratio_only(payload)


def test_controlled_export_no_mutation(web_db, client):
    before = current_state_snapshot(web_db)
    with SessionLocal() as session:
        service = TargetAllocationControlledExportService(session)
        service.build_export_payload()
        service.build_json_bytes()
        service.build_zip_bytes()
    run_cli("--dry-run")
    assert client.get("/api/target-allocation/shadow/export?format=json").status_code == 200
    assert client.get("/api/target-allocation/shadow/export?format=zip").status_code == 200
    after = current_state_snapshot(web_db)
    assert after == before


def test_controlled_export_current_only_code_paths():
    paths = [
        ROOT / "web" / "backend" / "app" / "services" / "target_allocation_export.py",
        ROOT / "scripts" / "export_target_allocation_shadow.py",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "latest_index.files" not in text
        assert '["files"]' not in text
        assert "['files']" not in text
        assert "target_allocation_2026-" not in text
        assert "market_score_2026-" not in text
        assert "action_plan_2026-" not in text
