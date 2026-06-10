from __future__ import annotations

import io
import json
import sqlite3
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

from web.backend.app.db import SessionLocal
from web.backend.app.services.history_snapshot import (
    HISTORY_DB_PATH,
    HISTORY_EXPORT_DIR,
    ZIP_FILES,
    BLOCKED_VALUE_TERMS,
    HistorySnapshotService,
)
from web.backend.app.repositories import history_snapshot_repo as history_snapshot_repo_module
from web.backend.app.repositories.history_snapshot_repo import HistorySnapshotRepository
from web.backend.app.services.ratio_only import RatioOnlyService
from web.backend.app.services.target_allocation_candidate_audit import TargetAllocationCandidateAuditService
from web.backend.app.services.target_allocation_export import EXPORT_DIR, TargetAllocationControlledExportService
from web.backend.app.services.target_allocation_promotion import CANDIDATE_EXPORT_DIR


ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "temp" / "web_db" / "myinvest.sqlite"
LOCAL_PATH_RE = RatioOnlyService.local_path_re


def assert_ratio_only(value: Any) -> None:
    RatioOnlyService.assert_safe(value)
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    assert not LOCAL_PATH_RE.search(text)
    lowered = text.replace(chr(92), "/").lower()
    assert not any(term in lowered for term in BLOCKED_VALUE_TERMS)


def current_state_snapshot(web_db: Path) -> dict[str, Any]:
    with sqlite3.connect(web_db) as connection:
        connection.row_factory = sqlite3.Row
        modules = [dict(row) for row in connection.execute("SELECT module, artifact_id, updated_at FROM current_modules ORDER BY module")]
        current_artifacts = [
            dict(row)
            for row in connection.execute("SELECT module, path, is_current FROM artifacts WHERE is_current = 1 ORDER BY module, path")
        ]
    return {
        "latest_index": (ROOT / "research" / "latest_index.json").read_bytes(),
        "current_modules": modules,
        "current_artifacts": current_artifacts,
        "allocation_files": sorted(path.name for path in (ROOT / "research" / "allocation").glob("target_allocation_*.json")),
        "action_files": sorted(path.name for path in (ROOT / "research" / "actions").glob("action_plan_*.json")),
    }


def history_files() -> set[Path]:
    files: set[Path] = set()
    for directory in [HISTORY_EXPORT_DIR, CANDIDATE_EXPORT_DIR, EXPORT_DIR]:
        if directory.exists():
            files.update(path for path in directory.glob("*") if path.is_file())
    return files


def cleanup_new_files(before: set[Path]) -> None:
    for path in history_files() - before:
        path.unlink(missing_ok=True)
    remove_history_db()


def remove_history_db() -> None:
    for _ in range(10):
        try:
            HISTORY_DB_PATH.unlink(missing_ok=True)
            break
        except PermissionError:
            time.sleep(0.1)


def history_db_marker() -> tuple[bool, int | None]:
    if not HISTORY_DB_PATH.exists():
        return False, None
    return True, HISTORY_DB_PATH.stat().st_mtime_ns


def read_history_zip(content: bytes) -> dict[str, Any]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = set(archive.namelist())
        assert names == ZIP_FILES
        return {name: json.loads(archive.read(name).decode("utf-8")) for name in names}


def run_cli(*args: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "scripts/export_history_snapshot.py", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )
    return json.loads(proc.stdout)


