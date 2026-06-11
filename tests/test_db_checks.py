from __future__ import annotations

from myinvest.db.checks import run_db_checks
from myinvest.db.connection import connect
from myinvest.db.ingest import expand_artifact_paths, ingest_artifacts
from myinvest.db.migrations import apply_migrations


def test_db_checks_cover_privacy_scan_rows(tmp_path) -> None:
    db_path = tmp_path / "history.sqlite3"
    apply_migrations(db_path)
    ingest_artifacts(db_path, expand_artifact_paths([], all_artifacts=True))

    assert run_db_checks(db_path, strict=True) == []

    conn = connect(db_path, create_parent=False)
    try:
        conn.execute("DELETE FROM privacy_scan_results WHERE privacy_scan_id = (SELECT privacy_scan_id FROM privacy_scan_results LIMIT 1)")
        conn.commit()
    finally:
        conn.close()

    findings = run_db_checks(db_path, strict=True)
    assert any("privacy scan coverage" in item.message for item in findings)
