#!/usr/bin/env python3
"""Export a ratio-only audit snapshot from the MyInvest history database."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from myinvest.db.checks import run_db_checks  # noqa: E402
from myinvest.db.connection import connect, resolve_db_path  # noqa: E402
from myinvest.db.migrations import check_migrations  # noqa: E402
from myinvest.db.queries.action_history import query_action_history  # noqa: E402
from myinvest.db.queries.market_history import query_market_history  # noqa: E402
from myinvest.db.queries.position_history import query_position_history  # noqa: E402
from myinvest.db.queries.valuation_history import query_valuation_history  # noqa: E402


def rel_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def db_counts(db_path: Path) -> dict[str, int]:
    conn = connect(db_path, create_parent=False)
    try:
        return {
            "tables": int(conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'").fetchone()[0]),
            "views": int(conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'view'").fetchone()[0]),
            "research_runs": int(conn.execute("SELECT COUNT(*) FROM research_runs").fetchone()[0]),
            "artifacts": int(conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]),
            "privacy_blocked": int(conn.execute("SELECT COUNT(*) FROM privacy_scan_results WHERE status != 'passed'").fetchone()[0]),
        }
    finally:
        conn.close()


def recent_positions(db_path: Path, *, limit: int) -> list[dict[str, Any]]:
    conn = connect(db_path, create_parent=False)
    try:
        rows = conn.execute(
            """
            SELECT
              slot_code, ts_code, name, slot_bucket_key, snapshot_bucket_key,
              category, snapshot_at, basis_trade_date, weight_pct,
              day_change_pct, reference_pnl_pct, lifecycle_status, snapshot_id
            FROM v_position_slot_history
            ORDER BY snapshot_at DESC, slot_code
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def build_report(
    db_path: str | Path,
    *,
    code: str | None = None,
    bucket: str | None = None,
    action_type: str | None = None,
    limit: int = 20,
    since: str | None = None,
    until: str | None = None,
) -> dict[str, Any]:
    path = resolve_db_path(db_path)
    migration = dict(check_migrations(path))
    if migration.get("db"):
        migration["db"] = rel_path(Path(str(migration["db"])))
    findings = run_db_checks(path, strict=True) if path.exists() else []
    positions = query_position_history(path, code=code, bucket=bucket) if code or bucket else recent_positions(path, limit=limit)
    market_history = filter_rows(query_market_history(path, limit=limit) if path.exists() else [], since=since, until=until)
    valuation_history = filter_rows(query_valuation_history(path, code) if path.exists() and code else [], since=since, until=until)
    position_history = filter_rows(positions[-limit:] if limit else positions, since=since, until=until)
    action_history = filter_rows(query_action_history(path, code=code, action_type=action_type, limit=limit) if path.exists() else [], since=since, until=until)
    return {
        "module": "history_db_export",
        "generated_at": datetime.now().strftime("%Y-%m-%d_%H%M%S"),
        "db": rel_path(path),
        "filters": {"code": code, "bucket": bucket, "action_type": action_type, "limit": limit, "since": since, "until": until},
        "summary": {
            **(db_counts(path) if path.exists() else {}),
            "db_ready": path.exists(),
            "migration_status": migration.get("status"),
            "finding_count": len(findings),
        },
        "migration": migration,
        "findings": [{"level": item.level, "message": item.message} for item in findings],
        "market_history": market_history,
        "valuation_history": valuation_history,
        "position_history": position_history,
        "action_history": action_history,
        "boundary": {
            "ratio_only": True,
            "prices_are_private": False,
            "no_trading_capability": True,
            "source_of_truth": "research JSON/Markdown artifacts; DB is derived and rebuildable",
        },
    }


def row_timestamp(row: dict[str, Any]) -> str:
    for key in ("generated_at", "snapshot_at", "basis_trade_date", "basis_date"):
        value = row.get(key)
        if value:
            return str(value)
    return ""