def run_cli_raw(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/export_history_snapshot.py", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def test_history_snapshot_payload_is_safe(web_db):
    with SessionLocal() as session:
        payload = HistorySnapshotService(session).build_history_snapshot()
    assert payload["module"] == "history_snapshot"
    assert payload["export_type"] == "history_snapshot"
    assert payload["current_only"] is True
    assert payload["live_current_summary"]["shadow_vs_reference"]["matched"] is True
    assert payload["live_current_summary"]["candidate_audit_compare"]["matched"] is True
    assert payload["live_current_summary"]["replay_fixture_summary"]["failed"] == 0
    assert payload["live_current_summary"]["promotion_mode"]["official_allowed"] is False
    assert payload["safety"]["writes_research_files"] is False
    assert payload["safety"]["updates_latest_index"] is False
    assert payload["safety"]["updates_current_modules"] is False
    assert payload["safety"]["generates_action_plan"] is False
    assert_ratio_only(payload)


def test_history_snapshot_json_and_zip_bytes(web_db):
    with SessionLocal() as session:
        service = HistorySnapshotService(session)
        json_payload = json.loads(service.build_json_bytes().decode("utf-8"))
        zip_payloads = read_history_zip(service.build_zip_bytes())
    assert json_payload["live_current_summary"]["shadow_vs_reference"]["matched"] is True
    assert zip_payloads["history_snapshot.json"]["live_current_summary"]["candidate_audit_compare"]["matched"] is True
    assert zip_payloads["live_current_summary.json"]["replay_fixture_summary"]["failed"] == 0
    for payload in zip_payloads.values():
        assert_ratio_only(payload)


def test_history_snapshot_scans_existing_temp_exports(web_db):
    before = history_files()
    try:
        with SessionLocal() as session:
            TargetAllocationControlledExportService(session).write_to_temp("json")
            TargetAllocationCandidateAuditService(session).write_to_temp("json")
            payload = HistorySnapshotService(session).build_history_snapshot()
        kinds = {entry["export_kind"] for entry in payload["history_entries"]}
        assert "controlled_shadow_export" in kinds
        assert "candidate_audit" in kinds
        assert payload["source_export_count"] >= 2
        assert_ratio_only(payload)
    finally:
        cleanup_new_files(before)


def test_history_snapshot_cli_dry_run_does_not_write(web_db):
    before = history_files()
    summary = run_cli("--dry-run")
    after = history_files()
    assert after == before
    assert summary["output_path"] is None
    assert summary["database_written"] is False
    assert summary["shadow_matched"] is True
    assert summary["candidate_matched"] is True
    assert summary["replay_fail_count"] == 0
    assert summary["official_allowed"] is False
    RatioOnlyService.assert_safe(summary)


def test_history_snapshot_cli_json_export(web_db):
    before_state = current_state_snapshot(web_db)
    before_files = history_files()
    summary = run_cli("--format", "json")
    new_files = history_files() - before_files
    try:
        assert summary["shadow_matched"] is True
        assert summary["candidate_matched"] is True
        assert summary["replay_fail_count"] == 0
        assert summary["database_written"] is True
        assert str(summary["output_path"]).startswith("temp/history_exports/")
        assert len(new_files) == 1
        output = ROOT / summary["output_path"]
        payload = json.loads(output.read_text(encoding="utf-8"))
        assert payload["live_current_summary"]["shadow_vs_reference"]["matched"] is True
        assert_ratio_only(payload)
        assert HISTORY_DB_PATH.exists()
        with sqlite3.connect(HISTORY_DB_PATH) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'history_%' ORDER BY name"
                )
            }
        assert {"history_snapshot_metadata", "history_export_entries", "history_safety_checks"} <= tables
        assert current_state_snapshot(web_db) == before_state
    finally:
        cleanup_new_files(before_files)


def test_history_snapshot_cli_zip_export(web_db):
    before_state = current_state_snapshot(web_db)
    before_files = history_files()
    summary = run_cli("--format", "zip")
    new_files = history_files() - before_files
    try:
        assert summary["shadow_matched"] is True
        assert summary["candidate_matched"] is True
        assert str(summary["output_path"]).startswith("temp/history_exports/")
        assert len(new_files) == 1
        output = ROOT / summary["output_path"]
        payloads = read_history_zip(output.read_bytes())
        for payload in payloads.values():
            assert_ratio_only(payload)
        assert HISTORY_DB_PATH.exists()
        assert current_state_snapshot(web_db) == before_state
    finally:
        cleanup_new_files(before_files)


def test_history_snapshot_api_json(client):
    for path in ["/api/history/export", "/api/history/export?format=json"]:
        response = client.get(path)
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["data"]["live_current_summary"]["shadow_vs_reference"]["matched"] is True
        assert payload["data"]["live_current_summary"]["candidate_audit_compare"]["matched"] is True
        assert payload["data"]["live_current_summary"]["replay_fixture_summary"]["failed"] == 0
        assert_ratio_only(payload)


def test_history_snapshot_api_zip(client):
    response = client.get("/api/history/export?format=zip")
    assert response.status_code == 200
    assert "application/zip" in response.headers["content-type"]
    payloads = read_history_zip(response.content)
    for payload in payloads.values():
        assert_ratio_only(payload)


