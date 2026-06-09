#!/usr/bin/env python3
"""Ingest current-only MyInvest research state into the read-only Web SQLite DB."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web.backend.app.config import DB_PATH, DECISION_LOG_PATH, EXECUTABLE_ACTIONS, LATEST_INDEX_PATH, REQUIRED_CURRENT_MODULES
from web.backend.app.db import Base, engine, reset_database
from web.backend.app.models import (
    ActionItem,
    ActionPlan,
    Artifact,
    BucketAllocation,
    CurrentModule,
    DecisionLogEntry,
    IntradayBucketRule,
    IntradayRule,
    LiquidityGate,
    MarketPositionMapping,
    MarketScore,
    PortfolioPosition,
    PortfolioSnapshot,
    Profile,
    ResearchFirstItem,
    Subject,
    SystemCheckResult,
    TargetAllocation,
    Valuation,
)
from web.backend.app.services.ratio_only import RatioOnlyService


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def rel_path(path: Path | str) -> str:
    p = Path(path)
    if p.is_absolute():
        return p.resolve().relative_to(ROOT.resolve()).as_posix()
    return p.as_posix()


def resolve_repo_path(value: Any) -> Path:
    if not value:
        raise ValueError("empty path")
    text = str(value)
    path = Path(text)
    if path.is_absolute():
        raise ValueError(f"absolute path is not allowed: {text}")
    resolved = (ROOT / path).resolve()
    root_resolved = ROOT.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError(f"path escapes repository root: {text}")
    if not resolved.exists():
        raise FileNotFoundError(text)
    return resolved


def plain_code(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def split_exchange(code: Any) -> tuple[str | None, str | None]:
    text = str(code or "").strip()
    if "." in text:
        base, exchange = text.split(".", 1)
        return base or None, exchange or None
    return text or None, None


def parse_float(value: Any) -> float | None:
    try:
        text = str(value).replace("%", "").replace("pp", "").strip()
        if not text:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def parse_range(value: Any) -> tuple[float | None, float | None]:
    text = str(value or "").replace("%", "").strip()
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*[-~]\s*(-?\d+(?:\.\d+)?)", text)
    if match:
        return float(match.group(1)), float(match.group(2))
    single = parse_float(value)
    return single, single


def parse_pp_pair(value: Any) -> tuple[float | None, float | None]:
    nums = [float(item) for item in re.findall(r"-?\d+(?:\.\d+)?", str(value or ""))]
    if not nums:
        return None, None
    if len(nums) == 1:
        return nums[0], nums[0]
    return nums[0], nums[1]


def safe_json(value: Any) -> str:
    return RatioOnlyService.safe_json(value)


def current_ref(index: dict[str, Any], module: str) -> dict[str, Any]:
    ref = (index.get("modules") or {}).get(module)
    if not isinstance(ref, dict):
        raise KeyError(f"latest_index.modules.{module} missing")
    resolve_repo_path(ref.get("path"))
    return ref


def load_current_module(index: dict[str, Any], module: str) -> dict[str, Any]:
    ref = current_ref(index, module)
    data = read_json(resolve_repo_path(ref["path"]))
    if not isinstance(data, dict):
        raise ValueError(f"{module} current artifact is not an object")
    return data


def run_check(name: str, args: list[str]) -> tuple[str, str]:
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = "\n".join(part for part in [completed.stdout.strip(), completed.stderr.strip()] if part)
    status = "ok" if completed.returncode == 0 else "fail"
    if status != "ok":
        raise RuntimeError(f"{name} failed\n{output}")
    return status, output


def validate_inputs(index: dict[str, Any]) -> list[tuple[str, str, str]]:
    missing = [item for item in sorted(REQUIRED_CURRENT_MODULES) if item not in (index.get("modules") or {})]
    if missing:
        raise KeyError(f"missing current modules: {', '.join(missing)}")
    action_path = current_ref(index, "action_plan")["path"]
    checks = [
        ("ratio_only", ["scripts/check_ratio_only.py", "--path", str(action_path)]),
        ("research_first_gate", ["scripts/check_research_first_gate.py", "--path", str(action_path)]),
        ("allocation_consistency", ["scripts/check_cross_file_allocation_consistency.py"]),
        ("project_check_current_only", ["scripts/project_check.py", "--current-only"]),
    ]
    results = []
    for name, args in checks:
        status, message = run_check(name, args)
        results.append((name, status, message))
    return results


def add_artifact(session: Session, ref: dict[str, Any], artifact_type: str, is_current: bool, raw: dict[str, Any]) -> Artifact:
    artifact = Artifact(
        module=str(ref.get("module") or artifact_type),
        subject_code=ref.get("code"),
        artifact_type=artifact_type,
        path=rel_path(ref.get("path")),
        generated_at=ref.get("generated_at"),
        basis_trade_date=ref.get("basis_trade_date"),
        sha256=ref.get("sha256"),
        raw_json=safe_json(raw),
        is_current=is_current,
    )
    session.add(artifact)
    session.flush()
    return artifact


def upsert_subject(cache: dict[str, Subject], session: Session, code: Any, name: Any, subject_type: Any, bucket: Any, status: Any = None) -> Subject:
    code_text = str(code or "").strip()
    name_text = RatioOnlyService.sanitize_text(str(name or "").strip()) or None
    base_code, exchange = split_exchange(code_text)
    key = plain_code(code_text) or f"{subject_type}:{name_text}"
    if key in cache:
        subject = cache[key]
        if code_text and ("." in code_text or not subject.code):
            subject.code = code_text
        if name_text and not subject.name:
            subject.name = name_text
        if subject_type and not subject.subject_type:
            subject.subject_type = str(subject_type)
        if bucket:
            subject.bucket = str(bucket)
        if status:
            subject.status = str(status)
        if exchange:
            subject.exchange = exchange
        session.flush()
        return subject
    subject = Subject(
        code=code_text or None,
        name=name_text,
        subject_type=str(subject_type or "").strip() or None,
        exchange=exchange,
        bucket=str(bucket or "").strip() or None,
        status=str(status or "").strip() or None,
    )
    if not subject.code and base_code:
        subject.code = base_code
    session.add(subject)
    session.flush()
    cache[key] = subject
    return subject


def find_511360_registry(etf_registry: dict[str, Any]) -> dict[str, Any]:
    for row in etf_registry.get("etfs") or []:
        if plain_code(row.get("code")) == "511360":
            return row
    raise KeyError("511360 not found in current etf_registry")


def import_current_modules(session: Session, index: dict[str, Any], imported_at: str) -> dict[str, Artifact]:
    artifacts: dict[str, Artifact] = {}
    for module, ref in sorted((index.get("modules") or {}).items()):
        resolve_repo_path(ref.get("path"))
        raw = {
            "module": module,
            "path": ref.get("path"),
            "generated_at": ref.get("generated_at"),
            "basis_trade_date": ref.get("basis_trade_date"),
            "quality": (ref.get("quality") or {}).get("status"),
            "staleness": (ref.get("staleness") or {}).get("status"),
        }
        artifact = add_artifact(session, ref, module, True, raw)
        artifacts[module] = artifact
        session.add(CurrentModule(module=module, artifact_id=artifact.id, updated_at=imported_at))
    return artifacts


def import_market_score(session: Session, data: dict[str, Any]) -> MarketScore:
    summary = data.get("summary") or {}
    equity_min, equity_max = parse_range(summary.get("equity_allocation_range"))
    cash_min, cash_max = parse_range(summary.get("bond_cash_allocation_range"))
    row = MarketScore(
        score=parse_float(summary.get("market_position_score")),
        state=RatioOnlyService.sanitize_text(str(summary.get("market_state") or "")) or None,
        basis_trade_date=data.get("basis_trade_date"),
        generated_at=data.get("generated_at"),
        equity_min_pct=equity_min,
        equity_max_pct=equity_max,
        cash_min_pct=cash_min,
        cash_max_pct=cash_max,
        raw_json=safe_json(
            {
                "summary": {
                    "market_state": summary.get("market_state"),
                    "market_position_score": summary.get("market_position_score"),
                    "equity_allocation_range": summary.get("equity_allocation_range"),
                    "bond_cash_allocation_range": summary.get("bond_cash_allocation_range"),
                    "offensive_bucket_status": summary.get("offensive_bucket_status"),
                }
            }
        ),
    )
    session.add(row)
    session.flush()
    return row


def import_market_position_mapping(session: Session, data: dict[str, Any]) -> None:
    for item in data.get("ranges") or []:
        equity_min, equity_max = parse_range(item.get("equity_allocation_range"))
        cash_min, cash_max = parse_range(item.get("bond_cash_allocation_range"))
        session.add(
            MarketPositionMapping(
                score_min=parse_float(item.get("score_min")),
                score_max=parse_float(item.get("score_max")),
                equity_min_pct=equity_min,
                equity_max_pct=equity_max,
                cash_min_pct=cash_min,
                cash_max_pct=cash_max,
                label=RatioOnlyService.sanitize_text(str(item.get("market_state") or "")) or None,
                is_active=True,
            )
        )


def import_portfolio(session: Session, data: dict[str, Any], subjects: dict[str, Subject]) -> PortfolioSnapshot:
    summary = data.get("summary") or {}
    snapshot = PortfolioSnapshot(
        generated_at=data.get("generated_at"),
        basis_trade_date=data.get("date"),
        privacy_policy="ratio-only fields persisted; source prices and account details excluded",
        equity_pct=parse_float(summary.get("equity_weight_pct")),
        cash_short_pct=parse_float(summary.get("bond_cash_weight_pct")),
        raw_json=safe_json(
            {
                "generated_at": data.get("generated_at"),
                "basis_trade_date": data.get("date"),
                "equity_pct": summary.get("equity_weight_pct"),
                "cash_short_pct": summary.get("bond_cash_weight_pct"),
            }
        ),
    )
    session.add(snapshot)
    session.flush()
    for item in data.get("holdings") or []:
        subject = upsert_subject(
            subjects,
            session,
            item.get("ts_code") or item.get("code"),
            item.get("name"),
            item.get("type"),
            item.get("allocation_bucket") or item.get("category"),
            None,
        )
        session.add(
            PortfolioPosition(
                snapshot_id=snapshot.id,
                subject_id=subject.id,
                bucket=item.get("allocation_bucket") or item.get("category"),
                position_pct=parse_float(item.get("weight_pct")),
                reference_only_flag=True,
            )
        )
    return snapshot


def import_target_allocation(session: Session, data: dict[str, Any], market_score: MarketScore) -> TargetAllocation:
    summary = data.get("summary") or {}
    equity_min, equity_max = parse_range(summary.get("recommended_equity_range"))
    cash_min, cash_max = parse_range(summary.get("recommended_bond_cash_range"))
    target = TargetAllocation(
        generated_at=data.get("generated_at"),
        basis_trade_date=data.get("basis_trade_date"),
        market_score_id=market_score.id,
        equity_min_pct=equity_min,
        equity_max_pct=equity_max,
        cash_min_pct=cash_min,
        cash_max_pct=cash_max,
        raw_json=safe_json(
            {
                "generated_at": data.get("generated_at"),
                "basis_trade_date": data.get("basis_trade_date"),
                "recommended_equity_range": summary.get("recommended_equity_range"),
                "recommended_bond_cash_range": summary.get("recommended_bond_cash_range"),
            }
        ),
    )
    session.add(target)
    session.flush()
    for item in ((data.get("actual_allocation_overlay") or {}).get("buckets") or []):
        session.add(
            BucketAllocation(
                target_allocation_id=target.id,
                bucket=item.get("key") or item.get("label"),
                actual_pct=parse_float(item.get("actual_pct")),
                target_pct=parse_float(item.get("target_pct")),
                gap_pct=parse_float(item.get("gap_pct")),
            )
        )
    return target


def import_intraday_rules(session: Session, data: dict[str, Any]) -> IntradayRule:
    staleness = data.get("staleness") or {}
    gate = data.get("global_gate") or {}
    status = str(staleness.get("status") or "unknown")
    rules = IntradayRule(
        generated_at=data.get("generated_at"),
        basis_trade_date=data.get("basis_trade_date"),
        status=status,
        stale_flag=status in {"stale", "blocked"},
        degraded_flag=status == "degraded",
        risk_mode=str(gate.get("default_market_gate") or ""),
        raw_json=safe_json(
            {
                "generated_at": data.get("generated_at"),
                "status": status,
                "risk_mode": gate.get("default_market_gate"),
            }
        ),
    )
    session.add(rules)
    session.flush()
    for item in ((data.get("allocation_map") or {}).get("buckets") or []):
        session.add(
            IntradayBucketRule(
                intraday_rules_id=rules.id,
                bucket=item.get("key") or item.get("label"),
                actual_pct=parse_float(item.get("actual_pct")),
                target_pct=parse_float(item.get("target_pct")),
                gap_pct=parse_float(item.get("gap_pct")),
            )
        )
    return rules


def import_action_plan(session: Session, data: dict[str, Any], subjects: dict[str, Subject]) -> ActionPlan:
    summary = data.get("summary") or {}
    preconditions = data.get("preconditions") or {}
    market = preconditions.get("market_position") or {}
    plan = ActionPlan(
        generated_at=data.get("generated_at"),
        basis_trade_date=data.get("basis_trade_date"),
        privacy_policy="ratio-only action plan persisted",
        market_state=RatioOnlyService.sanitize_text(str(market.get("state") or market.get("market_state") or "")) or None,
        status=str(summary.get("action_state") or summary.get("recommendation_strength") or "unknown"),
        raw_json=safe_json(
            {
                "generated_at": data.get("generated_at"),
                "basis_trade_date": data.get("basis_trade_date"),
                "summary": {
                    "action_state": summary.get("action_state"),
                    "recommendation_strength": summary.get("recommendation_strength"),
                },
            }
        ),
    )
    session.add(plan)
    session.flush()
    for idx, item in enumerate(data.get("actions") or [], start=1):
        subject_data = item.get("subject") or {}
        subject = upsert_subject(
            subjects,
            session,
            subject_data.get("code"),
            subject_data.get("name"),
            subject_data.get("type"),
            item.get("bucket_role"),
            None,
        )
        target_min, target_max = parse_range(item.get("target_position"))
        change_min, change_max = parse_pp_pair(item.get("suggested_change"))
        reason = "; ".join(str(x) for x in (item.get("evidence") or []))
        session.add(
            ActionItem(
                action_plan_id=plan.id,
                sequence=idx,
                action_type=item.get("action_type"),
                subject_id=subject.id,
                bucket=item.get("bucket_role"),
                current_position_pct=parse_float(item.get("current_position")),
                target_range_min_pct=target_min,
                target_range_max_pct=target_max,
                suggested_change_min_pp=change_min,
                suggested_change_max_pp=change_max,
                reason=RatioOnlyService.sanitize_text(reason),
                requires_manual_confirmation=bool(item.get("needs_manual_confirmation")),
            )
        )
    for item in data.get("research_first_list") or data.get("research_first") or []:
        subject_data = item.get("subject") or item
        subject = upsert_subject(
            subjects,
            session,
            subject_data.get("code"),
            subject_data.get("name"),
            subject_data.get("type") or item.get("subject_type"),
            item.get("bucket_role"),
            "research_first",
        )
        reason = item.get("blocking_reason") or item.get("reason") or "; ".join(item.get("blocking_reasons") or [])
        session.add(
            ResearchFirstItem(
                action_plan_id=plan.id,
                subject_id=subject.id,
                missing_profile="profile" in str(reason).lower(),
                missing_valuation="valuation" in str(reason).lower(),
                missing_liquidity="liquidity" in str(reason).lower(),
                missing_theme_binding="theme" in str(reason).lower(),
                allowed_conclusion="research_first",
                blocking_reason=RatioOnlyService.sanitize_text(str(reason or "")),
            )
        )
    return plan


def import_511360_gates(
    session: Session,
    index: dict[str, Any],
    etf_registry: dict[str, Any],
    liquidity_registry: dict[str, Any],
    subjects: dict[str, Subject],
) -> None:
    row = find_511360_registry(etf_registry)
    subject = upsert_subject(subjects, session, row.get("code"), row.get("name"), "ETF", row.get("bucket_role"), row.get("status"))

    profile_path = resolve_repo_path(row.get("last_profile_json"))
    profile_data = read_json(profile_path)
    profile_ref = {
        "module": "etf_profile",
        "code": profile_data.get("code") or row.get("code"),
        "path": rel_path(profile_path),
        "generated_at": profile_data.get("generated_at"),
        "basis_trade_date": profile_data.get("basis_trade_date") or profile_data.get("basis_date") or profile_data.get("date"),
        "sha256": None,
    }
    profile_artifact = add_artifact(session, profile_ref, "511360_profile", False, profile_ref)
    session.add(
        Profile(
            subject_id=subject.id,
            status=row.get("status") or "profile_generated",
            source_artifact_id=profile_artifact.id,
            generated_at=profile_ref["generated_at"],
            basis_date=profile_ref["basis_trade_date"],
            raw_json=safe_json({"code": row.get("code"), "status": row.get("status"), "path": rel_path(profile_path)}),
        )
    )

    instruments = liquidity_registry.get("instruments") or {}
    gate = instruments.get("511360") or next((item for item in instruments.values() if plain_code(item.get("code")) == "511360"), None)
    if not isinstance(gate, dict):
        raise KeyError("511360 liquidity gate missing")
    valuation_path = resolve_repo_path(gate.get("valuation_source"))
    valuation_data = read_json(valuation_path)
    valuation_ref = {
        "module": "valuation_report",
        "code": valuation_data.get("code") or gate.get("code"),
        "path": rel_path(valuation_path),
        "generated_at": valuation_data.get("generated_at"),
        "basis_trade_date": valuation_data.get("basis_date") or valuation_data.get("basis_trade_date") or valuation_data.get("date"),
        "sha256": None,
    }
    valuation_artifact = add_artifact(session, valuation_ref, "511360_valuation", False, valuation_ref)
    session.add(
        Valuation(
            subject_id=subject.id,
            valuation_status=gate.get("valuation_status"),
            valuation_source_artifact_id=valuation_artifact.id,
            generated_at=valuation_ref["generated_at"],
            basis_date=valuation_ref["basis_trade_date"],
            raw_json=safe_json({"code": gate.get("code"), "valuation_status": gate.get("valuation_status"), "path": rel_path(valuation_path)}),
        )
    )
    session.add(
        LiquidityGate(
            subject_id=subject.id,
            liquidity_status=gate.get("liquidity_status"),
            duration_boundary_confirmed=bool(gate.get("duration_boundary_confirmed")),
            valuation_status=gate.get("valuation_status"),
            interest_rate_risk_disclosed=bool(gate.get("interest_rate_risk_disclosed")),
            credit_risk_disclosed=bool(gate.get("credit_risk_disclosed")),
            liquidity_risk_disclosed=bool(gate.get("liquidity_risk_disclosed")),
            source_profile_artifact_id=profile_artifact.id,
            source_valuation_artifact_id=valuation_artifact.id,
            generated_at=(index.get("modules") or {}).get("liquidity_gate_registry", {}).get("generated_at"),
        )
    )


def import_decision_log(session: Session, related_action_plan_id: int | None) -> None:
    if not DECISION_LOG_PATH.exists():
        return
    entries = []
    for line in DECISION_LOG_PATH.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        if line.startswith("## ") or re.match(r"^\d{4}-\d{2}-\d{2}", line):
            entries.append(line.strip("# ").strip())
    for entry in entries[-40:]:
        session.add(
            DecisionLogEntry(
                entry_time=entry.split(" ", 1)[0] if entry else None,
                entry_type="decision_log",
                related_action_plan_id=related_action_plan_id,
                summary=RatioOnlyService.sanitize_text(entry[:240]),
                reason="current read-only web ingest",
                ratio_only_text=RatioOnlyService.sanitize_text(entry[:240]),
                raw_markdown=RatioOnlyService.sanitize_text(entry[:240]),
            )
        )


def import_system_checks(session: Session, checks: list[tuple[str, str, str]], generated_at: str) -> None:
    for name, status, message in checks:
        session.add(
            SystemCheckResult(
                check_name=name,
                status=status,
                message=RatioOnlyService.sanitize_text(message[:1000]),
                generated_at=generated_at,
            )
        )


def verify_database(session: Session) -> None:
    for table in Base.metadata.sorted_tables:
        rows = session.execute(select(table)).mappings().all()
        for row in rows:
            payload = dict(row)
            for key in ["raw_json", "raw_markdown", "privacy_policy"]:
                if key in payload and isinstance(payload[key], str):
                    try:
                        payload[key] = json.loads(payload[key])
                    except json.JSONDecodeError:
                        pass
            RatioOnlyService.assert_safe(payload, f"db.{table.name}")


def ingest() -> dict[str, int]:
    index = read_json(LATEST_INDEX_PATH)
    checks = validate_inputs(index)
    generated_at = now_text()
    reset_database()
    with Session(engine) as session:
        artifacts = import_current_modules(session, index, generated_at)
        data = {module: load_current_module(index, module) for module in REQUIRED_CURRENT_MODULES}
        subjects: dict[str, Subject] = {}
        market_score = import_market_score(session, data["market_score"])
        import_market_position_mapping(session, data["market_position_mapping"])
        import_portfolio(session, data["portfolio_snapshot"], subjects)
        import_target_allocation(session, data["target_allocation"], market_score)
        import_intraday_rules(session, data["intraday_rules"])
        action_plan = import_action_plan(session, data["action_plan"], subjects)
        import_511360_gates(session, index, data["etf_registry"], data["liquidity_gate_registry"], subjects)
        import_decision_log(session, action_plan.id)
        import_system_checks(session, checks, generated_at)
        verify_database(session)
        session.commit()
        counts = {table.name: session.execute(select(table)).all() for table in Base.metadata.sorted_tables}
        return {name: len(rows) for name, rows in counts.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        counts = ingest()
    except Exception as exc:  # noqa: BLE001 - CLI should surface blocker.
        print(f"[FAIL] web DB ingest failed: {exc}")
        return 1
    print("Web DB ingest: OK")
    print(f"Database: {DB_PATH.relative_to(ROOT).as_posix()}")
    print(json.dumps(counts, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
