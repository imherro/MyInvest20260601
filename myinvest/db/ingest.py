"""Research artifact ingestion for the MyInvest history database."""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .connection import ROOT, connect
from .privacy import scan_json_privacy


RESEARCH = ROOT / "research"
TIMESTAMP_RE = __import__("re").compile(r"(\d{4}-\d{2}-\d{2}_\d{6})")
MODULE_ALIASES = {
    "MARKET_POSITION": "market_score",
    "market_position": "market_score",
    "market_score": "market_score",
    "THEME_RESEARCH": "theme_review",
    "theme_research": "theme_review",
    "theme_review": "theme_review",
    "theme_leaders": "theme_leaders",
    "target_allocation_reference": "target_allocation",
    "target_allocation": "target_allocation",
    "portfolio_analysis": "portfolio_snapshot",
    "portfolio_snapshot": "portfolio_snapshot",
    "portfolio_research_backlog": "research_backlog",
    "research_backlog": "research_backlog",
    "valuation_report": "valuation_report",
    "intraday_rules": "intraday_rules",
    "intraday_alert": "intraday_alerts",
    "intraday_analysis": "intraday_alerts",
    "intraday_alerts": "intraday_alerts",
    "premarket_check": "premarket_check",
    "PREMARKET_CHECK": "premarket_check",
    "action_plan": "action_plan",
    "post_market_review": "post_market_review",
    "staleness_check": "staleness_check",
    "STRATEGY_BRIEFING": "STRATEGY_BRIEFING",
    "ETF_RESEARCH": "etf_profile",
    "etf_research": "etf_profile",
    "stock_profile": "stock_profile",
    "STOCK_RESEARCH": "stock_profile",
    "stock_research": "stock_profile",
    "etf_profile": "etf_profile",
}
MODULE_BY_DIR = {
    "market": "market_score",
    "themes": "theme_review",
    "theme_leaders": "theme_leaders",
    "allocation": "target_allocation",
    "portfolio": "portfolio_snapshot",
    "valuations": "valuation_report",
    "alerts": "intraday_rules",
    "checks": "premarket_check",
    "actions": "action_plan",
    "reviews": "post_market_review",
    "stocks": "stock_profile",
    "etfs": "etf_profile",
    "briefings": "STRATEGY_BRIEFING",
    "config": "config",
}


class IngestError(Exception):
    """Raised when artifact ingestion cannot safely continue."""


@dataclass(frozen=True)
class ArtifactPlan:
    path: Path
    rel_path: str
    sha256: str
    data: dict[str, Any]
    module: str
    generated_at: str
    basis_date: str | None
    basis_trade_date: str | None
    code: str | None
    name: str | None
    quality_status: str
    staleness_status: str
    dependency_paths: tuple[str, ...]
    privacy_findings: tuple[dict[str, str], ...]
    artifact_id: str = field(init=False)
    run_id: str = field(init=False)

    def __post_init__(self) -> None:
        artifact_digest = stable_digest(f"artifact|{self.rel_path}|{self.sha256}")
        run_digest = stable_digest(f"run|{self.module}|{self.generated_at}|{self.rel_path}|{self.sha256}")
        object.__setattr__(self, "artifact_id", f"artifact_{artifact_digest[:20]}")
        object.__setattr__(self, "run_id", f"run_{run_digest[:20]}")

    @property
    def safe_raw_json(self) -> str | None:
        if self.privacy_findings:
            return None
        return json.dumps(self.data, ensure_ascii=False, sort_keys=True)

    @property
    def privacy_status(self) -> str:
        return "blocked_raw_json" if self.privacy_findings else "passed"


def stable_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def timestamp_from_name(path: Path) -> str | None:
    match = TIMESTAMP_RE.search(path.name)
    return match.group(1) if match else None


