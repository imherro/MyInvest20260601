from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module: Mapped[str] = mapped_column(String, index=True)
    subject_code: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    artifact_type: Mapped[str | None] = mapped_column(String, nullable=True)
    path: Mapped[str] = mapped_column(String, unique=True)
    generated_at: Mapped[str | None] = mapped_column(String, nullable=True)
    basis_trade_date: Mapped[str | None] = mapped_column(String, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_json: Mapped[str] = mapped_column(Text)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class CurrentModule(Base):
    __tablename__ = "current_modules"

    module: Mapped[str] = mapped_column(String, primary_key=True)
    artifact_id: Mapped[int] = mapped_column(ForeignKey("artifacts.id"))
    updated_at: Mapped[str] = mapped_column(String)


class MarketScore(Base):
    __tablename__ = "market_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    basis_trade_date: Mapped[str | None] = mapped_column(String, nullable=True)
    generated_at: Mapped[str | None] = mapped_column(String, nullable=True)
    equity_min_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    equity_max_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    cash_min_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    cash_max_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_json: Mapped[str] = mapped_column(Text)


class MarketPositionMapping(Base):
    __tablename__ = "market_position_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    score_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    equity_min_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    equity_max_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    cash_min_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    cash_max_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    subject_type: Mapped[str | None] = mapped_column(String, nullable=True)
    exchange: Mapped[str | None] = mapped_column(String, nullable=True)
    bucket: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    source_artifact_id: Mapped[int | None] = mapped_column(ForeignKey("artifacts.id"), nullable=True)
    generated_at: Mapped[str | None] = mapped_column(String, nullable=True)
    basis_date: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_json: Mapped[str] = mapped_column(Text)


class Valuation(Base):
    __tablename__ = "valuations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    valuation_status: Mapped[str | None] = mapped_column(String, nullable=True)
    valuation_source_artifact_id: Mapped[int | None] = mapped_column(ForeignKey("artifacts.id"), nullable=True)
    generated_at: Mapped[str | None] = mapped_column(String, nullable=True)
    basis_date: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_json: Mapped[str] = mapped_column(Text)


class LiquidityGate(Base):
    __tablename__ = "liquidity_gates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    liquidity_status: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_boundary_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    valuation_status: Mapped[str | None] = mapped_column(String, nullable=True)
    interest_rate_risk_disclosed: Mapped[bool] = mapped_column(Boolean, default=False)
    credit_risk_disclosed: Mapped[bool] = mapped_column(Boolean, default=False)
    liquidity_risk_disclosed: Mapped[bool] = mapped_column(Boolean, default=False)
    source_profile_artifact_id: Mapped[int | None] = mapped_column(ForeignKey("artifacts.id"), nullable=True)
    source_valuation_artifact_id: Mapped[int | None] = mapped_column(ForeignKey("artifacts.id"), nullable=True)
    generated_at: Mapped[str | None] = mapped_column(String, nullable=True)


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    generated_at: Mapped[str | None] = mapped_column(String, nullable=True)
    basis_trade_date: Mapped[str | None] = mapped_column(String, nullable=True)
    privacy_policy: Mapped[str | None] = mapped_column(Text, nullable=True)
    equity_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    cash_short_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_json: Mapped[str] = mapped_column(Text)


class PortfolioPosition(Base):
    __tablename__ = "portfolio_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("portfolio_snapshots.id"))
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    bucket: Mapped[str | None] = mapped_column(String, nullable=True)
    position_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_only_flag: Mapped[bool] = mapped_column(Boolean, default=True)


class TargetAllocation(Base):
    __tablename__ = "target_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    generated_at: Mapped[str | None] = mapped_column(String, nullable=True)
    basis_trade_date: Mapped[str | None] = mapped_column(String, nullable=True)
    market_score_id: Mapped[int | None] = mapped_column(ForeignKey("market_scores.id"), nullable=True)
    equity_min_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    equity_max_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    cash_min_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    cash_max_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_json: Mapped[str] = mapped_column(Text)


class BucketAllocation(Base):
    __tablename__ = "bucket_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_allocation_id: Mapped[int] = mapped_column(ForeignKey("target_allocations.id"))
    bucket: Mapped[str] = mapped_column(String, index=True)
    actual_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    gap_pct: Mapped[float | None] = mapped_column(Float, nullable=True)


class ActionPlan(Base):
    __tablename__ = "action_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    generated_at: Mapped[str | None] = mapped_column(String, nullable=True)
    basis_trade_date: Mapped[str | None] = mapped_column(String, nullable=True)
    privacy_policy: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_state: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_json: Mapped[str] = mapped_column(Text)


class ActionItem(Base):
    __tablename__ = "action_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action_plan_id: Mapped[int] = mapped_column(ForeignKey("action_plans.id"))
    sequence: Mapped[int] = mapped_column(Integer)
    action_type: Mapped[str | None] = mapped_column(String, nullable=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    bucket: Mapped[str | None] = mapped_column(String, nullable=True)
    current_position_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_range_min_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_range_max_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    suggested_change_min_pp: Mapped[float | None] = mapped_column(Float, nullable=True)
    suggested_change_max_pp: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_manual_confirmation: Mapped[bool] = mapped_column(Boolean, default=True)


class ResearchFirstItem(Base):
    __tablename__ = "research_first_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action_plan_id: Mapped[int | None] = mapped_column(ForeignKey("action_plans.id"), nullable=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    missing_profile: Mapped[bool] = mapped_column(Boolean, default=False)
    missing_valuation: Mapped[bool] = mapped_column(Boolean, default=False)
    missing_liquidity: Mapped[bool] = mapped_column(Boolean, default=False)
    missing_theme_binding: Mapped[bool] = mapped_column(Boolean, default=False)
    allowed_conclusion: Mapped[str | None] = mapped_column(String, nullable=True)
    blocking_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class IntradayRule(Base):
    __tablename__ = "intraday_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    generated_at: Mapped[str | None] = mapped_column(String, nullable=True)
    basis_trade_date: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    stale_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    degraded_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_mode: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_json: Mapped[str] = mapped_column(Text)


class IntradayBucketRule(Base):
    __tablename__ = "intraday_bucket_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    intraday_rules_id: Mapped[int] = mapped_column(ForeignKey("intraday_rules.id"))
    bucket: Mapped[str] = mapped_column(String, index=True)
    actual_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    gap_pct: Mapped[float | None] = mapped_column(Float, nullable=True)


class DecisionLogEntry(Base):
    __tablename__ = "decision_log_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_time: Mapped[str | None] = mapped_column(String, nullable=True)
    entry_type: Mapped[str | None] = mapped_column(String, nullable=True)
    related_action_plan_id: Mapped[int | None] = mapped_column(ForeignKey("action_plans.id"), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ratio_only_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)


class SystemCheckResult(Base):
    __tablename__ = "system_check_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    check_name: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[str] = mapped_column(String)
