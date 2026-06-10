#!/usr/bin/env python3
"""Export a candidate target-allocation audit bundle to temp only."""

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
from web.backend.app.services.ratio_only import RatioOnlyService  # noqa: E402
from web.backend.app.services.target_allocation_candidate_audit import (  # noqa: E402
    TargetAllocationCandidateAuditService,
)


def ensure_db() -> None:
    if DB_PATH.exists():
        return
    subprocess.run([sys.executable, "scripts/ingest_current_state.py"], cwd=ROOT, check=True)


def build_summary(format_name: str, output_path: str | None, payload: dict) -> dict:
    compare = payload["compare"]
    replay = payload["replay_summary"]
    promotion = payload["promotion_mode"]
    summary = {
        "format": format_name,
        "output_path": output_path,
        "matched": compare["matched"],
        "diff_count": len(compare.get("diffs") or []),
        "unsupported_field_count": len(compare.get("unsupported_fields") or []),
        "compared_field_count": len(compare.get("compared_fields") or []),
        "replay_scenario_count": replay["scenario_count"],
        "replay_fail_count": replay["failed"],
        "candidate_allowed": promotion["candidate_allowed"],
        "official_allowed": promotion["official_allowed"],
        "writes_research_files": False,
        "updates_latest_index": False,
        "updates_current_modules": False,
        "generates_action_plan": False,
        "ratio_only": "OK",
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
    with SessionLocal() as session:
        service = TargetAllocationCandidateAuditService(session)
        payload = service.build_audit_payload()
        service.assert_exportable(payload)
        if args.dry_run:
            output_path = None
        else:
            output_path = service.write_to_temp(args.format)
        output = build_summary(args.format, output_path, payload)
        if args.print_summary:
            output["summary"] = "candidate audit bundle export check passed"
    RatioOnlyService.assert_safe(output)
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