def normalize_module(value: Any, path: Path) -> str:
    text = str(value or "").strip()
    if text in MODULE_ALIASES:
        return MODULE_ALIASES[text]
    lowered = text.lower()
    if lowered in MODULE_ALIASES:
        return MODULE_ALIASES[lowered]
    if text:
        return text
    candidate = path if path.is_absolute() else ROOT / path
    try:
        first = candidate.relative_to(RESEARCH).parts[0]
    except ValueError:
        return "unknown"
    return MODULE_BY_DIR.get(first, first)


def quality_status(data: dict[str, Any]) -> str:
    value = data.get("quality")
    if isinstance(value, dict) and value.get("status"):
        return str(value["status"])
    return "legacy_unknown"


def staleness_status(data: dict[str, Any]) -> str:
    value = data.get("staleness")
    if isinstance(value, dict) and value.get("status"):
        return str(value["status"])
    return "legacy_unknown"


def normalize_dependency_path(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    text = raw.strip().replace("\\", "/")
    if not text:
        return None
    path = Path(text)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            return text
    return text


def extract_path_from_dependency(value: Any) -> str | None:
    if isinstance(value, str):
        return normalize_dependency_path(value)
    if isinstance(value, dict):
        for key in ("path", "file", "source_file", "source_path", "artifact_path", "dependency_path"):
            if key in value:
                return normalize_dependency_path(value[key])
    return None


def extract_dependency_paths(data: dict[str, Any]) -> tuple[str, ...]:
    paths: set[str] = set()

    def add(value: Any) -> None:
        path = extract_path_from_dependency(value)
        if path and path.endswith((".json", ".md")):
            paths.add(path)

    source_files = data.get("source_files")
    if isinstance(source_files, list):
        for item in source_files:
            add(item)
    else:
        add(source_files)

    dependencies = data.get("dependencies")
    if isinstance(dependencies, dict):
        for key, value in dependencies.items():
            if key in {"required", "optional", "source_files"} and isinstance(value, list):
                for item in value:
                    add(item)
            else:
                add(value)
    elif isinstance(dependencies, list):
        for item in dependencies:
            add(item)

    return tuple(sorted(paths))


def load_json_artifact(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise IngestError(f"{repo_relative(path)} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise IngestError(f"{repo_relative(path)} root JSON value must be an object")
    return data


def build_artifact_plan(path: Path, *, module_override: str | None = None) -> ArtifactPlan:
    path = path.resolve()
    try:
        rel_path = repo_relative(path)
    except ValueError as exc:
        raise IngestError(f"{path} is outside the current repository") from exc
    if "temp" in path.relative_to(ROOT).parts or "runtime" in path.relative_to(ROOT).parts:
        raise IngestError(f"{rel_path} is under a transient directory and cannot be imported")

    data = load_json_artifact(path)
    module = module_override or normalize_module(data.get("module"), path)
    generated_at = str(data.get("generated_at") or data.get("last_updated") or timestamp_from_name(path) or "legacy_unknown")
    basis_date = data.get("basis_date") or data.get("date")
    basis_trade_date = data.get("basis_trade_date")
    code = data.get("code") or data.get("ts_code") or data.get("security_code")
    name = data.get("name") or data.get("security_name")

    return ArtifactPlan(
        path=path,
        rel_path=rel_path,
        sha256=file_sha256(path),
        data=data,
        module=str(module),
        generated_at=generated_at,
        basis_date=str(basis_date) if basis_date is not None else None,
        basis_trade_date=str(basis_trade_date) if basis_trade_date is not None else None,
        code=str(code) if code is not None else None,
        name=str(name) if name is not None else None,
        quality_status=quality_status(data),
        staleness_status=staleness_status(data),
        dependency_paths=extract_dependency_paths(data),
        privacy_findings=tuple(scan_json_privacy(data)),
    )


def expand_artifact_paths(path_args: list[str], *, all_artifacts: bool = False) -> list[Path]:
    candidates: list[Path] = []
    if all_artifacts:
        candidates.extend(RESEARCH.rglob("*.json"))

    for item in path_args:
        pattern_path = Path(item)
        pattern = str(pattern_path if pattern_path.is_absolute() else ROOT / pattern_path)
        matches = [Path(match) for match in glob.glob(pattern)]
        if not matches:
            matches = [pattern_path if pattern_path.is_absolute() else ROOT / pattern_path]
        for match in matches:
            if match.is_dir():
                candidates.extend(match.rglob("*.json"))
            else:
                candidates.append(match)

    unique = {path.resolve(): path.resolve() for path in candidates if path.exists() and path.is_file()}
    return sorted(unique)


def find_existing_artifact_id(conn: sqlite3.Connection, dependency_path: str) -> str | None:
    row = conn.execute(
        "SELECT artifact_id FROM artifacts WHERE path = ? ORDER BY ingested_at DESC LIMIT 1",
        (dependency_path,),
    ).fetchone()
    return str(row["artifact_id"]) if row else None


def write_plan(conn: sqlite3.Connection, plan: ArtifactPlan) -> dict[str, int]:
    counts = {"research_runs_inserted": 0, "artifacts_inserted": 0, "privacy_rows_inserted": 0}

    result = conn.execute(
        """
        INSERT OR IGNORE INTO research_runs(
          run_id, module, generated_at, basis_date, basis_trade_date,
          quality_status, staleness_status, privacy_policy
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            plan.run_id,
            plan.module,
            plan.generated_at,
            plan.basis_date,
            plan.basis_trade_date,
            plan.quality_status,
            plan.staleness_status,
            plan.privacy_status,
        ),
    )
    counts["research_runs_inserted"] += result.rowcount

    result = conn.execute(
        """
        INSERT OR IGNORE INTO artifacts(
          artifact_id, run_id, module, artifact_type, path, sha256,
          generated_at, basis_date, basis_trade_date, code, name, raw_json,
          quality_status, staleness_status
        ) VALUES (?, ?, ?, 'json', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            plan.artifact_id,
            plan.run_id,
            plan.module,
            plan.rel_path,
            plan.sha256,
            plan.generated_at,
            plan.basis_date,
            plan.basis_trade_date,
            plan.code,
            plan.name,
            plan.safe_raw_json,
            plan.quality_status,
            plan.staleness_status,
        ),
    )
    counts["artifacts_inserted"] += result.rowcount

    scan_id = f"privacy_{stable_digest(plan.artifact_id)[:20]}"
    result = conn.execute(
        """
        INSERT OR IGNORE INTO privacy_scan_results(
          privacy_scan_id, artifact_id, run_id, scanner_version, status,
          finding_count, findings_json
        ) VALUES (?, ?, ?, 'db_privacy_v1', ?, ?, ?)
        """,
        (
            scan_id,
            plan.artifact_id,
            plan.run_id,
            plan.privacy_status,
            len(plan.privacy_findings),
            json.dumps(list(plan.privacy_findings), ensure_ascii=False, sort_keys=True),
        ),
    )
    counts["privacy_rows_inserted"] += result.rowcount

    return counts


def write_dependencies(conn: sqlite3.Connection, plan: ArtifactPlan, path_to_artifact: dict[str, str]) -> int:
    inserted = 0
    for dependency_path in plan.dependency_paths:
        depends_on_id = path_to_artifact.get(dependency_path) or find_existing_artifact_id(conn, dependency_path)
        dependency_sha = None
        dep_abs = ROOT / dependency_path
        if dep_abs.exists() and dep_abs.is_file():
            dependency_sha = file_sha256(dep_abs)
        result = conn.execute(
            """
            INSERT OR IGNORE INTO artifact_dependencies(
              artifact_id, depends_on_artifact_id, dependency_path, dependency_role,
              dependency_sha256, required, status
            ) VALUES (?, ?, ?, 'source', ?, 1, ?)
            """,
            (
                plan.artifact_id,
                depends_on_id,
                dependency_path,
                dependency_sha,
                "ok" if dep_abs.exists() else "missing",
            ),
        )
        inserted += result.rowcount
    return inserted


def ingest_artifacts(
    db_path: str | Path,
    paths: list[Path],
    *,
    module_override: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    plans = [build_artifact_plan(path, module_override=module_override) for path in paths]
    path_to_artifact = {plan.rel_path: plan.artifact_id for plan in plans}
    privacy_blocked = sum(1 for plan in plans if plan.privacy_findings)
    finding_count = sum(len(plan.privacy_findings) for plan in plans)
    summary: dict[str, Any] = {
        "status": "ok",
        "dry_run": dry_run,
        "planned_artifacts": len(plans),
        "privacy_blocked_raw_json": privacy_blocked,
        "privacy_finding_count": finding_count,
        "modules": sorted({plan.module for plan in plans}),
    }
    if dry_run:
        return summary

    conn = connect(db_path)
    try:
        counts = {"research_runs_inserted": 0, "artifacts_inserted": 0, "dependencies_inserted": 0, "privacy_rows_inserted": 0}
        for plan in plans:
            for key, value in write_plan(conn, plan).items():
                counts[key] += value
        normalized_counts: dict[str, int] = {}
        from .extractors.action_plan import write_action_plan
        from .extractors.market_score import write_market_score
        from .extractors.portfolio_snapshot import write_portfolio_snapshot
        from .extractors.security_profile import write_security_profile
        from .extractors.target_allocation import write_target_allocation
        from .extractors.theme_review import write_theme_review
        from .extractors.valuation_report import write_valuation_report

        for plan in plans:
            if plan.module == "valuation_report":
                for key, value in write_valuation_report(conn, plan).items():
                    normalized_counts[key] = normalized_counts.get(key, 0) + value
            elif plan.module == "portfolio_snapshot":
                for key, value in write_portfolio_snapshot(conn, plan).items():
                    normalized_counts[key] = normalized_counts.get(key, 0) + value
            elif plan.module == "target_allocation":
                for key, value in write_target_allocation(conn, plan).items():
                    normalized_counts[key] = normalized_counts.get(key, 0) + value
            elif plan.module == "action_plan":
                for key, value in write_action_plan(conn, plan).items():
                    normalized_counts[key] = normalized_counts.get(key, 0) + value
            elif plan.module == "market_score":
                for key, value in write_market_score(conn, plan).items():
                    normalized_counts[key] = normalized_counts.get(key, 0) + value
            elif plan.module == "theme_review":
                for key, value in write_theme_review(conn, plan).items():
                    normalized_counts[key] = normalized_counts.get(key, 0) + value
            elif plan.module in {"etf_profile", "stock_profile"}:
                for key, value in write_security_profile(conn, plan).items():
                    normalized_counts[key] = normalized_counts.get(key, 0) + value
        for plan in plans:
            counts["dependencies_inserted"] += write_dependencies(conn, plan, path_to_artifact)
        conn.commit()
        summary.update(counts)
        summary.update(normalized_counts)
        return summary
    finally:
        conn.close()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="temp/history_db/myinvest_history.sqlite3", help="SQLite database path.")
    parser.add_argument("--all", action="store_true", help="Import all research JSON artifacts.")
    parser.add_argument("--path", action="append", default=[], help="Artifact file, directory, or glob pattern to import.")
    parser.add_argument("--module", help="Override module name for imported artifacts.")
    parser.add_argument("--dry-run", action="store_true", help="Plan ingestion without writing to the database.")
    return parser


def cli_main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if not args.all and not args.path:
        parser.error("Use --all or at least one --path")

    try:
        paths = expand_artifact_paths(args.path, all_artifacts=args.all)
        summary = ingest_artifacts(args.db, paths, module_override=args.module, dry_run=args.dry_run)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - keep CLI output machine-readable.
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
