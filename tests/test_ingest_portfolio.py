from __future__ import annotations

from myinvest.db.connection import ROOT
from myinvest.db.ingest import ingest_artifacts
from myinvest.db.migrations import apply_migrations
from myinvest.db.queries.position_history import query_position_history


def test_portfolio_ingest_populates_position_history(tmp_path) -> None:
    db_path = tmp_path / "history.sqlite3"
    sample = sorted((ROOT / "research" / "portfolio").glob("portfolio_snapshot_*.json"))[-1]

    apply_migrations(db_path)
    summary = ingest_artifacts(db_path, [sample])
    rows = query_position_history(db_path, code="511360.SH")

    assert summary["portfolio_snapshots_inserted"] == 1
    assert summary["portfolio_positions_inserted"] > 0
    assert summary["position_slots_inserted"] > 0
    assert rows
    assert rows[-1]["weight_pct"] is not None
    assert rows[-1]["slot_code"].startswith("PS-")
