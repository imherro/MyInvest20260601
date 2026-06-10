#!/usr/bin/env python3
"""Simulate target-allocation promotion modes without writing current state."""

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
from web.backend.app.services.target_allocation_promotion import (  # noqa: E402
    TargetAllocationPromotionSimulationService,
)


def ensure_db() -> None:
    if DB_PATH.exists():
        return
    subprocess.run([sys.executable, "scripts/ingest_current_state.py"], cwd=ROOT, check=True)


def candidate_summary(payload: dict, output_path: str | None) -> dict:
    compare = payload["golden_compare"]
    summary = {
        "mode": "candidate",
        "status": "candidate_temp_exported" if output_path else "candidate_dry_run",
        "matched": compare["matched"],
        "diff_count": len(compare.get("diffs") or []),
        "compared_field_count": len(compare.get("compared_fields") or []),
        "output_path": output_path,
        "ratio_only": "OK",
        "writes_research_files": False,
        "updates_latest_index": False,
        "updates_current_modules": False,
        "generates_action_plan": False,
    }
    RatioOnlyService.assert_safe(summary)
    return summary


def official_summary(report: dict) -> dict:
    summary = {
        "mode": "official",
        "status": report["status"],
        "output_path": None,
        "blocked": report["status"] == "blocked",
        "reason": report["reason"],
        "ratio_only": "OK",
        "writes_research_files": False,
        "updates_latest_index": False,
        "updates_current_modules": False,
        "generates_action_plan": False,
    }
    RatioOnlyService.assert_safe(summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["candidate", "official"], required=True)
    parser.add_argument("--write", action="store_true", help="write candidate JSON under temp/candidate_exports")
    parser.add_argument("--full-report", action="store_true", help="print the full sanitized report instead of a summary")
    args = parser.parse_args(argv)

    ensure_db()
    with SessionLocal() as session:
        service = TargetAllocationPromotionSimulationService(session)
        if args.mode == "official":
            report = service.build_official_block_report()
            output = report if args.full_report else official_summary(report)
        else:
            payload = service.build_candidate_payload()
            output_path = service.write_candidate_to_temp() if args.write else None
            output = payload if args.full_report else candidate_summary(payload, output_path)
    RatioOnlyService.assert_safe(output)
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