def test_history_snapshot_no_mutation(web_db, client):
    before_state = current_state_snapshot(web_db)
    with SessionLocal() as session:
        service = HistorySnapshotService(session)
        service.build_history_snapshot()
        service.build_json_bytes()
        service.build_zip_bytes()
    run_cli("--dry-run")
    assert client.get("/api/history/export?format=json").status_code == 200
    assert client.get("/api/history/export?format=zip").status_code == 200
    assert current_state_snapshot(web_db) == before_state


def test_history_snapshot_corrupt_sources_fail_safely(web_db, client):
    before_files = history_files()
    before_db = history_db_marker()
    bad_json = EXPORT_DIR / "corrupt_history_probe.json"
    bad_zip = CANDIDATE_EXPORT_DIR / "corrupt_history_probe.zip"
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    CANDIDATE_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        bad_json.write_text("{not valid json", encoding="utf-8")
        bad_zip.write_text("not a zip archive", encoding="utf-8")
        proc = run_cli_raw("--dry-run")
        assert proc.returncode == 1
        assert "Traceback" not in proc.stdout
        assert not LOCAL_PATH_RE.search(proc.stdout)
        payload = json.loads(proc.stdout)
        assert payload["ok"] is False
        assert payload["error"] == "history_snapshot_export_failed"
        assert payload["output_path"] is None
        assert payload["database_written"] is False
        RatioOnlyService.assert_safe(payload)
        response = client.get("/api/history/export")
        assert response.status_code == 500
        assert response.json()["detail"] == "history snapshot source scan failed"
        assert history_db_marker() == before_db
    finally:
        for path in history_files() - before_files:
            path.unlink(missing_ok=True)
        if before_db[0] is False:
            remove_history_db()


def test_history_snapshot_current_only_code_paths():
    paths = [
        ROOT / "web" / "backend" / "app" / "services" / "history_snapshot.py",
        ROOT / "scripts" / "export_history_snapshot.py",
        ROOT / "web" / "backend" / "app" / "routers" / "current.py",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "latest_index.files" not in text
        assert '["files"]' not in text
        assert "['files']" not in text
        assert "target_allocation_2026-" not in text
        assert "action_plan_2026-" not in text


def test_history_snapshot_service_delegates_io_to_repository():
    service_source = (ROOT / "web" / "backend" / "app" / "services" / "history_snapshot.py").read_text(encoding="utf-8")
    repo_source = (ROOT / "web" / "backend" / "app" / "repositories" / "history_snapshot_repo.py").read_text(
        encoding="utf-8"
    )

    assert "HistorySnapshotRepository" in service_source
    assert ".read_text(" not in service_source
    assert "sqlite3" not in service_source
    assert ".execute(" not in service_source
    assert "latest_index.files" not in repo_source
    assert ".read_text(" not in repo_source
    assert "HistorySnapshotRepository" in repo_source


def test_history_snapshot_repository_scans_temp_json_safely(monkeypatch):
    controlled_dir = ROOT / "temp" / "phase9b3_history_controlled"
    candidate_dir = ROOT / "temp" / "phase9b3_history_candidate"
    for directory in [controlled_dir, candidate_dir]:
        shutil.rmtree(directory, ignore_errors=True)
        directory.mkdir(parents=True, exist_ok=True)
    source = controlled_dir / "probe.json"
    ignored = controlled_dir / "ignored.txt"
    try:
        source.write_text(json.dumps({"module": "controlled_export", "current_only": True}), encoding="utf-8")
        ignored.write_text("ignored", encoding="utf-8")
        monkeypatch.setattr(history_snapshot_repo_module, "CONTROLLED_EXPORT_DIR", controlled_dir)
        monkeypatch.setattr(history_snapshot_repo_module, "CANDIDATE_EXPORT_DIR", candidate_dir)

        repo = HistorySnapshotRepository("sentinel")
        paths = repo.source_paths()
        payload = repo.read_export_payload(source)

        assert paths == [source]
        assert payload["current_only"] is True
        assert payload["module"] == "controlled_export"
    finally:
        shutil.rmtree(controlled_dir, ignore_errors=True)
        shutil.rmtree(candidate_dir, ignore_errors=True)
