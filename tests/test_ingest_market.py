from __future__ import annotations

from myinvest.db.connection import ROOT
from myinvest.db.ingest import ingest_artifacts
from myinvest.db.migrations import apply_migrations
from myinvest.db.queries.market_history import query_market_history


def test_market_ingest_populates_market_history(tmp_path) -> None:
    db_path = tmp_path / "history.sqlite3"
    sample = sorted((ROOT / "research" / "market").glob("market_score_*.json"))[-1]

    apply_migrations(db_path)
    summary = ingest_artifacts(db_path, [sample])
    rows = query_market_history(db_path)

    assert summary["market_score_runs_inserted"] == 1
    assert summary["market_score_components_inserted"] > 0
    assert rows
    assert rows[-1]["market_position_score"] is not None
    assert rows[-1]["equity_range_low_pct"] is not None
