"""SQLite connection helpers for the MyInvest history database."""

from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = ROOT / "temp" / "history_db" / "myinvest_history.sqlite3"


def resolve_db_path(db_path: str | Path | None = None) -> Path:
    """Return an absolute database path within the local workspace when relative."""

    if db_path is None:
        return DEFAULT_DB_PATH
    path = Path(db_path)
    if not path.is_absolute():
        path = ROOT / path
    return path


def connect(db_path: str | Path | None = None, *, create_parent: bool = True) -> sqlite3.Connection:
    """Open a SQLite connection with project defaults enabled."""

    path = resolve_db_path(db_path)
    if create_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
