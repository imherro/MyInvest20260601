"""DB integrity checks for project_check.py."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .connection import ROOT, connect
from .migrations import check_migrations


RESEARCH = ROOT / "research"


@dataclass(frozen=True)
class DbFinding:
    level: str
    message: str


def level(strict: bool) -> str:
    return "FAIL" if strict else "WARN"


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def research_json_paths() -> set[str]:
    return {
        rel(path)
        for path in RESEARCH.rglob("*.json")
        if "temp" not in path.parts and "runtime" not in path.parts
    }


def scalar(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    return int(conn.execute(sql, params).fetchone()[0])


def check_artifact_coverage(conn: sqlite3.Connection, findings: list[DbFinding], strict: bool) -> None:
    db_paths = {str(row["path"]) for row in conn.execute("SELECT path FROM artifacts")}
    missing = sorted(research_json_paths() - db_paths)
    if missing:
        sample = ", ".join(missing[:5])
        findings.append(DbFinding(level(strict), f"DB artifact coverage missing {len(missing)} research JSON files: {sample}"))


def check_normalized_coverage(conn: sqlite3.Connection, findings: list[DbFinding], strict: bool) -> None:
    checks = [
        ("valuation_report", "valuation_reports"),
        ("portfolio_snapshot", "portfolio_snapshots"),
        ("target_allocation", "target_allocation_runs"),
        ("action_plan", "action_plans"),
    ]
    for module, table in checks:
        missing = scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM artifacts a
            LEFT JOIN {table} n ON n.run_id = a.run_id
            WHERE a.module = ? AND n.run_id IS NULL
            """,
            (module,),
        )
        if missing:
            findings.append(DbFinding(level(strict), f"DB normalized coverage missing {missing} rows for module {module}"))


def check_dependencies(conn: sqlite3.Connection, findings: list[DbFinding], strict: bool) -> None:
    missing = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM artifact_dependencies d
        JOIN artifacts a ON a.artifact_id = d.artifact_id
        WHERE a.module = 'action_plan' AND d.status = 'missing'
        """,
    )
    if missing:
        findings.append(DbFinding(level(strict), f"DB action_plan dependencies contain {missing} missing paths"))


def check_valuation_zones(conn: sqlite3.Connection, findings: list[DbFinding], strict: bool) -> None:
    missing_zones = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM valuation_reports vr
        LEFT JOIN valuation_zones vz ON vz.valuation_id = vr.valuation_id
        WHERE vz.valuation_id IS NULL
        """,
    )
    if missing_zones:
        findings.append(DbFinding(level(strict), f"DB valuation zone check found {missing_zones} reports without zones"))

    invalid_zone = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM valuation_reports vr
        WHERE vr.current_zone_key IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM valuation_zones vz
            WHERE vz.valuation_id = vr.valuation_id AND vz.zone_key = vr.current_zone_key
          )
        """,
    )
    if invalid_zone:
        findings.append(DbFinding(level(strict), f"DB valuation zone check found {invalid_zone} current zones not in zone rows"))


def check_privacy(conn: sqlite3.Connection, findings: list[DbFinding], strict: bool) -> None:
    blocked = scalar(conn, "SELECT COUNT(*) FROM privacy_scan_results WHERE status != 'passed'")
    if blocked:
        findings.append(DbFinding(level(strict), f"DB privacy scan blocked raw_json for {blocked} artifacts"))


def check_latest_consistency(conn: sqlite3.Connection, findings: list[DbFinding], strict: bool) -> None:
    latest_path = RESEARCH / "latest_index.json"
    if not latest_path.exists():
        return
    latest = json.loads(latest_path.read_text(encoding="utf-8-sig"))
    missing: list[str] = []
    for item in (latest.get("modules") or {}).values():
        if not isinstance(item, dict) or not item.get("path"):
            continue
        count = scalar(conn, "SELECT COUNT(*) FROM artifacts WHERE path = ?", (item["path"],))
        if not count:
            missing.append(item["path"])
    if missing:
        sample = ", ".join(missing[:5])
        findings.append(DbFinding(level(strict), f"DB latest consistency missing {len(missing)} latest module artifacts: {sample}"))


def run_db_checks(db_path: str | Path, *, strict: bool = False) -> list[DbFinding]:
    findings: list[DbFinding] = []
    migration_state = check_migrations(db_path)
    if migration_state.get("status") != "ok":
        findings.append(DbFinding(level(strict), f"DB migration check status={migration_state.get('status')}"))
        return findings

    conn = connect(db_path, create_parent=False)
    try:
        check_artifact_coverage(conn, findings, strict)
        check_normalized_coverage(conn, findings, strict)
        check_dependencies(conn, findings, strict)
        check_valuation_zones(conn, findings, strict)
        check_privacy(conn, findings, strict)
        check_latest_consistency(conn, findings, strict)
    finally:
        conn.close()
    return findings
