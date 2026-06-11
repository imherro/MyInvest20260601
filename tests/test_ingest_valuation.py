from __future__ import annotations

from myinvest.db.connection import ROOT
from myinvest.db.ingest import ingest_artifacts
from myinvest.db.migrations import apply_migrations
from myinvest.db.queries.valuation_history import query_valuation_history


def test_valuation_ingest_populates_history_view(tmp_path) -> None:
    db_path = tmp_path / "history.sqlite3"
    sample = sorted((ROOT / "research" / "valuations").glob("*688333*.json"))[-1]

    apply_migrations(db_path)
    summary = ingest_artifacts(db_path, [sample])
    rows = query_valuation_history(db_path, "688333.SH")

    assert summary["valuation_reports_inserted"] == 1
    assert summary["valuation_zones_inserted"] >= 4
    assert rows
    assert rows[0]["reasonable_min"] is not None
    assert rows[0]["not_portfolio_action"] == 1
