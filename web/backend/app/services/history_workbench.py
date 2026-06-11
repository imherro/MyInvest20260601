from __future__ import annotations

from pathlib import Path
from typing import Any

from myinvest.db.checks import run_db_checks
from myinvest.db.connection import ROOT, connect
from myinvest.db.migrations import check_migrations
from myinvest.db.queries.action_history import query_action_history
from myinvest.db.queries.market_history import query_market_history
from myinvest.db.queries.position_history import query_position_history
from myinvest.db.queries.security_research_history import query_security_research_history
from myinvest.db.queries.valuation_history import query_valuation_history

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

    def coverage(self) -> dict[str, Any]:
        if not self.db_path.exists():
            return {"rows": [], "summary": {"db_ready": False, "module_count": 0, "artifact_count": 0}}
        normalized = self._normalized_counts()
        conn = connect(self.db_path, create_parent=False)
        try:
            rows = [
                {
                    "module": str(row["module"]),
                    "artifact_count": int(row["artifact_count"]),
                    "first_generated_at": row["first_generated_at"],
                    "latest_generated_at": row["latest_generated_at"],
                    "normalized_count": normalized.get(str(row["module"]), 0),
                }
                for row in conn.execute(
                    """
                    SELECT
                      module,
                      COUNT(*) AS artifact_count,
                      MIN(generated_at) AS first_generated_at,
                      MAX(generated_at) AS latest_generated_at
                    FROM artifacts
                    GROUP BY module
                    ORDER BY module
                    """
                ).fetchall()
            ]
        finally:
            conn.close()
        return {
            "rows": rows,
            "summary": {
                "db_ready": True,
                "module_count": len(rows),
                "artifact_count": sum(row["artifact_count"] for row in rows),
                "normalized_module_count": sum(1 for row in rows if row["normalized_count"] > 0),
            },
        }

    def security_history(self, code: str) -> dict[str, Any]:
        if not self.db_path.exists():
            return {
                "code": code,
                "summary": {"db_ready": False, "valuation_count": 0, "position_count": 0, "action_count": 0, "profile_count": 0},
                "valuation_history": [],
                "position_history": [],
                "action_history": [],
                "profile_history": [],
            }
        valuations = query_valuation_history(self.db_path, code)
        positions = query_position_history(self.db_path, code=code)
        actions = query_action_history(self.db_path, code=code, limit=100)
        profiles = query_security_research_history(self.db_path, code)
        latest_dates = [
            item
            for item in [
                valuations[-1]["generated_at"] if valuations else None,
                positions[-1]["snapshot_at"] if positions else None,
                actions[-1]["generated_at"] if actions else None,
                profiles[-1]["generated_at"] if profiles else None,
            ]
            if item
        ]
        return {
            "code": code,
            "summary": {
                "db_ready": True,
                "valuation_count": len(valuations),
                "position_count": len(positions),
                "action_count": len(actions),
                "profile_count": len(profiles),
                "latest_generated_at": max(latest_dates) if latest_dates else None,
            },
            "valuation_history": valuations[-20:],
            "position_history": positions[-20:],
            "action_history": actions[-20:],
            "profile_history": profiles[-20:],
            "note": "security history is read-only and ratio-only; it is not a trading instruction",
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

    def _normalized_counts(self) -> dict[str, int]:
        table_by_module = {
            "action_plan": "action_plans",
            "market_score": "market_score_runs",
            "portfolio_snapshot": "portfolio_snapshots",
            "target_allocation": "target_allocation_runs",
            "theme_review": "theme_review_runs",
            "valuation_report": "valuation_reports",
            "etf_profile": "security_profile_runs",
            "stock_profile": "security_profile_runs",
        }
        conn = connect(self.db_path, create_parent=False)
        try:
            counts: dict[str, int] = {}
            for module, table in table_by_module.items():
                if module in {"etf_profile", "stock_profile"}:
                    counts[module] = int(
                        conn.execute(
                            """
                            SELECT COUNT(*)
                            FROM security_profile_runs spr
                            JOIN artifacts a ON a.run_id = spr.run_id
                            WHERE a.module = ?
                            """,
                            (module,),
                        ).fetchone()[0]
                    )
                else:
                    counts[module] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            return counts
        finally:
            conn.close()

    def _relative_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            return path.name
