from __future__ import annotations

from myinvest.db.connection import ROOT
from myinvest.db.ingest import ingest_artifacts
from myinvest.db.migrations import apply_migrations
from myinvest.db.queries.action_history import query_action_history


def test_action_ingest_populates_action_history(tmp_path) -> None:
    db_path = tmp_path / "history.sqlite3"
    portfolio = sorted((ROOT / "research" / "portfolio").glob("portfolio_snapshot_*.json"))[-1]
    allocation = sorted((ROOT / "research" / "allocation").glob("target_allocation_*.json"))[-1]
    action = sorted((ROOT / "research" / "actions").glob("action_plan_*.json"))[-1]

    apply_migrations(db_path)
    summary = ingest_artifacts(db_path, [portfolio, allocation, action])
    rows = query_action_history(db_path, action_type="Reduce")

    assert summary["target_allocation_runs_inserted"] == 1
    assert summary["action_plans_inserted"] == 1
    assert summary["action_items_inserted"] > 0
    assert rows
    assert rows[0]["suggested_change_low_pp"] is not None
    assert rows[0]["needs_manual_confirmation"] == 1