def filter_rows(rows: list[dict[str, Any]], *, since: str | None, until: str | None) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        stamp = row_timestamp(row)
        if since and stamp < since:
            continue
        if until and stamp > until:
            continue
        result.append(row)
    return result


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    filters = report["filters"]
    findings = report["findings"]
    lines = [
        "# History DB Export",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- DB: `{report['db']}`",
        f"- Migration: `{summary.get('migration_status')}`",
        f"- Tables / views: `{summary.get('tables', 0)}` / `{summary.get('views', 0)}`",
        f"- Artifacts / runs: `{summary.get('artifacts', 0)}` / `{summary.get('research_runs', 0)}`",
        f"- Privacy blocked rows: `{summary.get('privacy_blocked', 0)}`",
        f"- Filters: code=`{filters.get('code') or ''}` bucket=`{filters.get('bucket') or ''}` action_type=`{filters.get('action_type') or ''}`",
        "",
        "## Boundary",
        "",
        "- Ratio-only export.",
        "- Security prices are not private by themselves.",
        "- Amounts, quantities, accounts, orders, fills, deals, credentials, and local absolute paths remain excluded.",
        "- This export does not create trading capability.",
        "",
        "## Findings",
        "",
    ]
    if findings:
        lines.extend(f"- {item['level']}: {item['message']}" for item in findings)
    else:
        lines.append("- No DB quality findings.")

    lines.extend(["", "## Market History", "", "| generated_at | state | score | equity range |", "| --- | --- | ---: | --- |"])
    for row in report["market_history"]:
        lines.append(
            f"| {row.get('generated_at')} | {row.get('market_state') or ''} | {row.get('market_position_score') or ''} | "
            f"{row.get('equity_range_low_pct') or ''} - {row.get('equity_range_high_pct') or ''} |"
        )

    lines.extend(["", "## Position History", "", "| snapshot_at | code | bucket | weight pct |", "| --- | --- | --- | ---: |"])
    for row in report["position_history"]:
        lines.append(
            f"| {row.get('snapshot_at')} | {row.get('ts_code') or row.get('slot_code') or ''} | "
            f"{row.get('slot_bucket_key') or row.get('snapshot_bucket_key') or ''} | {row.get('weight_pct') or ''} |"
        )

    lines.extend(["", "## Action History", "", "| generated_at | action | subject | change |", "| --- | --- | --- | --- |"])
    for row in report["action_history"]:
        subject = row.get("subject_code") or row.get("bucket_key") or ""
        lines.append(
            f"| {row.get('generated_at')} | {row.get('action_type') or ''} | {subject} | {row.get('suggested_change_text') or ''} |"
        )

    return "\n".join(lines) + "\n"


def write_outputs(report: dict[str, Any], out_dir: Path, fmt: str, *, zip_output: bool = False) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"history_db_export_{report['generated_at']}"
    created: dict[str, str] = {}
    created_paths: list[Path] = []
    if fmt in {"json", "both"}:
        json_path = out_dir / f"{stem}.json"
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        created["json"] = rel_path(json_path)
        created_paths.append(json_path)
    if fmt in {"md", "both"}:
        md_path = out_dir / f"{stem}.md"
        md_path.write_text(render_markdown(report), encoding="utf-8")
        created["md"] = rel_path(md_path)
        created_paths.append(md_path)
    if zip_output:
        zip_path = out_dir / f"{stem}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in created_paths:
                archive.write(path, arcname=path.name)
        created["zip"] = rel_path(zip_path)
    return created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="temp/history_db/myinvest_history.sqlite3", help="SQLite database path.")
    parser.add_argument("--out-dir", default="temp/history_db/exports", help="Output directory under temp/.")
    parser.add_argument("--format", choices=["json", "md", "both"], default="both")
    parser.add_argument("--code", help="Optional security code filter.")
    parser.add_argument("--bucket", help="Optional position bucket filter.")
    parser.add_argument("--action-type", help="Optional action type filter.")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--since", help="Optional lower timestamp/date bound.")
    parser.add_argument("--until", help="Optional upper timestamp/date bound.")
    parser.add_argument("--zip", action="store_true", help="Also package created export files into a zip.")
    args = parser.parse_args(argv)

    report = build_report(args.db, code=args.code, bucket=args.bucket, action_type=args.action_type, limit=args.limit, since=args.since, until=args.until)
    created = write_outputs(report, ROOT / args.out_dir, args.format, zip_output=args.zip)
    print(json.dumps({"status": "ok", "created": created, "summary": report["summary"]}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
