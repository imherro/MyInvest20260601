from __future__ import annotations

import json

from myinvest.db.connection import ROOT
from myinvest.db.ingest import ingest_artifacts
from myinvest.db.migrations import apply_migrations
from myinvest.db.privacy import scan_json_privacy
from scripts.db_export_report import build_report, write_outputs


def test_db_export_report_writes_ratio_only_snapshot(tmp_path) -> None:
    db_path = tmp_path / "history.sqlite3"
    out_dir = tmp_path / "exports"
    apply_migrations(db_path)
    ingest_artifacts(
        db_path,
        [
            sorted((ROOT / "research" / "market").glob("market_score_*.json"))[-1],
            sorted((ROOT / "research" / "portfolio").glob("portfolio_snapshot_*.json"))[-1],
            sorted((ROOT / "research" / "actions").glob("action_plan_*_latest_ratio_only.json"))[-1],
            sorted((ROOT / "research" / "valuations").glob("*688333*.json"))[-1],
        ],
    )

    report = build_report(db_path, code="688333.SH", limit=5, since="2026-01-01", until="2099-01-01")
    created = write_outputs(report, out_dir, "both", zip_output=True)

    json_path = out_dir / created["json"].split("/")[-1]
    md_path = out_dir / created["md"].split("/")[-1]
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert json_path.exists()
    assert md_path.exists()
    assert (out_dir / created["zip"].split("/")[-1]).exists()
    assert payload["summary"]["migration_status"] == "ok"
    assert payload["market_history"]
    assert payload["valuation_history"]
    assert scan_json_privacy(payload) == []
    assert "Security prices are not private" in md_path.read_text(encoding="utf-8")
