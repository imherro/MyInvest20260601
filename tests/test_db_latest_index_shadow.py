from __future__ import annotations

from myinvest.db.ingest import expand_artifact_paths, ingest_artifacts
from myinvest.db.migrations import apply_migrations
from scripts.db_build_latest_index_shadow import build_shadow, compare_with_current


def test_db_latest_index_shadow_matches_current_modules(tmp_path) -> None:
    db_path = tmp_path / "history.sqlite3"
    apply_migrations(db_path)
    ingest_artifacts(db_path, expand_artifact_paths([], all_artifacts=True))

    shadow = build_shadow(db_path)
    comparison = compare_with_current(shadow)

    assert shadow["modules"]
    assert comparison["ok"] is True
    assert comparison["path_mismatches"] == []
