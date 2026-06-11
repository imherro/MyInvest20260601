#!/usr/bin/env python3
"""Build and compare a latest_index shadow from the history database."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from myinvest.db.connection import connect, resolve_db_path  # noqa: E402


LATEST_INDEX = ROOT / "research" / "latest_index.json"


def build_shadow(db_path: str | Path) -> dict[str, Any]:
    path = resolve_db_path(db_path)
    current = json.loads(LATEST_INDEX.read_text(encoding="utf-8-sig"))
    current_modules = current.get("modules") or {}
    conn = connect(path, create_parent=False)
    try:
        modules: dict[str, dict[str, Any]] = {}
        for module, record in sorted(current_modules.items()):
            if not isinstance(record, dict) or not record.get("path"):
                continue
            row = conn.execute(
                """
                SELECT module, path, sha256, generated_at, basis_date, basis_trade_date
                FROM artifacts
                WHERE path = ?
                ORDER BY generated_at DESC
                LIMIT 1
                """,
                (record["path"],),
            ).fetchone()
            if row is None:
                continue
            modules[str(module)] = {
                "path": row["path"],
                "sha256": row["sha256"],
                "generated_at": row["generated_at"],
                "basis_date": row["basis_date"],
                "basis_trade_date": row["basis_trade_date"],
                "db_module": row["module"],
            }
    finally:
        conn.close()
    return {
        "module": "latest_index_shadow",
        "generated_at": datetime.now().strftime("%Y-%m-%d_%H%M%S"),
        "source_db": str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path.name).replace("\\", "/"),
        "source_index": "research/latest_index.json",
        "modules": modules,
    }


def compare_with_current(shadow: dict[str, Any], current_path: Path = LATEST_INDEX) -> dict[str, Any]:
    current = json.loads(current_path.read_text(encoding="utf-8-sig"))
    current_modules = current.get("modules") or {}
    shadow_modules = shadow.get("modules") or {}
    mismatches = []
    missing_in_db = []
    extra_in_db = []
    for module, record in sorted(current_modules.items()):
        if not isinstance(record, dict) or not record.get("path"):
            continue
        shadow_record = shadow_modules.get(module)
        if not shadow_record:
            missing_in_db.append(module)
            continue
        if shadow_record.get("path") != record.get("path"):
            mismatches.append({"module": module, "current_path": record.get("path"), "db_path": shadow_record.get("path")})
    for module in sorted(set(shadow_modules) - {key for key, value in current_modules.items() if isinstance(value, dict)}):
        extra_in_db.append(module)
    return {
        "missing_in_db": missing_in_db,
        "extra_in_db": extra_in_db,
        "path_mismatches": mismatches,
        "ok": not missing_in_db and not mismatches,
    }


def write_shadow(shadow: dict[str, Any], comparison: dict[str, Any], out: Path | None) -> str | None:
    if out is None:
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"shadow": shadow, "comparison": comparison}, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    try:
        return out.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return out.name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="temp/history_db/myinvest_history.sqlite3", help="SQLite database path.")
    parser.add_argument("--out", type=Path, help="Optional output JSON path, preferably under temp/.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when DB and current latest_index differ.")
    args = parser.parse_args(argv)

    shadow = build_shadow(args.db)
    comparison = compare_with_current(shadow)
    created = write_shadow(shadow, comparison, args.out)
    print(json.dumps({"status": "ok" if comparison["ok"] else "mismatch", "created": created, "comparison": comparison}, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if args.strict and not comparison["ok"] else 0


if __name__ == "__main__":
    sys.exit(main())
