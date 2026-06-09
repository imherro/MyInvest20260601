from __future__ import annotations

import sqlite3


def test_ingest_creates_required_tables(web_db):
    assert web_db.exists()
    conn = sqlite3.connect(web_db)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        }
    finally:
        conn.close()
    assert "current_modules" in tables
    assert "action_plans" in tables
    assert "system_check_results" in tables


def test_current_modules_has_action_plan(web_db):
    conn = sqlite3.connect(web_db)
    try:
        count = conn.execute("SELECT COUNT(*) FROM current_modules WHERE module='action_plan'").fetchone()[0]
    finally:
        conn.close()
    assert count == 1
