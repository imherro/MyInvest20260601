from __future__ import annotations

from myinvest.db.connection import ROOT
from myinvest.db.ingest import ingest_artifacts
from myinvest.db.migrations import apply_migrations
from myinvest.db.queries.security_research_history import query_security_research_history
from myinvest.db.queries.theme_history import query_theme_history


def test_theme_and_security_profile_ingest(tmp_path) -> None:
    db_path = tmp_path / "history.sqlite3"
    theme = sorted((ROOT / "research" / "themes").glob("theme_review_*.json"))[-1]
    etf = sorted((ROOT / "research" / "etfs").glob("*588200*.json"))[-1]

    apply_migrations(db_path)
    summary = ingest_artifacts(db_path, [theme, etf])
    theme_rows = query_theme_history(db_path)
    security_rows = query_security_research_history(db_path, "588200.SH")

    assert summary["theme_review_runs_inserted"] == 1
    assert summary["theme_review_items_inserted"] > 0
    assert summary["security_profile_runs_inserted"] == 1
    assert theme_rows
    assert security_rows
    assert security_rows[0]["action_rating"] is not None
