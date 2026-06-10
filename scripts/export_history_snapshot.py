#!/usr/bin/env python3
"""Export a Phase 6 history snapshot to temp only."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "temp" / "web_db" / "myinvest.sqlite"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web.backend.app.db import SessionLocal  # noqa: E402
from web.backend.app.services.history_snapshot import HistorySnapshotService  # noqa: E402
from web.backend.app.services.ratio_only import RatioOnlyService  # noqa: E402


def ensure_db() -> None:
    if DB_PATH.exists():
        return
    subprocess.run([sys.executable, "scripts/ingest_current_state.py"], cwd=ROOT, check=True)


def build_summary(format_name: str, output_path: str | None, database_written: bool, payload: dict) -> dict:
    live = payload["live_current_summary"]
    shadow = live["shadow_vs_reference"]
    candidate = live["candidate_audit_compare"]
    replay = live["replay_fixture_summary"]
    promotion = live["promotion_mode"]
    summary = {
        "format": format_name,
        "output_path": output_path,
        "database_written": database_written,
        "source_export_count": payload["source_export_count"],
        "history_entry_count": len(payload["history_entries"]),
        "shadow_matched": shadow["matched"],
        "shadow_diff_count": shadow["diff_count"],
        "candidate_matched": candidate["matched"],
        "candidate_diff_count": candidate["diff_count"],
        "replay_scenario_count": replay["scenario_count"],
        "replay_fail_count": replay["failed"],
        "official_allowed": promotion["official_allowed"],
        "writes_research_files": False,
        "updates_latest_index": False,
        "updates_current_modules": False,
        "generates_action_plan": False,
        "ratio_only": "OK",
        "current_only": True,
    }
    RatioOnlyService.assert_safe(summary)
    return summary


def build_error_summary(exc: Exception) -> dict:
    summary = {
        "ok": False,
        "error": "history_snapshot_export_failed",
        "reason": RatioOnlyService.sanitize_text(str(exc))[:240] or "history snapshot export failed",
        "output_path": None,
        "database_written": False,
        "writes_research_files": False,
        "updates_latest_index": False,
        "updates_current_modules": False,
        "generates_action_plan": False,
        "ratio_only": "OK",
        "current_only": True,
    }
    RatioOnlyService.assert_safe(summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--format", choices=["json", "zip"], default="zip")
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args(argv)

    ensure_db()
    try:
        with SessionLocal() as session:
            service = HistorySnapshotService(session)
            payload = service.build_history_snapshot()
            service.assert_exportable(payload)
            if args.dry_run:
                output_path = None
                database_written = False
            else:
                output_path = service.write_to_temp(args.format)
                database_written = True
            output = build_summary(args.format, output_path, database_written, payload)
            if args.print_summary:
                output["summary"] = "history snapshot export check passed"
    except Exception as exc:  # noqa: BLE001
        output = build_error_summary(exc)
        print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    RatioOnlyService.assert_safe(output)
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
