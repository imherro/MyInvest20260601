from __future__ import annotations

from pathlib import Path
from typing import Any

from myinvest.db.checks import run_db_checks
from myinvest.db.connection import ROOT, connect
from myinvest.db.migrations import check_migrations
from myinvest.db.queries.action_history import query_action_history
from myinvest.db.queries.market_history import query_market_history
from myinvest.db.queries.position_history import query_position_history

from ..config import HISTORY_DB_PATH


class HistoryWorkbenchService:
    def __init__(self, db_path: Path = HISTORY_DB_PATH) -> None:
        self.db_path = db_path

    def _missing(self, kind: str) -> dict[str, Any]:
        return {
            "rows": [],
            "summary": {"kind": kind, "count": 0, "db_ready": False, "latest_generated_at": None},
        }

    def market_history(self, *, limit: int = 50) -> dict[str, Any]:
        if not self.db_path.exists():
            return self._missing("market_history")
        rows = [self._without_narrative(row) for row in query_market_history(self.db_path, limit=limit)]
        return {
            "rows": rows,
            "summary": {
                "kind": "market_history",
                "count": len(rows),
                "db_ready": True,
                "latest_generated_at": rows[-1]["generated_at"] if rows else None,
                "latest_market_state": rows[-1]["market_state"] if rows else None,
            },
            "note": "market history contains scores and ratio ranges only",
        }

    def position_history(self, *, code: str | None = None, bucket: str | None = None, limit: int = 100) -> dict[str, Any]:
        if not self.db_path.exists():
            result = self._missing("position_history")
            result["filters"] = {"code": code, "bucket": bucket}
            return result
        if code or bucket:
            rows = query_position_history(self.db_path, code=code, bucket=bucket)
            if limit:
                rows = rows[-limit:]
        else:
            rows = self._recent_positions(limit=limit)
        return {
            "filters": {"code": code, "bucket": bucket},
            "rows": rows,
            "summary": {
                "kind": "position_history",
                "count": len(rows),
                "db_ready": True,
                "latest_generated_at": rows[-1]["snapshot_at"] if rows else None,
            },
            "note": "portfolio history stores ratios and percentage points only",
        }

    def action_history(
        self,
        *,
        code: str | None = None,
        action_type: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        if not self.db_path.exists():
            result = self._missing("action_history")
            result["filters"] = {"code": code, "action_type": action_type}
            return result
        rows = [self._without_narrative(row) for row in query_action_history(self.db_path, code=code, action_type=action_type, limit=limit)]
        return {
            "filters": {"code": code, "action_type": action_type},
            "rows": rows,
            "summary": {
                "kind": "action_history",
                "count": len(rows),
                "db_ready": True,
                "latest_generated_at": rows[-1]["generated_at"] if rows else None,
            },
            "note": "action history is ratio-only and requires manual confirmation",
        }

    def quality(self) -> dict[str, Any]:
        migration_state = dict(check_migrations(self.db_path))
        if migration_state.get("db"):
            migration_state["db"] = self._relative_path(Path(str(migration_state["db"])))
        findings = []
        if self.db_path.exists():
            findings = run_db_checks(self.db_path, strict=True)
        fail_count = sum(1 for item in findings if item.level == "FAIL")
        warn_count = sum(1 for item in findings if item.level == "WARN")
        counts = self._object_counts() if self.db_path.exists() else {}
        return {
            "summary": {
                "db_ready": self.db_path.exists(),
                "migration_status": migration_state.get("status"),
                "fail_count": fail_count,
                "warn_count": warn_count,
                "table_count": counts.get("tables", 0),
                "view_count": counts.get("views", 0),
            },
            "migration": migration_state,
            "findings": [{"level": item.level, "message": item.message} for item in findings],
            "counts": counts,
        }

    def _recent_positions(self, *, limit: int) -> list[dict[str, Any]]:
        conn = connect(self.db_path, create_parent=False)
        try:
            rows = conn.execute(
                """
                SELECT
                  slot_code, ts_code, name, slot_bucket_key, snapshot_bucket_key,
                  category, snapshot_at, basis_trade_date, weight_pct,
                  day_change_pct, reference_pnl_pct, lifecycle_status, snapshot_id
                FROM v_position_slot_history
                ORDER BY snapshot_at DESC, slot_code
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def _without_narrative(self, row: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in row.items() if key not in {"one_line_conclusion"}}

    def _object_counts(self) -> dict[str, int]:
        conn = connect(self.db_path, create_parent=False)
        try:
            tables = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'").fetchone()[0]
            views = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'view'").fetchone()[0]
            artifacts = conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
            runs = conn.execute("SELECT COUNT(*) FROM research_runs").fetchone()[0]
            return {"tables": int(tables), "views": int(views), "artifacts": int(artifacts), "research_runs": int(runs)}
        finally:
            conn.close()

    def _relative_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            return path.name
