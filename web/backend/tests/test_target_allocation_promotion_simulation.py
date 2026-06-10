from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

from web.backend.app.db import SessionLocal
from web.backend.app.services.ratio_only import RatioOnlyService
from web.backend.app.services.target_allocation_promotion import (
    CANDIDATE_EXPORT_DIR,
    TargetAllocationPromotionSimulationService,
)


ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "temp" / "web_db" / "myinvest.sqlite"


def conn(web_db: Path) -> sqlite3.Connection:
    assert web_db == DB_PATH
    connection = sqlite3.connect(web_db)
    connection.row_factory = sqlite3.Row
    return connection


def assert_ratio_only(value: Any) -> None:
    RatioOnlyService.assert_safe(value)


def current_state_snapshot(web_db: Path) -> dict[str, Any]:
    with conn(web_db) as db:
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


def candidate_files() -> set[Path]:
    if not CANDIDATE_EXPORT_DIR.exists():
        return set()
    return set(CANDIDATE_EXPORT_DIR.glob("*candidate*.json"))


def run_cli(*args: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "scripts/simulate_target_allocation_promotion.py", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )
    return json.loads(proc.stdout)


def test_promotion_mode_summary_is_safe(web_db):
    with SessionLocal() as session:
        summary = TargetAllocationPromotionSimulationService(session).build_mode_summary()
    statuses = {item["mode"]: item["status"] for item in summary["modes"]}
    assert statuses["reference"] == "allowed"
    assert statuses["shadow"] == "allowed"
    assert statuses["controlled_export"] == "allowed"
    assert statuses["candidate"] == "blocked"
    assert statuses["official"] == "blocked"
    assert statuses["unknown"] == "blocked"
    assert_ratio_only(summary)


def test_candidate_payload_uses_current_inputs_and_matches_shadow(web_db):
    with SessionLocal() as session:
        payload = TargetAllocationPromotionSimulationService(session).build_candidate_payload()
    assert payload["simulation_mode"] == "candidate"
    assert payload["status"] == "candidate_ready_for_temp_export"
    assert payload["mode_status"]["status"] == "blocked"
    assert payload["target_allocation"]["mode"] == "candidate"
    assert payload["target_allocation"]["scenario"] == "current_candidate_promotion_simulation"
    assert payload["golden_compare"]["matched"] is True
    assert payload["golden_compare"]["diffs"] == []
    assert payload["safety"]["writes_candidate_temp_export"] is True
    assert payload["safety"]["writes_research_files"] is False
    assert payload["safety"]["updates_latest_index"] is False
    assert payload["safety"]["updates_current_modules"] is False
    assert payload["safety"]["generates_action_plan"] is False
    assert_ratio_only(payload)


def test_candidate_write_only_uses_temp_candidate_exports(web_db):
    before_state = current_state_snapshot(web_db)
    before_files = candidate_files()
    with SessionLocal() as session:
        output_path = TargetAllocationPromotionSimulationService(session).write_candidate_to_temp()
    new_files = candidate_files() - before_files
    try:
        assert output_path.startswith("temp/candidate_exports/")
        assert "candidate" in Path(output_path).name
        assert len(new_files) == 1
        output = ROOT / output_path
        assert output in new_files
        payload = json.loads(output.read_text(encoding="utf-8"))
        assert payload["golden_compare"]["matched"] is True
        assert_ratio_only(payload)
        assert current_state_snapshot(web_db) == before_state
    finally:
        for path in new_files:
            path.unlink(missing_ok=True)


def test_official_mode_is_blocked_and_does_not_write(web_db):
    before_state = current_state_snapshot(web_db)
    before_files = candidate_files()
    with SessionLocal() as session:
        report = TargetAllocationPromotionSimulationService(session).build_official_block_report()
    assert report["simulation_mode"] == "official"
    assert report["status"] == "blocked"
    assert report["mode_status"]["status"] == "blocked"
    assert report["output_path"] is None
    assert report["safety"]["writes_candidate_temp_export"] is False
    assert current_state_snapshot(web_db) == before_state
    assert candidate_files() == before_files
    assert_ratio_only(report)


def test_promotion_simulation_cli_candidate_and_official(web_db):
    before_state = current_state_snapshot(web_db)
    before_files = candidate_files()
    dry = run_cli("--mode", "candidate")
    assert dry["status"] == "candidate_dry_run"
    assert dry["matched"] is True
    assert dry["diff_count"] == 0
    assert dry["output_path"] is None

    written = run_cli("--mode", "candidate", "--write")
    new_files = candidate_files() - before_files
    try:
        assert written["status"] == "candidate_temp_exported"
        assert written["matched"] is True
        assert written["diff_count"] == 0
        assert str(written["output_path"]).startswith("temp/candidate_exports/")
        assert "candidate" in Path(str(written["output_path"])).name
        assert len(new_files) == 1

        official = run_cli("--mode", "official")
        assert official["mode"] == "official"
        assert official["status"] == "blocked"
        assert official["blocked"] is True
        assert official["output_path"] is None

        assert current_state_snapshot(web_db) == before_state
    finally:
        for path in new_files:
            path.unlink(missing_ok=True)


def test_promotion_simulation_code_paths_are_current_only():
    paths = [
        ROOT / "web" / "backend" / "app" / "services" / "target_allocation_promotion.py",
        ROOT / "scripts" / "simulate_target_allocation_promotion.py",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "latest_index.files" not in text
        assert '["files"]' not in text
        assert "['files']" not in text
        assert "target_allocation_2026-" not in text
        assert "action_plan_2026-" not in text
