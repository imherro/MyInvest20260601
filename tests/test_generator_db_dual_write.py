from __future__ import annotations

from myinvest.db.connection import ROOT
from myinvest.db.migrations import apply_migrations
from scripts.generate_action_plan import ingest_generated_action_plan
from scripts.generate_target_allocation import ingest_generated_target_allocation
from scripts.generate_valuation_reports import ingest_generated_reports
from scripts.qmt_portfolio_snapshot import ingest_generated_snapshot


def test_valuation_generator_db_ingest_helper(tmp_path) -> None:
    db_path = tmp_path / "history.sqlite3"
    sample = sorted((ROOT / "research" / "valuations").glob("*688333*.json"))[-1]

    apply_migrations(db_path)
    summary = ingest_generated_reports(db_path, [( {}, sample.with_suffix(".md"), sample)])

    assert summary is not None
    assert summary["research_runs_inserted"] == 1
    assert summary["artifacts_inserted"] == 1
    assert summary["valuation_reports_inserted"] == 1


def test_target_allocation_generator_db_ingest_helper(tmp_path) -> None:
    db_path = tmp_path / "history.sqlite3"
    sample = sorted((ROOT / "research" / "allocation").glob("target_allocation_*.json"))[-1]

    apply_migrations(db_path)
    summary = ingest_generated_target_allocation(db_path, sample)

    assert summary is not None
    assert summary["research_runs_inserted"] == 1
    assert summary["artifacts_inserted"] == 1
    assert summary["target_allocation_runs_inserted"] == 1


def test_action_plan_generator_db_ingest_helper(tmp_path) -> None:
    db_path = tmp_path / "history.sqlite3"
    sample = sorted((ROOT / "research" / "actions").glob("action_plan_*_latest_ratio_only.json"))[-1]

    apply_migrations(db_path)
    summary = ingest_generated_action_plan(db_path, sample)

    assert summary is not None
    assert summary["research_runs_inserted"] == 1
    assert summary["artifacts_inserted"] == 1
    assert summary["action_plans_inserted"] == 1


def test_portfolio_generator_db_ingest_helper(tmp_path) -> None:
    db_path = tmp_path / "history.sqlite3"
    sample = sorted((ROOT / "research" / "portfolio").glob("portfolio_snapshot_*.json"))[-1]

    apply_migrations(db_path)
    summary = ingest_generated_snapshot(db_path, sample)

    assert summary is not None
    assert summary["research_runs_inserted"] == 1
    assert summary["artifacts_inserted"] == 1
    assert summary["portfolio_snapshots_inserted"] == 1
